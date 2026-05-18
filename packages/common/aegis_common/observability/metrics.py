"""Prometheus metrics shared across services.

Metrics are module-level singletons so any service that imports this module
contributes to the same registry namespace conventions (``aegis_*``).
``instrument_app`` wires request counters/latency histograms into a FastAPI
app and exposes ``/metrics`` in the standard Prometheus text format.
"""

from __future__ import annotations

import time
from typing import Callable

from fastapi import FastAPI, Request, Response
from prometheus_client import (
    CONTENT_TYPE_LATEST,
    Counter,
    Gauge,
    Histogram,
    generate_latest,
)

REQUEST_COUNT = Counter(
    "aegis_http_requests_total",
    "Total HTTP requests",
    ["service", "method", "path", "status"],
)

REQUEST_LATENCY = Histogram(
    "aegis_http_request_latency_seconds",
    "HTTP request latency in seconds",
    ["service", "method", "path"],
)

EVENTS_PROCESSED = Counter(
    "aegis_events_processed_total",
    "Total events processed by a pipeline stage",
    ["service", "stage", "outcome"],
)

QUEUE_LAG = Gauge(
    "aegis_queue_lag",
    "Consumer lag for a topic/group",
    ["service", "topic", "group"],
)

MODEL_LATENCY = Histogram(
    "aegis_model_latency_seconds",
    "Latency of ML/LLM inference calls",
    ["service", "model"],
)

ERRORS_TOTAL = Counter(
    "aegis_errors_total",
    "Total handled errors by category",
    ["service", "category"],
)


def instrument_app(app: FastAPI, service_name: str) -> None:
    @app.middleware("http")
    async def _metrics_middleware(request: Request, call_next: Callable):
        start = time.perf_counter()
        try:
            response = await call_next(request)
        except Exception:
            ERRORS_TOTAL.labels(service=service_name, category="unhandled_exception").inc()
            raise
        elapsed = time.perf_counter() - start
        path = request.url.path
        REQUEST_COUNT.labels(
            service=service_name, method=request.method, path=path, status=response.status_code
        ).inc()
        REQUEST_LATENCY.labels(service=service_name, method=request.method, path=path).observe(
            elapsed
        )
        response.headers["X-Aegis-Service"] = service_name
        return response

    @app.get("/metrics", include_in_schema=False)
    async def metrics() -> Response:
        return Response(content=generate_latest(), media_type=CONTENT_TYPE_LATEST)
