FROM python:3.11-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /srv

COPY packages/common /srv/packages/common
RUN pip install --no-cache-dir /srv/packages/common

COPY services/normalization/requirements.txt /srv/services/normalization/requirements.txt
RUN pip install --no-cache-dir -r /srv/services/normalization/requirements.txt

COPY services/normalization/normalization_core /srv/normalization_core
COPY services/normalization/app /srv/app
COPY data /srv/data

EXPOSE 8002

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8002"]
