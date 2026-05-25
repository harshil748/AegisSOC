"""AegisSOC Graph Builder Service.

Consumes enriched events, projects them into GraphNode/GraphEdge upserts
(temporal first_seen/last_seen/count, provenance pointers) against Neo4j,
falling back automatically to an in-memory/file-backed graph when Neo4j is
unreachable (sync/demo mode). Exposes neighborhood, attack-path, and
entity-timeline query APIs for the analyst UI and the LLM triage service.
"""

from __future__ import annotations

import asyncio
import logging
from contextlib import asynccontextmanager

from fastapi import Body, FastAPI, HTTPException, Query

from aegis_common.config import Settings, TOPIC_ENRICHED, TOPIC_GRAPH_UPDATES
from aegis_common.kafka.consumer import AegisConsumer
from aegis_common.kafka.producer import AegisProducer
from aegis_common.observability import EVENTS_PROCESSED, QUEUE_LAG
from aegis_common.schema.events import CanonicalEvent
from aegis_common.service import create_service_app

from aegis_common.graphstore import get_store
from graph_core.writer import derive_graph_updates, observation_for

settings = Settings()
logger = logging.getLogger("aegis.graph_builder")

SERVICE_NAME = "graph_builder"
_state: dict = {}


async def apply_event_to_graph(event: CanonicalEvent) -> dict:
    store = _state["store"]
    nodes, edges = derive_graph_updates(event)
    obs = observation_for(event)
    for node in nodes:
        await store.upsert_node(node, observation=obs)
    for edge in edges:
        await store.upsert_edge(edge, observation=obs)
    return {"nodes_upserted": len(nodes), "edges_upserted": len(edges)}


async def _handle_message(message: dict) -> None:
    producer: AegisProducer = _state["producer"]
    event = CanonicalEvent.model_validate(message)
    result = await apply_event_to_graph(event)
    EVENTS_PROCESSED.labels(service=SERVICE_NAME, stage="graph_write", outcome="written").inc()
    await producer.send(
        TOPIC_GRAPH_UPDATES,
        {"event_id": event.event_id, **result},
        key=event.event_id,
    )


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
    store = await get_store(settings.neo4j_uri, settings.neo4j_user, settings.neo4j_password)
    _state["store"] = store
    producer = AegisProducer(bootstrap_servers=settings.kafka_bootstrap, client_id=SERVICE_NAME)
    await producer.start()
    consumer = AegisConsumer(TOPIC_ENRICHED, settings.kafka_bootstrap, group_id=SERVICE_NAME)
    await consumer.start()
    _state["producer"] = producer
    _state["consumer"] = consumer

    stop_event = asyncio.Event()
    task = asyncio.create_task(_consumer_loop(stop_event))
    _state["task"] = task
    logger.info("graph_builder_service_started backend=%s", store.backend_name)
    yield
    stop_event.set()
    task.cancel()
    await producer.stop()
    await consumer.stop()
    await store.close()


app = create_service_app(
    service_name=SERVICE_NAME,
    description="Temporal security graph construction and query API (Neo4j / in-memory fallback).",
    lifespan=lifespan,
)


@app.post("/api/v1/graph/ingest", tags=["graph"])
async def ingest_event(event: dict = Body(...)) -> dict:
    canonical = CanonicalEvent.model_validate(event)
    return await apply_event_to_graph(canonical)


@app.get("/api/v1/graph/neighborhood/{node_id}", tags=["graph"])
async def neighborhood(node_id: str, depth: int = Query(1, ge=1, le=4), limit: int = 100) -> dict:
    return await _state["store"].neighborhood(node_id, depth=depth, limit=limit)


@app.get("/api/v1/graph/path", tags=["graph"])
async def attack_path(src: str, dst: str, max_depth: int = Query(6, ge=1, le=10)) -> dict:
    return await _state["store"].attack_path(src, dst, max_depth=max_depth)


@app.get("/api/v1/graph/timeline/{node_id}", tags=["graph"])
async def entity_timeline(node_id: str, limit: int = 200) -> list[dict]:
    return await _state["store"].entity_timeline(node_id, limit=limit)


@app.get("/api/v1/graph/node/{node_id}", tags=["graph"])
async def get_node(node_id: str) -> dict:
    node = await _state["store"].get_node(node_id)
    if not node:
        raise HTTPException(status_code=404, detail="node_not_found")
    return node


@app.get("/api/v1/graph/features/{node_id}", tags=["graph"])
async def graph_features(node_id: str, known_bad: list[str] = Query(default=[])) -> dict:
    store = _state["store"]
    degree = await store.degree(node_id)
    path_len = await store.path_length_to_known_bad(node_id, known_bad)
    return {"node_id": node_id, "degree": degree, "path_length_to_known_bad": path_len}


@app.get("/api/v1/graph/stats", tags=["ops"])
async def graph_stats() -> dict:
    return await _state["store"].stats()
