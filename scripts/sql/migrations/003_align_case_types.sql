-- Align case_management tables with SQLAlchemy String PKs (TEXT), not UUID.
-- Safe for local demo volumes; run against the aegis DB.

ALTER TABLE IF EXISTS case_feedback DROP CONSTRAINT IF EXISTS case_feedback_case_id_fkey;
ALTER TABLE IF EXISTS actions DROP CONSTRAINT IF EXISTS actions_case_id_fkey;
ALTER TABLE IF EXISTS approvals DROP CONSTRAINT IF EXISTS approvals_case_id_fkey;
ALTER TABLE IF EXISTS approvals DROP CONSTRAINT IF EXISTS approvals_action_id_fkey;

DROP TABLE IF EXISTS case_feedback CASCADE;
DROP TABLE IF EXISTS approvals CASCADE;
DROP TABLE IF EXISTS actions CASCADE;
DROP TABLE IF EXISTS alerts_landed CASCADE;
DROP TABLE IF EXISTS cases CASCADE;

CREATE TABLE cases (
    case_id         TEXT PRIMARY KEY,
    tenant_id       TEXT NOT NULL DEFAULT 'default',
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
    cluster_id      TEXT,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX idx_cases_tenant_status ON cases (tenant_id, status);
CREATE INDEX idx_cases_cluster_id ON cases (cluster_id);

CREATE TABLE case_feedback (
    feedback_id     TEXT PRIMARY KEY,
    case_id         TEXT NOT NULL REFERENCES cases(case_id),
    analyst         TEXT NOT NULL,
    verdict         TEXT NOT NULL,
    comment         TEXT,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE alerts_landed (
    alert_id         TEXT PRIMARY KEY,
    tenant_id        TEXT NOT NULL DEFAULT 'default',
    cluster_id       TEXT,
    case_id          TEXT,
    title            TEXT NOT NULL,
    severity         TEXT NOT NULL,
    calibrated_score DOUBLE PRECISION NOT NULL DEFAULT 0,
    payload          JSONB NOT NULL DEFAULT '{}',
    created_at       TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at       TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX idx_alerts_landed_cluster ON alerts_landed (cluster_id);
CREATE INDEX idx_alerts_landed_case ON alerts_landed (case_id);
