"""Observability helpers: Prometheus metrics, structured logs, OTel stubs."""

from aegis_common.observability.metrics import (
    instrument_app,
    REQUEST_COUNT,
    REQUEST_LATENCY,
    EVENTS_PROCESSED,
    QUEUE_LAG,
    MODEL_LATENCY,
    ERRORS_TOTAL,
)
from aegis_common.observability.tracing import get_tracer, trace_span

__all__ = [
    "instrument_app",
    "REQUEST_COUNT",
    "REQUEST_LATENCY",
    "EVENTS_PROCESSED",
    "QUEUE_LAG",
    "MODEL_LATENCY",
    "ERRORS_TOTAL",
    "get_tracer",
    "trace_span",
]
