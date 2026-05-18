-- AegisSOC Postgres schema bootstrap.
-- Applied automatically by the official postgres image on first container
-- start (docker-entrypoint-initdb.d). Services currently use in-memory
-- stores for the MVP stubs; this DDL is the target schema they graduate to.

CREATE TABLE IF NOT EXISTS tenants (
    tenant_id       TEXT PRIMARY KEY,
    name            TEXT NOT NULL,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

INSERT INTO tenants (tenant_id, name) VALUES ('default', 'Default Tenant')
    ON CONFLICT DO NOTHING;

CREATE TABLE IF NOT EXISTS users (
    user_id         UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id       TEXT NOT NULL REFERENCES tenants(tenant_id),
    username        TEXT NOT NULL UNIQUE,
    password_hash   TEXT NOT NULL,
    role            TEXT NOT NULL CHECK (role IN ('analyst', 'admin')),
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS cases (
    case_id         UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id       TEXT NOT NULL REFERENCES tenants(tenant_id),
    title           TEXT NOT NULL,
    status          TEXT NOT NULL DEFAULT 'new',
    severity        TEXT NOT NULL,
    risk_score      DOUBLE PRECISION NOT NULL DEFAULT 0,
    alert_ids       JSONB NOT NULL DEFAULT '[]',
    entity_ids      JSONB NOT NULL DEFAULT '[]',
    technique_ids   JSONB NOT NULL DEFAULT '[]',
    timeline        JSONB NOT NULL DEFAULT '[]',
    attack_story    TEXT,
    assignee        TEXT,
    tags            JSONB NOT NULL DEFAULT '[]',
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_cases_tenant_status ON cases (tenant_id, status);

CREATE TABLE IF NOT EXISTS case_feedback (
    feedback_id     UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    case_id         UUID NOT NULL REFERENCES cases(case_id),
    analyst         TEXT NOT NULL,
    verdict         TEXT NOT NULL CHECK (verdict IN ('true_positive', 'false_positive', 'benign')),
    comment         TEXT,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS actions (
    action_id           UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    case_id             UUID NOT NULL REFERENCES cases(case_id),
    action_class        TEXT NOT NULL,
    disruptive          BOOLEAN NOT NULL DEFAULT false,
    dry_run_default     BOOLEAN NOT NULL DEFAULT true,
    playbook_id         TEXT,
    parameters          JSONB NOT NULL DEFAULT '{}',
    evidence_refs        JSONB NOT NULL DEFAULT '[]',
    confidence          DOUBLE PRECISION NOT NULL DEFAULT 0.7,
    status              TEXT NOT NULL DEFAULT 'pending',
    created_at          TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS approvals (
    approval_id     UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    action_id       UUID NOT NULL REFERENCES actions(action_id),
    case_id         UUID NOT NULL REFERENCES cases(case_id),
    requested_by    TEXT NOT NULL,
    decided_by      TEXT,
    decision        TEXT CHECK (decision IN ('approved', 'rejected')),
    rationale       TEXT,
    dry_run         BOOLEAN NOT NULL DEFAULT true,
    status          TEXT NOT NULL DEFAULT 'pending',
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    decided_at      TIMESTAMPTZ
);

CREATE TABLE IF NOT EXISTS audit_log (
    audit_id        UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id       TEXT NOT NULL REFERENCES tenants(tenant_id),
    actor           TEXT NOT NULL,
    actor_type      TEXT NOT NULL CHECK (actor_type IN ('user', 'system', 'llm', 'service')),
    action          TEXT NOT NULL,
    resource_type   TEXT NOT NULL,
    resource_id     TEXT NOT NULL,
    details         JSONB NOT NULL DEFAULT '{}',
    prompt_hash     TEXT,
    evidence_refs   JSONB NOT NULL DEFAULT '[]',
    timestamp       TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- Append-only guard: revoke UPDATE/DELETE from the application role once
-- provisioned (kept commented for local dev where the app role == owner).
-- REVOKE UPDATE, DELETE ON audit_log FROM aegis_app;

CREATE INDEX IF NOT EXISTS idx_audit_resource ON audit_log (resource_type, resource_id);
CREATE INDEX IF NOT EXISTS idx_audit_actor_type ON audit_log (actor_type);
