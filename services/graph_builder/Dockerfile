FROM python:3.11-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /srv

COPY packages/common /srv/packages/common
RUN pip install --no-cache-dir /srv/packages/common

COPY services/graph_builder/requirements.txt /srv/services/graph_builder/requirements.txt
RUN pip install --no-cache-dir -r /srv/services/graph_builder/requirements.txt

COPY services/graph_builder/graph_core /srv/graph_core
COPY services/graph_builder/app /srv/app
COPY data /srv/data

EXPOSE 8004

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8004"]
