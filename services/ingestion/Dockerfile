FROM python:3.11-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /srv

# Shared library first (better layer caching across services)
COPY packages/common /srv/packages/common
RUN pip install --no-cache-dir /srv/packages/common

COPY services/ingestion/requirements.txt /srv/services/ingestion/requirements.txt
RUN pip install --no-cache-dir -r /srv/services/ingestion/requirements.txt

COPY services/ingestion/ingestion_core /srv/ingestion_core
COPY services/ingestion/app /srv/app
COPY data /srv/data

EXPOSE 8001

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8001"]
