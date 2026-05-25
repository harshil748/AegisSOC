FROM python:3.11-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /srv

COPY packages/common /srv/packages/common
RUN pip install --no-cache-dir /srv/packages/common

COPY services/enrichment/requirements.txt /srv/services/enrichment/requirements.txt
RUN pip install --no-cache-dir -r /srv/services/enrichment/requirements.txt

COPY services/enrichment/enrichment_core /srv/enrichment_core
COPY services/enrichment/app /srv/app
COPY data /srv/data

EXPOSE 8003

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8003"]
