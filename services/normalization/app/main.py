"""AegisSOC Normalization Service.

Consumes raw multi-source telemetry, applies per-source parsers to produce
CanonicalEvent records, and publishes to the normalized-events stream.
Also exposes a synchronous REST endpoint for direct use by the demo
orchestrator and for services/tests that want to normalize without going
through the bus.
"""

from __future__ import annotations

import asyncio
import logging
from contextlib import asynccontextmanager

from fastapi import Body, FastAPI, HTTPException

from aegis_common.config import Settings, TOPIC_NORMALIZED, TOPIC_RAW_DLQ, TOPIC_RAW_EVENTS
from aegis_common.kafka.consumer import AegisConsumer
from aegis_common.kafka.producer import AegisProducer
from aegis_common.observability import EVENTS_PROCESSED, QUEUE_LAG
from aegis_common.schema.events import CanonicalEvent
from aegis_common.service import create_service_app

from normalization_core.normalize import NormalizationError, normalize_raw_message

settings = Settings()
logger = logging.getLogger("aegis.normalization")

SERVICE_NAME = "normalization"
_state: dict = {}


async def _handle_message(message: dict) -> None:
    producer: AegisProducer = _state["producer"]
    try:
        event = normalize_raw_message(message)
    except NormalizationError as exc:
        EVENTS_PROCESSED.labels(service=SERVICE_NAME, stage="normalize", outcome="dead_lettered").inc()
        await producer.send_dlq(TOPIC_RAW_DLQ, TOPIC_RAW_EVENTS, exc.raw, exc.reason)
        return
    EVENTS_PROCESSED.labels(service=SERVICE_NAME, stage="normalize", outcome="normalized").inc()
    await producer.send(TOPIC_NORMALIZED, event.model_dump(mode="json"), key=event.event_id)


async def _consumer_loop(stop_event: asyncio.Event) -> None:
    consumer: AegisConsumer = _state["consumer"]
    while not stop_event.is_set():
        try:
            batch = await consumer.poll_batch()
            for message in batch:
                await _handle_message(message)
            if not batch:
                await asyncio.sleep(1.0)
            QUEUE_LAG.labels(service=SERVICE_NAME, topic=TOPIC_RAW_EVENTS, group=SERVICE_NAME).set(
                consumer.lag()
            )
        except Exception:
            logger.exception("consumer_loop_error")
            await asyncio.sleep(1.0)


@asynccontextmanager
async def lifespan(app: FastAPI):
    producer = AegisProducer(bootstrap_servers=settings.kafka_bootstrap, client_id=SERVICE_NAME)
    await producer.start()
    consumer = AegisConsumer(TOPIC_RAW_EVENTS, settings.kafka_bootstrap, group_id=SERVICE_NAME)
    await consumer.start()
    _state["producer"] = producer
    _state["consumer"] = consumer

    stop_event = asyncio.Event()
    task = asyncio.create_task(_consumer_loop(stop_event))
    _state["task"] = task
    _state["stop_event"] = stop_event
    logger.info("normalization_service_started")
    yield
    stop_event.set()
    await asyncio.sleep(0)
    task.cancel()
    await producer.stop()
    await consumer.stop()


app = create_service_app(
    service_name=SERVICE_NAME,
    description="Per-source parsing and canonical event normalization.",
    lifespan=lifespan,
)


@app.post("/api/v1/normalize", response_model=CanonicalEvent, tags=["normalize"])
async def normalize_one(message: dict = Body(...)) -> CanonicalEvent:
    try:
        return normalize_raw_message(message)
    except NormalizationError as exc:
        raise HTTPException(status_code=422, detail=exc.reason) from exc


@app.get("/api/v1/stats", tags=["ops"])
async def stats() -> dict:
    consumer: AegisConsumer | None = _state.get("consumer")
    return {"consumer_lag": consumer.lag() if consumer else None}
