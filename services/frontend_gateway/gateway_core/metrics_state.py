"""Lightweight in-process counters for the ``/api/metrics`` dashboard snapshot.

These track real activity observed by *this gateway process* since it
started (events run through the sync-mode demo pipeline, triage reports
generated) -- they are not a substitute for a real time-series metrics
backend (Prometheus/Grafana already cover that at ``/metrics`` on every
service), just enough live signal to make the analyst dashboard's summary
tiles reflect actual usage rather than being hardcoded.
"""

from __future__ import annotations

import threading
from dataclasses import dataclass, field
from datetime import datetime, timezone


def _today() -> str:
    return datetime.now(timezone.utc).date().isoformat()


@dataclass
class _Counters:
    lock: threading.Lock = field(default_factory=threading.Lock)
    ingestion_events_total: int = 0
    llm_requests_total: int = 0
    llm_latency_ms_total: float = 0.0
    llm_groundedness_sum: float = 0.0
    started_day: str = field(default_factory=_today)


_state = _Counters()


def record_ingested_events(count: int) -> None:
    with _state.lock:
        _state.ingestion_events_total += count


def record_triage_report(*, latency_ms: float, groundedness_score: float) -> None:
    with _state.lock:
        _state.llm_requests_total += 1
        _state.llm_latency_ms_total += latency_ms
        _state.llm_groundedness_sum += groundedness_score


def snapshot() -> dict:
    with _state.lock:
        requests = _state.llm_requests_total
        return {
            "ingestion_events_total": _state.ingestion_events_total,
            "llm_requests_total": requests,
            "llm_avg_latency_ms": (_state.llm_latency_ms_total / requests) if requests else 0.0,
            "llm_groundedness_avg": (_state.llm_groundedness_sum / requests) if requests else 0.0,
        }
