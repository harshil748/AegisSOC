FROM python:3.11-slim AS base
WORKDIR /app
ENV PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

RUN apt-get update && apt-get install -y --no-install-recommends curl \
    && rm -rf /var/lib/apt/lists/*

COPY packages/common /app/packages/common
RUN pip install -e /app/packages/common

COPY services/approval/requirements.txt /app/requirements.txt
RUN pip install -r /app/requirements.txt

COPY services/approval/approval_core /app/approval_core
COPY services/approval/app /app/app

EXPOSE 8009
HEALTHCHECK --interval=15s --timeout=5s --start-period=20s --retries=5 \
    CMD curl -fs http://localhost:8009/health || exit 1

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8009"]
