FROM python:3.11-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /srv

COPY packages/common /srv/packages/common
RUN pip install --no-cache-dir /srv/packages/common

COPY services/detection/requirements.txt /srv/services/detection/requirements.txt
RUN pip install --no-cache-dir -r /srv/services/detection/requirements.txt

COPY services/detection/detection_core /srv/detection_core
COPY services/detection/app /srv/app
COPY data /srv/data

EXPOSE 8005

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8005"]
