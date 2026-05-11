# ADR 0005: Scale Path — How the Architecture Scales From MVP to Production

## Status
Accepted

## Context
The target design assumptions are 100M logs/day, ~100K alerts/day,
thousands of suspicious clusters/day, hundreds of analyst investigations,
and strict triage/enrichment latency SLOs. The MVP, by design (see the
"Recommended MVP boundary" in `prompt.md`), runs a small subset of
sources through a single-node docker-compose stack. The architecture
must be chosen so that the MVP is not a dead end — every component that
is a single instance today has a documented, non-rearchitecture path to
horizontal scale.

This ADR records the decision to design every layer for horizontal
scale-out from the start, even though the MVP deploys single instances of
most infrastructure, rather than treating scale as a later rewrite.

## Decision
Each layer's scale path is fixed at design time, detailed fully in
`docs/SCALABILITY.md`, and summarized here as the architectural decision:

- **Ingestion/streaming**: Kafka-compatible topics from day one (Redpanda
  locally, Kafka/MSK/Confluent in production) with topic partitioning
  and consumer groups as the scaling primitive — not a queue that would
  need replacing later. `TOPIC_RAW_EVENTS`, `TOPIC_NORMALIZED`, etc. are
  already named and typed in `packages/common/aegis_common/config.py`.
- **Stateless services** (ingestion, normalization, enrichment,
  detection, frontend_gateway) are horizontally scaled via Kubernetes
  HPA (`infra/k8s/hpa.yaml`) keyed on CPU today, with a documented
  upgrade to Kafka-lag-based scaling (KEDA) as consumer lag becomes the
  more accurate scaling signal than CPU.
- **Graph store**: Neo4j Community single instance in the MVP; the
  decision to isolate all graph writes behind `graph_builder` (ADR 0001)
  means the migration to a Causal Cluster / read-replica topology is a
  deployment change, not an application rewrite.
- **Search store**: OpenSearch single-node in the MVP; index templates
  and ISM (index state management) policies are designed against
  multi-node/hot-warm-cold tiering from the start (see
  `docs/SCALABILITY.md` "search tiers"), so growing the cluster is a
  capacity change, not a schema change.
- **Relational store**: Postgres single instance in the MVP; the audit
  table is append-only by construction (ADR/behavior in `audit` service)
  specifically so it can later be moved to a write-optimized/partitioned
  table or a separate WORM store without touching write-path code.
- **LLM cost/latency**: `llm_triage` is architecturally decoupled from
  the ingestion hot path (ADR 0002) — it is only ever invoked
  synchronously for a bounded, already-alerted case, never per raw
  event, so LLM cost scales with alert volume (~100K/day) and analyst
  investigation volume (hundreds/day), not with log volume
  (100M/day) — a ~1000x reduction in LLM call volume by construction.
- **Deployment target**: docker-compose for local dev, Kubernetes
  manifests (`infra/k8s/`) and a Helm chart (`infra/helm/aegis/`) for
  every environment beyond a laptop, so "MVP to production" is a
  `docker compose up` → `helm install` transition using the *same*
  container images and service contracts, not a re-platforming.

## Consequences
- Every service ships with `/health`, `/ready`, and `/metrics` from the
  first commit (see each `services/*/app/main.py`) because horizontal
  scaling and rolling deploys require them — retrofitting observability
  after the fact is far more expensive than building it in.
- Kafka topic naming/partitioning decisions made now (single partition
  per topic in the MVP) are documented as needing revisiting before
  production load (`docs/SCALABILITY.md` gives concrete partition-count
  guidance) rather than left implicit.
- The MVP intentionally under-provisions (single-node everything) to
  keep local dev cheap and fast to start, accepting that a from-scratch
  load test against docker-compose will not reflect production
  throughput — `tests/load/` and `make load-test` are explicitly scoped
  as functional/regression checks, not capacity benchmarks.

## Alternatives considered
- **Build the MVP without regard for scale, rewrite later**: rejected —
  the project brief explicitly requires "every major design choice"
  to be "extensible to real SOC scale"; retrofitting partitioning,
  idempotent consumers, and clustering into a system built without them
  in mind is materially more expensive than designing for it up front,
  even if the MVP itself runs on a single node.
- **Design for a specific target scale (e.g. exactly 100M/day) and
  hard-code capacity assumptions**: rejected — the scale path is kept as
  a set of documented, parameterized levers (partition count, replica
  count, tiering thresholds) rather than fixed constants, since real
  deployments will land at many different scales.
