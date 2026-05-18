-- Incremental schema fixes for case_management (safe to re-run).
ALTER TABLE cases ADD COLUMN IF NOT EXISTS cluster_id TEXT;
CREATE INDEX IF NOT EXISTS idx_cases_cluster_id ON cases (cluster_id);

CREATE TABLE IF NOT EXISTS alerts_landed (
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

CREATE INDEX IF NOT EXISTS idx_alerts_landed_cluster ON alerts_landed (cluster_id);
CREATE INDEX IF NOT EXISTS idx_alerts_landed_case ON alerts_landed (case_id);
