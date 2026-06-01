"""Multi-event correlation engine for Sigma ``correlation`` blocks.

Maintains a per-rule, per-group sliding window of recent matching events and
evaluates ``threshold`` (raw count) and ``distinct_count`` (cardinality of a
field) correlation types, mirroring common Sigma aggregation semantics.
"""

from __future__ import annotations

from collections import defaultdict, deque
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from aegis_common.schema.events import CanonicalEvent


@dataclass
class WindowEntry:
    timestamp: datetime
    event_id: str
    group_values: tuple
    field_value: Any


class CorrelationEngine:
    def __init__(self) -> None:
        self._windows: dict[str, deque[WindowEntry]] = defaultdict(deque)

    @staticmethod
    def _group_key(rule_id: str, group_values: tuple) -> str:
        return f"{rule_id}::{group_values}"

    def _prune(self, key: str, window_seconds: int, now: datetime) -> None:
        window = self._windows[key]
        while window and (now - window[0].timestamp).total_seconds() > window_seconds:
            window.popleft()

    def evaluate(
        self, rule: dict[str, Any], event: CanonicalEvent
    ) -> tuple[bool, dict[str, Any]]:
        correlation = rule.get("correlation")
        if not correlation:
            return False, {}

        group_by = correlation.get("group_by", [])
        group_values = tuple(getattr(event, g, None) for g in group_by)
        key = self._group_key(rule.get("id", "unknown"), group_values)
        window_seconds = correlation.get("window_seconds", 300)

        distinct_field = correlation.get("distinct_field")
        field_value = getattr(event, distinct_field, None) if distinct_field else None

        entry = WindowEntry(
            timestamp=event.timestamp,
            event_id=event.event_id,
            group_values=group_values,
            field_value=field_value,
        )
        window = self._windows[key]
        window.append(entry)
        self._prune(key, window_seconds, event.timestamp)

        corr_type = correlation.get("type")
        if corr_type == "threshold":
            min_count = correlation.get("min_count", 1)
            count = len(window)
            matched = count >= min_count
            evidence = {"type": "threshold", "count": count, "min_count": min_count, "window_seconds": window_seconds}
        elif corr_type == "distinct_count":
            min_distinct = correlation.get("min_distinct", 1)
            distinct_values = {e.field_value for e in window if e.field_value is not None}
            matched = len(distinct_values) >= min_distinct
            evidence = {
                "type": "distinct_count",
                "distinct_count": len(distinct_values),
                "min_distinct": min_distinct,
                "values": list(distinct_values),
                "window_seconds": window_seconds,
            }
        else:
            matched = False
            evidence = {}

        if matched:
            evidence["event_ids"] = [e.event_id for e in window]
        return matched, evidence


_engine: CorrelationEngine | None = None


def get_engine() -> CorrelationEngine:
    global _engine
    if _engine is None:
        _engine = CorrelationEngine()
    return _engine
