"""Normalization pipeline: raw envelope -> CanonicalEvent."""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Any

from aegis_common.schema.events import (
    CanonicalEvent,
    Provenance,
    resolve_telemetry_source,
)
from aegis_common.utils.helpers import utcnow

from normalization_core.parsers import get_parser, normalize_timestamp

logger = logging.getLogger("aegis.normalization")


class NormalizationError(Exception):
    def __init__(self, reason: str, raw: Any) -> None:
        super().__init__(reason)
        self.reason = reason
        self.raw = raw


def normalize_raw_message(message: dict[str, Any]) -> CanonicalEvent:
    """Convert a raw ingestion envelope dict into a CanonicalEvent.

    ``message`` matches the shape produced by ``RawEnvelope.model_dump()``:
    ``{event_id, tenant_id, source, timestamp, received_at, payload}``.
    """

    source_value = message.get("source")
    payload = message.get("payload") or {}
    tenant_id = message.get("tenant_id", "default")

    if not source_value:
        raise NormalizationError("missing_source", message)

    source_enum = resolve_telemetry_source(source_value)
    parser = get_parser(source_enum.value)
    timestamp = normalize_timestamp(message.get("timestamp"))

    try:
        event = parser(payload, timestamp, tenant_id)
    except Exception as exc:  # defensive: never let one bad record kill the consumer
        raise NormalizationError(f"parser_error: {exc}", message) from exc

    event.event_id = message.get("event_id") or event.event_id
    event.ingested_at = utcnow()
    event.provenance = Provenance(
        raw_event_id=event.event_id,
        topic="aegis.raw.events",
        source=source_enum,
        ingested_at=event.ingested_at,
    )
    return event


def batch_normalize(messages: list[dict[str, Any]]) -> tuple[list[CanonicalEvent], list[NormalizationError]]:
    events: list[CanonicalEvent] = []
    errors: list[NormalizationError] = []
    for message in messages:
        try:
            events.append(normalize_raw_message(message))
        except NormalizationError as exc:
            logger.warning("normalization_failed reason=%s", exc.reason)
            errors.append(exc)
    return events, errors
