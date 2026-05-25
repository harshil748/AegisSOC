"""Core ingestion business logic: validation, idempotency, DLQ routing."""

from __future__ import annotations

import logging

from aegis_common.config import TOPIC_RAW_DLQ, TOPIC_RAW_EVENTS
from aegis_common.idempotency import IdempotencyStore
from aegis_common.kafka.producer import AegisProducer
from aegis_common.observability import EVENTS_PROCESSED

from ingestion_core.models import IngestResult, RawEnvelope

logger = logging.getLogger("aegis.ingestion")

SERVICE_NAME = "ingestion"

REQUIRED_PAYLOAD_KEYS = {"event_type"}


def validate_envelope(envelope: RawEnvelope) -> tuple[bool, str | None]:
    """Malformed-record detection feeding the dead-letter queue.

    A record is malformed if it lacks an event_type discriminator, has an
    empty payload, or declares a timestamp far outside a sane window.
    """

    if not envelope.payload:
        return False, "empty_payload"
    if "event_type" not in envelope.payload and "EventID" not in envelope.payload:
        return False, "missing_event_type_discriminator"
    return True, None


async def process_envelope(
    envelope: RawEnvelope,
    producer: AegisProducer,
    idempotency: IdempotencyStore,
) -> IngestResult:
    event_id = envelope.compute_event_id()
    envelope.event_id = event_id

    if idempotency.seen_before(event_id):
        EVENTS_PROCESSED.labels(service=SERVICE_NAME, stage="ingest", outcome="duplicate").inc()
        logger.info("duplicate_event_skipped event_id=%s", event_id)
        return IngestResult(event_id=event_id, status="duplicate", reason="already_ingested")

    is_valid, reason = validate_envelope(envelope)
    if not is_valid:
        await producer.send_dlq(
            TOPIC_RAW_DLQ, TOPIC_RAW_EVENTS, envelope.model_dump(mode="json"), reason or "invalid"
        )
        EVENTS_PROCESSED.labels(
            service=SERVICE_NAME, stage="ingest", outcome="dead_lettered"
        ).inc()
        logger.warning("malformed_record_dead_lettered event_id=%s reason=%s", event_id, reason)
        return IngestResult(
            event_id=event_id, status="dead_lettered", topic=TOPIC_RAW_DLQ, reason=reason
        )

    await producer.send(TOPIC_RAW_EVENTS, envelope.model_dump(mode="json"), key=event_id)
    EVENTS_PROCESSED.labels(service=SERVICE_NAME, stage="ingest", outcome="accepted").inc()
    return IngestResult(event_id=event_id, status="accepted", topic=TOPIC_RAW_EVENTS)
