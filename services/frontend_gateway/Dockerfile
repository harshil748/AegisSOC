FROM python:3.11-slim AS base
WORKDIR /app
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1

RUN apt-get update && apt-get install -y --no-install-recommends curl \
    && rm -rf /var/lib/apt/lists/*

COPY packages/common /app/packages/common
RUN pip install -e /app/packages/common

COPY services/frontend_gateway/requirements.txt /app/requirements.txt
RUN pip install -r /app/requirements.txt

# ---------------------------------------------------------------------------
# Bundle every sibling service's <name>_core business-logic package. This is
# what makes AEGIS_SYNC_MODE=true's in-process demo pipeline
# (POST /api/demo/run-scenario, gateway_core/demo_pipeline.py) and
# in-process BFF reads (gateway_core/reads.py) work with zero Kafka/
# Postgres/Neo4j: the gateway calls these modules directly instead of
# making an HTTP call to a running sibling container. In async/proxy-only
# deployments these packages are simply never imported
# (see gateway_core/inprocess.py's lazy import).
# ---------------------------------------------------------------------------
COPY services/ingestion/ingestion_core /app/ingestion_core
COPY services/normalization/normalization_core /app/normalization_core
COPY services/enrichment/enrichment_core /app/enrichment_core
COPY services/graph_builder/graph_core /app/graph_core
COPY services/detection/detection_core /app/detection_core
COPY services/case_management/case_core /app/case_core
COPY services/llm_triage/triage_core /app/triage_core
COPY services/response_policy/policy_core /app/policy_core
COPY services/approval/approval_core /app/approval_core
COPY services/audit/audit_core /app/audit_core

# Sigma rules, demo scenarios, MITRE/threat-intel/asset-criticality seed
# data -- read by detection_core, ingestion_core, and enrichment_core at
# runtime via AEGIS_DATA_DIR (default ./data, i.e. /app/data here).
COPY data /app/data

COPY services/frontend_gateway/app /app/app
COPY services/frontend_gateway/gateway_core /app/gateway_core

EXPOSE 8080
HEALTHCHECK --interval=15s --timeout=5s --start-period=20s --retries=5 \
    CMD curl -fs http://localhost:8080/health || exit 1

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8080"]
