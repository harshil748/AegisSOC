"""Temporal sequence features per entity (rolling windows, no external deps)."""

from __future__ import annotations

from collections import defaultdict, deque
from dataclasses import dataclass
from datetime import datetime

from aegis_common.schema.events import CanonicalEvent

WINDOW_SECONDS = 300


@dataclass
class _Entry:
    timestamp: datetime
    event_type: str
    technique_ids: tuple


class TemporalFeatureTracker:
    def __init__(self, window_seconds: int = WINDOW_SECONDS) -> None:
        self.window_seconds = window_seconds
        self._by_host: dict[str, deque[_Entry]] = defaultdict(deque)
        self._first_seen: dict[str, datetime] = {}

    def _prune(self, host: str, now: datetime) -> None:
        window = self._by_host[host]
        while window and (now - window[0].timestamp).total_seconds() > self.window_seconds:
            window.popleft()

    def observe(self, event: CanonicalEvent) -> dict:
        host = event.host or event.user or "unknown"
        self._first_seen.setdefault(host, event.timestamp)
        window = self._by_host[host]
        window.append(
            _Entry(event.timestamp, event.event_type, tuple(event.technique_ids))
        )
        self._prune(host, event.timestamp)

        distinct_event_types = {e.event_type for e in window}
        distinct_techniques: set[str] = set()
        for e in window:
            distinct_techniques.update(e.technique_ids)

        return {
            "entity": host,
            "event_count_window": len(window),
            "distinct_event_types_window": len(distinct_event_types),
            "distinct_techniques_window": len(distinct_techniques),
            "time_since_first_seen_seconds": (
                event.timestamp - self._first_seen[host]
            ).total_seconds(),
            "window_seconds": self.window_seconds,
        }
