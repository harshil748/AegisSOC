# AegisSOC Security

This document is the controls reference for AegisSOC. See
`docs/threat-model/THREAT_MODEL.md` for the STRIDE analysis these
controls exist to address, and the ADRs in `docs/adr/` for why several
of these boundaries are architectural rather than merely policy.

## RBAC

Two roles in the MVP, carried as a `role` claim in the JWT issued by
`frontend_gateway`'s `/api/v1/auth/login`:

| Role | Can do |
|---|---|
| `analyst` | View/create/update cases, request triage reports, request approvals, view own audit-relevant actions, submit feedback |
| `admin` | Everything `analyst` can, plus: decide approvals (`POST /api/v1/approvals/{id}/decide`), query the audit trail (`GET /api/v1/audit`) |

Enforcement points:
- `frontend_gateway._require_admin()` gates admin-only routes at the
  edge (`approvals/*/decide`, `audit/*`) — see
  `services/frontend_gateway/app/main.py`.
- Each internal service should **independently** re-check role/tenant
  scoping rather than trust the gateway as the sole enforcement point
  (defense in depth) once real JWT verification replaces the current
  stub — tracked as a hardening TODO in `services/frontend_gateway/app/main.py`.
- Role is a server-issued JWT claim set at login from the user record in
  Postgres (`scripts/sql/001_init.sql` `users.role`), never a
  client-supplied field.

Extending RBAC beyond two roles (e.g. `viewer`, `tenant_admin`,
`playbook_editor`) is a straightforward addition to the `role` enum and
the `_require_*` helper pattern already established in the gateway.

## Secrets management

- **Local dev**: `.env` (git-ignored, copy from `.env.example`) feeds
  `docker-compose.yml` via `${VAR:-default}` interpolation. Never commit
  a real `.env`.
- **Kubernetes**: secrets are injected via `envFrom: secretRef` (see
  `infra/k8s/02-secrets.example.yaml`), never baked into images or
  ConfigMaps. `infra/helm/aegis/values.yaml`'s `secrets.create` defaults
  to `false` — production installs should provision `aegis-secrets` out
  of band (Vault, AWS/GCP/Azure secret manager via the External Secrets
  Operator, or sealed-secrets) rather than rendering a static `Secret`
  from Helm values.
- **What's a secret**: DB passwords/DSNs, Neo4j password, JWT signing
  secret, LLM API keys, Grafana admin password, and any threat-intel
  feed API keys (OpenCTI/MISP/VirusTotal-style). None of these belong in
  a ConfigMap, image layer, log line, or error response.
- **Rotation**: JWT secret rotation invalidates all outstanding tokens
  (`access_token_expire_minutes` bounds the blast radius to at most that
  window); DB/Neo4j password rotation should go through your secret
  manager's rotation hook plus a rolling restart of dependent
  deployments.

## Encryption

- **In transit**: TLS terminates at the ingress/load balancer in
  production (`infra/k8s/21-frontend.yaml`'s Ingress + cert-manager);
  internal service-to-service traffic runs over the cluster's private
  network. For stricter environments, add a service mesh (Linkerd/Istio)
  for mTLS between services — not required for the MVP's threat model
  but a natural addition alongside stronger tenant isolation
  (`docs/threat-model/THREAT_MODEL.md` §4).
- **At rest**: rely on the underlying platform's encryption-at-rest for
  Postgres/Neo4j/OpenSearch volumes (cloud-provider EBS/PD encryption or
  equivalent) plus Kubernetes Secret encryption at rest (enable
  `EncryptionConfiguration` for the `etcd` API server in production
  clusters — a cluster-operator responsibility, not application code).

## PII handling

- `redact_pii()` (`packages/common/aegis_common/utils/helpers.py`)
  redacts email addresses fully and partially masks IPv4 last-octet
  before any text is passed into an LLM prompt or displayed in a
  non-investigation context — IPs are only partially masked (not fully
  redacted) because full IPs frequently have direct investigative value
  and are treated as security data, not personal data, in this context;
  revisit this trade-off per your organization's data-classification
  policy.
- Apply `redact_pii()` (or an equivalent, stronger DLP pass) to any
  free-text field sourced from email bodies, chat, or ticket systems
  before it becomes `EvidenceItem.summary` for LLM consumption — this is
  both a privacy control and part of the prompt-injection-surface
  reduction described below.
- Minimize retention of raw PII-bearing payloads: the object-storage/
  parquet lake tier (long-term raw retention, `object_store_path`) should
  have a documented retention/purge policy per your compliance
  requirements; this repo does not implement automatic purge in the MVP.

## Prompt injection defenses

See `docs/threat-model/THREAT_MODEL.md` §2 for the full threat
enumeration. Concretely, in `services/llm_triage/app/main.py`:

1. **Untrusted-data framing**: every `EvidenceItem` is data the model
   must cite, never an instruction — the system prompt (once wired to a
   real LLM call) must state this explicitly and must not be
   overridable by evidence content.
2. **Pattern-based sanitization**: `_sanitize_evidence()` strips known
   injection markers ("ignore previous instructions", "you are now",
   "system prompt", "disregard the above") before evidence enters the
   prompt, and truncates each item to 2000 characters.
3. **Bounded evidence window**: `LLM_MAX_EVIDENCE_ITEMS` (default 40)
   caps how much untrusted text the model ever sees per request, per
   ADR 0004's "more context is not always better" guidance — also
   shrinks the injection attack surface.
4. **Output validation over trust**: rather than trying to make
   injection detection perfect, every output is validated against
   `evidence_cited` and unsupported claims are stripped — this is the
   actual backstop, since injection detection alone is inherently
   incomplete against a sufficiently creative payload.
5. **No privilege from LLM output**: the LLM's output can never itself
   trigger an action — `response_policy` and `approval` are separate
   services the LLM has no write access to (ADR 0002), so even a fully
   successful injection cannot cause an unapproved action to execute.
6. **Metrics for monitoring drift**: `aegis_llm_prompt_injection_blocked_total`
   and `aegis_llm_unsupported_claims_stripped_total` should be watched
   over time — a sudden spike suggests either an attack campaign or a
   new evasion technique worth adding a pattern/detector for.

## Model output validation and policy checks

Before any `ActionRecommendation` reaches an analyst or an approval
request, it passes through:
- `response_policy`'s fixed `DISRUPTIVE_CLASSES` set — disruptiveness is
  never inferred by an LLM or left to caller-supplied input.
- `dry_run_default=True` on every action — production/live execution
  requires an explicit opt-out plus an approval decision.
- `approval`'s human-in-the-loop gate — see
  `docs/threat-model/THREAT_MODEL.md` §3 for the full bypass analysis.

## Rate limiting and abuse controls

Not yet implemented as a shared middleware in the MVP stubs — tracked
as a required production hardening step:
- Per-source ingestion rate limits (token bucket per API key/source) at
  `ingestion`.
- Per-user request rate limits at `frontend_gateway` (e.g.
  `slowapi`/API-gateway-level throttling) to blunt credential-stuffing
  and approval-queue-flooding attempts (`docs/threat-model/THREAT_MODEL.md` §3.5).
- LLM call rate limits per tenant/user to bound cost exposure from a
  single compromised account.

## Tenant isolation

Logical isolation via `tenant_id` on every record; see
`docs/threat-model/THREAT_MODEL.md` §4 for the full analysis and its
explicit limitation (not hardened for mutually-adversarial tenants
without additional per-tenant infrastructure isolation).

## Security checklist for production deployment

- [ ] Replace demo auth (`_demo_authenticate`) with real user store + bcrypt (passlib is already a dependency) + signed JWTs (PyJWT is already a dependency).
- [ ] Enforce TLS everywhere via ingress + cert-manager (manifests already scaffolded in `infra/k8s/21-frontend.yaml`).
- [ ] Provision `aegis-secrets` via an external secret manager, not a static Kubernetes Secret.
- [ ] Enable dependency/image scanning in CI (`pip-audit`, `npm audit`, Trivy/Grype) — see `docs/threat-model/THREAT_MODEL.md` §5.
- [ ] Add per-source ingestion auth (mTLS or per-source API keys) before exposing `ingestion` outside the cluster network.
- [ ] Add rate limiting at `frontend_gateway` and `ingestion`.
- [ ] Revoke UPDATE/DELETE on `audit_log`/`approvals` tables from the application DB role (see commented `REVOKE` in `scripts/sql/001_init.sql`).
- [ ] Review and tune `redact_pii()` against your organization's actual PII/data-classification policy.
