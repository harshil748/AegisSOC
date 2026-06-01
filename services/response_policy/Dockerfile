FROM python:3.11-slim AS base
WORKDIR /app
ENV PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

RUN apt-get update && apt-get install -y --no-install-recommends curl \
    && rm -rf /var/lib/apt/lists/*

COPY packages/common /app/packages/common
RUN pip install -e /app/packages/common

COPY services/response_policy/requirements.txt /app/requirements.txt
RUN pip install -r /app/requirements.txt

COPY services/response_policy/app /app/app
COPY services/response_policy/policy_core /app/policy_core
COPY data /app/data

EXPOSE 8008
HEALTHCHECK --interval=15s --timeout=5s --start-period=20s --retries=5 \
    CMD curl -fs http://localhost:8008/health || exit 1

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8008"]
