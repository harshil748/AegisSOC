# ADR 0001: Use a Graph Store (Neo4j) in Addition to a Search Store (OpenSearch)

## Status
Accepted

## Context
AegisSOC needs two very different query patterns over the same underlying
security data:

1. **Investigation search**: "find all events matching X in the last N
   days", full-text search over raw/enriched event fields, fast faceted
   filtering across entities and cases, and dashboards over alert volume.
2. **Relationship reasoning**: "what did this user touch after
   authenticating to this host?", "is this IP part of a chain that also
   touched a domain controller?", multi-hop traversal to reconstruct an
   attack path, and incident memory that persists an entity's history
   across many unrelated alerts over weeks or months.

A single storage engine is poor at both. Document/search stores
(OpenSearch/Elasticsearch) are excellent at (1) — inverted indices, BM25
ranking, aggregations — but multi-hop relationship traversal in a
document store means either enormous fan-out queries or manually
maintained adjacency lists that don't scale past 2-3 hops. Graph
databases are excellent at (2) — index-free adjacency makes k-hop
traversal cheap — but are comparatively weak at full-text search and
large-scale analytical aggregation.

## Decision
Run **both**, each doing what it is good at, connected by shared entity
IDs (`entity_id(node_type, key, tenant_id)` from
`packages/common/aegis_common/utils/helpers.py`):

- **Neo4j** is the system of record for the canonical security graph:
  entities (User, Host, Process, File, IP, Domain, URL, Hash,
  RegistryKey, Email, CloudResource, K8sWorkload, AttackTechnique,
  Incident) and typed edges (`logged_in_to`, `spawned`, `executed`,
  `connected_to`, `resolved_to`, `mapped_to_technique`, etc). Every
  node/edge carries `first_seen`/`last_seen`/`count`/`confidence`/
  `sources`/`provenance_ids` so the graph itself is an audit trail of how
  an entity's risk picture was built over time. Detection's graph feature
  extraction and attack-path reconstruction run here.
- **OpenSearch** is the system of record for search/investigation:
  normalized+enriched events, alerts, and case documents, indexed for
  full-text search, faceted filtering, and the analyst dashboard's alert
  queue. It is also the natural home for time-series-heavy queries
  (volume over time, top-k prioritization) that a graph engine handles
  poorly.
- **Postgres** remains the system of record for workflow state (cases,
  approvals, users, audit) that needs relational integrity and
  transactions — see ADR context in `docs/ARCHITECTURE.md`.

The graph_builder service is the only writer to Neo4j; detection reads
graph features from it but never writes back into the ingestion path
synchronously (avoiding write contention on the hot path).

## Consequences
- Two storage engines to operate, back up, and monitor instead of one —
  accepted complexity cost, mitigated by keeping both eventually
  consistent from the same Kafka topic (`aegis.enriched.events`) rather
  than requiring synchronous dual writes.
- Entity resolution must be consistent across both stores; `entity_id()`
  is deterministic (stable hash of normalized key + tenant) specifically
  so the same logical entity gets the same ID in Neo4j nodes and
  OpenSearch documents without a lookup service.
- Graph writes are the most likely bottleneck at scale (see
  `docs/SCALABILITY.md`); OpenSearch and Postgres both scale
  horizontally more conventionally (sharding/read replicas).

## Alternatives considered
- **OpenSearch only, with a denormalized "related entities" field**:
  rejected — multi-hop attack-path queries degrade badly past 2 hops and
  duplicate relationship data across every event that references it.
- **Neo4j only**: rejected — full-text search and large aggregations over
  millions of daily events are not Neo4j's strength, and the analyst
  dashboard's alert queue needs sub-second faceted search.
- **Single relational store (Postgres) with recursive CTEs for graph
  traversal and `pg_trgm`/`tsvector` for search**: rejected for the MVP —
  viable at small scale but recursive CTE traversal cost grows quickly
  with fan-out, and it would require reimplementing much of what Neo4j
  and OpenSearch provide out of the box. Revisit only if operating three
  stores proves untenable for a much smaller deployment profile.
