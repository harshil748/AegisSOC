# AegisSOC Scalability

This document details the scale path referenced by
`docs/adr/0005-mvp-to-production-scale.md`, assuming the target design
load from `prompt.md`: **100M logs/day, ~100K alerts/day, thousands of
suspicious clusters/day, hundreds of analyst investigations/day**, with
strict latency SLOs for triage and enrichment.

Back-of-envelope: 100M logs/day ≈ **1,157 events/sec average**, with
realistic burstiness (business hours, incident spikes) meaning the
system should comfortably absorb **5,000-10,000 events/sec** peaks.

## Scalability path

### 1. Partitioning (Kafka/Redpanda)

The MVP (`docker-compose.yml`, `infra/k8s/34-kafka.yaml`) runs a
single-broker Redpanda with default topic settings — sufficient for
demo/dev throughput but not for 100M/day.

Production guidance:
- **Partition count**: size per-topic partitions for target parallelism,
  not just current load. For `aegis.raw.events`/`aegis.normalized.events`/
  `aegis.enriched.events`, start at **24-48 partitions** — enough
  headroom for normalization/enrichment consumer groups to scale to
  24-48 pods without repartitioning later (repartitioning breaks
  ordering guarantees and is disruptive).
- **Partition key**: partition by `tenant_id` + a coarse entity key
  (e.g. `host` or `src_ip` hash) rather than randomly — this keeps all
  events for a given host/tenant in one partition, which
  `graph_builder` and `detection` rely on for correct temporal ordering
  within an entity's history without needing a separate global sequencer.
- **Broker count**: move from 1 broker (MVP) to a **3-5 broker Redpanda
  or Kafka cluster** (replication factor 3) for durability and
  throughput; use the Strimzi operator if standardizing on upstream
  Kafka instead of Redpanda.
- **Retention**: raw topics need enough retention (7-14 days) to support
  replay/backfill (`aegis.replay.events`) without requiring the
  long-term parquet lake for short-term reprocessing.

### 2. Consumer groups

- Each data-path service (`normalization`, `enrichment`, `graph_builder`,
  `detection`) runs as its own Kafka consumer group — this is already
  the shape of the architecture (ADR 0005), not a change required at
  scale.
- **Scale by adding pods, not by hand-tuning**: consumer group
  parallelism is bounded by partition count, so partition count (above)
  must be sized ahead of the maximum pod count you intend to run.
- **Idempotent/effectively-once processing**: each consumer commits
  offsets only after the corresponding downstream write succeeds
  (Neo4j upsert, OpenSearch index, Postgres insert), and downstream
  writes are themselves idempotent (upsert by deterministic
  `entity_id()`/`event_id()`) — this makes at-least-once Kafka delivery
  behave as effectively-once at the data layer without needing Kafka
  transactions end-to-end.
- **Autoscaling on lag, not just CPU**: the MVP's HPA
  (`infra/k8s/hpa.yaml`) scales `ingestion`/`normalization`/`detection`
  on CPU utilization, which is a reasonable default but an imperfect
  proxy for "am I keeping up with the topic". Production should add a
  KEDA `ScaledObject` with a Kafka trigger keyed on consumer-group lag
  (commented example already included in `infra/k8s/hpa.yaml`) so
  replica count tracks actual backlog, not just CPU.
- **Backpressure**: if a downstream store (Neo4j, OpenSearch) becomes
  the bottleneck, consumer lag on the *upstream* topic is the correct
  signal to throttle/scale on — don't scale ingestion faster than
  graph_builder/detection can drain, or you just move the backlog
  earlier in the pipeline without fixing throughput.

### 3. Neo4j clustering

- MVP: single Neo4j Community instance (`infra/k8s/32-neo4j.yaml`).
  Fine for demo data volumes and a few thousand entities; will not hold
  up under 100M logs/day worth of entity/edge churn.
- Production path:
  1. **Neo4j Enterprise Causal Cluster** (or AuraDB managed) — core
     servers handle writes with consensus, read replicas scale
     `detection`'s graph-feature read queries horizontally.
  2. **Write isolation is already in place**: `graph_builder` is the
     only writer (ADR 0001), so migrating to a cluster is a connection-
     string + driver-routing change, not an application rewrite —
     `detection` and `llm_triage`'s evidence retrieval already only read.
  3. **Batch upserts**: at high event volume, batch multiple node/edge
     upserts per Cypher transaction (e.g. `UNWIND $rows AS row MERGE ...`)
     rather than one transaction per event, to amortize transaction
     overhead — a straightforward change inside `graph_builder`'s write
     path once volume warrants it.
  4. **Graph pruning/summarization**: not every low-confidence, low-
     degree node needs to live in the hot graph forever; define a
     TTL/archival policy that moves cold entities (no activity in N
     days, low `count`/`confidence`) out of the hot cluster into the
     parquet lake, keeping the working graph size bounded.

### 4. Search tiers (OpenSearch)

- MVP: single-node OpenSearch (`infra/k8s/33-opensearch.yaml`) — fine
  for demo/investigation volumes.
- Production: a **hot/warm/cold tiering strategy** via Index State
  Management (ISM) policies:
  - **Hot tier** (fast NVMe-backed nodes): last 7-30 days of
    alerts/cases/enriched events — where the analyst dashboard's alert
    queue and active investigations live; this tier needs to sustain
    heavy write throughput (100K alerts/day) plus low-latency search.
  - **Warm tier**: 30-180 days — still queryable but on cheaper
    storage/fewer replicas, for longer investigations and trend
    analysis.
  - **Cold tier**: 180+ days — ISM-managed snapshot to S3/object
    storage, restorable on demand for compliance/historical
    investigation, not kept in the live cluster.
  - Index-per-day (or per-week) with an alias pointing at the current
    write index is the standard rollover pattern — makes tier migration
    and retention-based deletion an index-lifecycle operation instead of
    a slow per-document delete.
  - Cluster sizing: start with a **3-node dedicated hot tier** (data +
    coordinating) once beyond demo scale; add warm nodes as retention
    requirements grow, independent of hot-tier sizing.

### 5. Relational store (Postgres)

- MVP: single instance. Cases/approvals/audit volume (~100K
  alerts/day → a smaller number of cases after clustering, hundreds of
  approvals/day) is much lower than raw event volume, so Postgres scales
  further than the streaming/graph/search tiers before needing
  horizontal solutions.
- Production path: managed Postgres (RDS/Cloud SQL/Azure Database) with
  read replicas for `case_management`'s read-heavy dashboard queries;
  consider partitioning `audit_log` by month once its append-only growth
  becomes large, since it is never updated/deleted (safe to partition by
  time without touching write-path logic).

### 6. LLM cost decoupling

This is the highest-leverage scaling decision in the whole architecture
(ADR 0005): **LLM calls scale with alert/case volume (~100K/day), never
with raw log volume (100M/day)**, because `llm_triage` is only invoked
after `detection` + `case_management` have already produced a case —
not per event, not per raw log line. This alone is a ~1000x reduction in
LLM call volume versus a naive "LLM sees every event" design.

Further cost/latency controls as volume grows:
- **Bounded evidence per call** (`LLM_MAX_EVIDENCE_ITEMS`) keeps
  per-call token cost roughly constant regardless of case complexity.
- **Cache/dedupe repeat triage requests**: if the same case is
  re-triaged without materially new evidence (e.g. a UI refresh),
  serve the cached `TriageReport` rather than re-calling the LLM — a
  Redis-backed cache keyed on `(case_id, evidence_hash)` is a natural
  fit given Redis is already in the stack.
- **Tiered model selection**: use a cheaper/faster model for
  low-severity cases and reserve the most capable model for
  high-severity/critical cases — `LLM_MODEL` is already
  environment-configurable per deployment; extending it to a per-request
  tier selection based on `Case.severity` is a small change to
  `llm_triage`.
- **Async, non-blocking triage**: triage requests should not block the
  detection→alert path; `llm_triage` is already architecturally
  separate (its own consumer group / independent service) so a slow or
  rate-limited LLM provider degrades triage latency, never ingestion or
  detection throughput.
- **Batch off-peak triage**: for lower-priority cases, defer LLM triage
  to a batched/off-peak job rather than synchronous on-open, trading
  latency for cost during high-volume periods.

## Reliability targets (SLOs)

| Stage | Target (indicative — tune per environment) |
|---|---|
| Ingestion availability | 99.9% (HPA min 2 replicas, no single point of failure once Kafka is clustered) |
| Ingestion → enriched event latency (p95) | < 30s at steady state, < 2min during peak burst |
| Detection scoring latency (p95) | < 5s per event batch |
| Graph write latency (p95) | < 500ms per upsert batch |
| Case/alert query latency (p95, UI) | < 300ms |
| LLM triage latency (p95) | < 15s (explicitly decoupled from ingestion SLOs above) |
| Analyst UI availability | 99.9% |

These targets should be codified as Prometheus alerting rules once an
Alertmanager is deployed (`infra/prometheus/prometheus.yml` already
reserves an `alerting.alertmanagers` block for this) — track burn-rate
alerts on the latency histograms already exposed by every service
(`aegis_*_latency_seconds`).

## Summary: what changes, what doesn't

| Layer | MVP (this repo) | Production at 100M/day |
|---|---|---|
| Streaming | 1-broker Redpanda, default partitions | 3-5 broker cluster, 24-48 partitions/topic, tenant/entity-keyed |
| Stateless services | Deployment + CPU-based HPA | Same, + KEDA lag-based scaling |
| Graph store | 1-node Neo4j Community | Causal Cluster / AuraDB, read replicas, batched writes |
| Search store | 1-node OpenSearch | Multi-node hot/warm/cold tiers with ISM |
| Relational store | 1-instance Postgres | Managed Postgres + read replicas, partitioned audit log |
| LLM | Same service, same evidence-bounding | + caching, tiered model selection, batch off-peak triage |
| Application code / service contracts | — | **Unchanged** — this is the point of ADR 0005 |
