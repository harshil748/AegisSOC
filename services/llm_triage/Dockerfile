FROM python:3.11-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /srv
RUN apt-get update && apt-get install -y --no-install-recommends curl \
    && rm -rf /var/lib/apt/lists/*

COPY packages/common /srv/packages/common
RUN pip install --no-cache-dir /srv/packages/common

COPY services/llm_triage/requirements.txt /srv/services/llm_triage/requirements.txt
RUN pip install --no-cache-dir -r /srv/services/llm_triage/requirements.txt

COPY services/llm_triage/triage_core /srv/triage_core
COPY services/llm_triage/app /srv/app

EXPOSE 8007
HEALTHCHECK --interval=15s --timeout=5s --start-period=20s --retries=5 \
    CMD curl -fs http://localhost:8007/health || exit 1

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8007"]
