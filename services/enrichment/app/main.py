"""AegisSOC Enrichment Service.

Consumes normalized events, applies MITRE ATT&CK tagging, asset criticality
scoring, identity resolution, threat-intel matching, and entity extraction,
then republishes enriched CanonicalEvent records for the graph builder and
detection services.
"""

from __future__ import annotations

import asyncio
import logging
from contextlib import asynccontextmanager

from fastapi import Body, FastAPI

from aegis_common.config import Settings, TOPIC_ENRICHED, TOPIC_NORMALIZED
from aegis_common.kafka.consumer import AegisConsumer
from aegis_common.kafka.producer import AegisProducer
from aegis_common.observability import EVENTS_PROCESSED, QUEUE_LAG
from aegis_common.schema.events import CanonicalEvent
from aegis_common.service import create_service_app

from enrichment_core import intel
from enrichment_core.pipeline import enrich_event

settings = Settings()
logger = logging.getLogger("aegis.enrichment")

SERVICE_NAME = "enrichment"
_state: dict = {}


async def _handle_message(message: dict) -> None:
    producer: AegisProducer = _state["producer"]
    event = CanonicalEvent.model_validate(message)
    enriched = enrich_event(event)
    EVENTS_PROCESSED.labels(service=SERVICE_NAME, stage="enrich", outcome="enriched").inc()
    await producer.send(TOPIC_ENRICHED, enriched.model_dump(mode="json"), key=enriched.event_id)


async def _consumer_loop(stop_event: asyncio.Event) -> None:
    consumer: AegisConsumer = _state["consumer"]
    while not stop_event.is_set():
        try:
            batch = await consumer.poll_batch()
            for message in batch:
                await _handle_message(message)
            if not batch:
                await asyncio.sleep(1.0)
            QUEUE_LAG.labels(service=SERVICE_NAME, topic=TOPIC_NORMALIZED, group=SERVICE_NAME).set(
                consumer.lag()
            )
        except Exception:
            logger.exception("consumer_loop_error")
            await asyncio.sleep(1.0)


@asynccontextmanager
async def lifespan(app: FastAPI):
    producer = AegisProducer(bootstrap_servers=settings.kafka_bootstrap, client_id=SERVICE_NAME)
    await producer.start()
    consumer = AegisConsumer(TOPIC_NORMALIZED, settings.kafka_bootstrap, group_id=SERVICE_NAME)
    await consumer.start()
    _state["producer"] = producer
    _state["consumer"] = consumer

    stop_event = asyncio.Event()
    task = asyncio.create_task(_consumer_loop(stop_event))
    _state["task"] = task
    logger.info("enrichment_service_started")
    yield
    stop_event.set()
    task.cancel()
    await producer.stop()
    await consumer.stop()


app = create_service_app(
    service_name=SERVICE_NAME,
    description="MITRE tagging, criticality, identity resolution, intel matching, entity extraction.",
    lifespan=lifespan,
)


@app.post("/api/v1/enrich", response_model=CanonicalEvent, tags=["enrich"])
async def enrich_one(event: dict = Body(...)) -> CanonicalEvent:
    canonical = CanonicalEvent.model_validate(event)
    return enrich_event(canonical)


@app.get("/api/v1/intel/iocs", tags=["intel"])
async def list_iocs() -> list[dict]:
    return intel.all_iocs()


@app.get("/api/v1/intel/kev", tags=["intel"])
async def list_kev() -> list[dict]:
    return intel.all_kev()


@app.get("/api/v1/intel/lookup", tags=["intel"])
async def lookup(indicator: str) -> dict:
    match = intel.match_indicator(indicator)
    return {"indicator": indicator, "match": match}


@app.get("/api/v1/stats", tags=["ops"])
async def stats() -> dict:
    consumer: AegisConsumer | None = _state.get("consumer")
    return {"consumer_lag": consumer.lag() if consumer else None}
