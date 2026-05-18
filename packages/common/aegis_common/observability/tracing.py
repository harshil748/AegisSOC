"""Lightweight OpenTelemetry-style tracing stub.

A full OTel SDK wiring is out of scope for the demo box, but every service
calls through this shim so swapping in real OTel exporters later is a
one-file change. When ``OTEL_ENDPOINT`` is unset (the default), spans are
recorded as structured log lines only.
"""

from __future__ import annotations

import contextlib
import logging
import os
import time
import uuid
from typing import Iterator

logger = logging.getLogger("aegis.tracing")


class _NoopTracer:
    def __init__(self, service_name: str) -> None:
        self.service_name = service_name

    @contextlib.contextmanager
    def start_span(self, name: str, **attributes: object) -> Iterator[dict]:
        span_id = uuid.uuid4().hex[:16]
        start = time.perf_counter()
        span = {"span_id": span_id, "name": name, "attributes": attributes}
        try:
            yield span
        finally:
            duration_ms = (time.perf_counter() - start) * 1000
            endpoint = os.getenv("OTEL_ENDPOINT")
            logger.debug(
                "span service=%s name=%s span_id=%s duration_ms=%.2f exported=%s attrs=%s",
                self.service_name,
                name,
                span_id,
                duration_ms,
                bool(endpoint),
                attributes,
            )


_tracers: dict[str, _NoopTracer] = {}


def get_tracer(service_name: str) -> _NoopTracer:
    if service_name not in _tracers:
        _tracers[service_name] = _NoopTracer(service_name)
    return _tracers[service_name]


def trace_span(service_name: str, name: str, **attributes: object):
    return get_tracer(service_name).start_span(name, **attributes)
