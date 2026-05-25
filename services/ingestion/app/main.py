"""AegisSOC Ingestion Service.

Accepts multi-source telemetry via REST, validates and deduplicates it,
and publishes onto the raw-events stream (Kafka in production, a local
file-backed bus in sync/demo mode). Malformed records are dead-lettered.
Also exposes a replay API for historical/demo scenarios.
"""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI, HTTPException

from aegis_common.config import Settings
from aegis_common.idempotency import default_store
from aegis_common.kafka.producer import AegisProducer
from aegis_common.service import create_service_app

from ingestion_core.ingest import process_envelope
from ingestion_core.models import (
    BatchIngestRequest,
    BatchIngestResult,
    IngestResult,
    RawEnvelope,
    ReplayRequest,
    ReplayResult,
)
from ingestion_core.replay import list_scenarios, replay_scenario

settings = Settings()
logger = logging.getLogger("aegis.ingestion")

_state: dict = {}


@asynccontextmanager
async def lifespan(app: FastAPI):
    producer = AegisProducer(bootstrap_servers=settings.kafka_bootstrap, client_id="ingestion")
    await producer.start()
    _state["producer"] = producer
    _state["idempotency"] = default_store("ingestion")
    logger.info("ingestion_service_started sync_mode=%s", app.state.__dict__.get("sync_mode"))
    yield
    await producer.stop()
    _state["idempotency"].close()


app = create_service_app(
    service_name="ingestion",
    description="Multi-source telemetry ingestion, DLQ routing, and scenario replay.",
    lifespan=lifespan,
)


def get_producer() -> AegisProducer:
    return _state["producer"]


def get_idempotency():
    return _state["idempotency"]


@app.post("/api/v1/ingest", response_model=IngestResult, tags=["ingest"])
async def ingest_event(
    envelope: RawEnvelope,
    producer: AegisProducer = Depends(get_producer),
    idempotency=Depends(get_idempotency),
) -> IngestResult:
    return await process_envelope(envelope, producer, idempotency)


@app.post("/api/v1/ingest/batch", response_model=BatchIngestResult, tags=["ingest"])
async def ingest_batch(
    request: BatchIngestRequest,
    producer: AegisProducer = Depends(get_producer),
    idempotency=Depends(get_idempotency),
) -> BatchIngestResult:
    results: list[IngestResult] = []
    for envelope in request.events:
        results.append(await process_envelope(envelope, producer, idempotency))
    return BatchIngestResult(
        accepted=sum(1 for r in results if r.status == "accepted"),
        duplicates=sum(1 for r in results if r.status == "duplicate"),
        dead_lettered=sum(1 for r in results if r.status == "dead_lettered"),
        results=results,
    )


@app.get("/api/v1/replay/scenarios", tags=["replay"])
async def get_scenarios() -> list[dict]:
    return list_scenarios()


@app.post("/api/v1/replay/{scenario_id}", response_model=ReplayResult, tags=["replay"])
async def run_replay(
    scenario_id: str,
    request: ReplayRequest | None = None,
    producer: AegisProducer = Depends(get_producer),
    idempotency=Depends(get_idempotency),
) -> ReplayResult:
    tenant_id = request.tenant_id if request else "default"
    try:
        return await replay_scenario(scenario_id, producer, idempotency, tenant_id=tenant_id)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@app.get("/api/v1/stats", tags=["ops"])
async def stats() -> dict:
    from aegis_common.kafka.bus import get_bus

    bus = get_bus()
    return {
        "raw_events_lag_normalization": bus.lag("aegis.raw.events", "normalization"),
    }
