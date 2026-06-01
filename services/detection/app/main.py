"""AegisSOC Detection Service.

Consumes enriched events and runs the full detection stack: Sigma-like
rule matching, multi-event correlation, graph feature extraction, temporal
sequence features, a lightweight numpy GraphSAGE-ish scorer, and an
ensemble risk score -- then deduplicates/clusters resulting detections into
Alert objects.
"""

from __future__ import annotations

import asyncio
import logging
from contextlib import asynccontextmanager

from fastapi import Body, FastAPI

from aegis_common.config import Settings, TOPIC_ALERTS, TOPIC_DETECTIONS, TOPIC_ENRICHED
from aegis_common.kafka.consumer import AegisConsumer
from aegis_common.kafka.producer import AegisProducer
from aegis_common.observability import EVENTS_PROCESSED, QUEUE_LAG
from aegis_common.schema.events import CanonicalEvent
from aegis_common.service import create_service_app

from detection_core.pipeline import DetectionState, get_default_state, process_event

settings = Settings()
logger = logging.getLogger("aegis.detection")

SERVICE_NAME = "detection"
_state: dict = {}


async def _handle_message(message: dict) -> None:
    producer: AegisProducer = _state["producer"]
    detection_state: DetectionState = _state["detection_state"]
    event = CanonicalEvent.model_validate(message)
    hits, alert = await process_event(event, detection_state, settings)

    for hit in hits:
        EVENTS_PROCESSED.labels(service=SERVICE_NAME, stage="detect", outcome="rule_hit").inc()
        await producer.send(TOPIC_DETECTIONS, hit.model_dump(mode="json"), key=hit.detection_id)

    if alert is not None:
        EVENTS_PROCESSED.labels(service=SERVICE_NAME, stage="detect", outcome="alert").inc()
        await producer.send(TOPIC_ALERTS, alert.model_dump(mode="json"), key=alert.alert_id)
    else:
        EVENTS_PROCESSED.labels(service=SERVICE_NAME, stage="detect", outcome="no_alert").inc()


async def _consumer_loop(stop_event: asyncio.Event) -> None:
    consumer: AegisConsumer = _state["consumer"]
    while not stop_event.is_set():
        try:
            batch = await consumer.poll_batch()
            for message in batch:
                await _handle_message(message)
            if not batch:
                await asyncio.sleep(1.0)
            QUEUE_LAG.labels(service=SERVICE_NAME, topic=TOPIC_ENRICHED, group=SERVICE_NAME).set(
                consumer.lag()
            )
        except Exception:
            logger.exception("consumer_loop_error")
            await asyncio.sleep(1.0)


@asynccontextmanager
async def lifespan(app: FastAPI):
    detection_state = get_default_state()
    await detection_state.ensure_graph_store(settings)
    _state["detection_state"] = detection_state

    producer = AegisProducer(bootstrap_servers=settings.kafka_bootstrap, client_id=SERVICE_NAME)
    await producer.start()
    consumer = AegisConsumer(TOPIC_ENRICHED, settings.kafka_bootstrap, group_id=SERVICE_NAME)
    await consumer.start()
    _state["producer"] = producer
    _state["consumer"] = consumer

    stop_event = asyncio.Event()
    task = asyncio.create_task(_consumer_loop(stop_event))
    _state["task"] = task
    logger.info("detection_service_started rules=%d", len(detection_state.rules))
    yield
    stop_event.set()
    task.cancel()
    await producer.stop()
    await consumer.stop()


app = create_service_app(
    service_name=SERVICE_NAME,
    description="Sigma-like rules, correlation, graph/ML scoring, ensemble risk, and alert clustering.",
    lifespan=lifespan,
)


@app.post("/api/v1/detect", tags=["detect"])
async def detect_one(event: dict = Body(...)) -> dict:
    canonical = CanonicalEvent.model_validate(event)
    detection_state: DetectionState = _state.get("detection_state") or get_default_state()
    hits, alert = await process_event(canonical, detection_state, settings)
    return {
        "detection_hits": [h.model_dump(mode="json") for h in hits],
        "alert": alert.model_dump(mode="json") if alert else None,
    }


@app.get("/api/v1/rules", tags=["rules"])
async def list_rules() -> list[dict]:
    detection_state: DetectionState = _state.get("detection_state") or get_default_state()
    return [
        {k: v for k, v in r.items() if k != "_file"} | {"file": r.get("_file")}
        for r in detection_state.rules
    ]


@app.post("/api/v1/rules/reload", tags=["rules"])
async def reload_rules() -> dict:
    detection_state: DetectionState = _state.get("detection_state") or get_default_state()
    count = detection_state.reload_rules()
    return {"rules_loaded": count}


@app.get("/api/v1/alerts", tags=["alerts"])
async def list_alerts() -> list[dict]:
    detection_state: DetectionState = _state.get("detection_state") or get_default_state()
    return [a.model_dump(mode="json") for a in detection_state.cluster_store.all_alerts()]


@app.get("/api/v1/stats", tags=["ops"])
async def stats() -> dict:
    consumer: AegisConsumer | None = _state.get("consumer")
    detection_state: DetectionState = _state.get("detection_state") or get_default_state()
    return {
        "consumer_lag": consumer.lag() if consumer else None,
        "rules_loaded": len(detection_state.rules),
        "open_alert_clusters": len(detection_state.cluster_store.all_alerts()),
    }
