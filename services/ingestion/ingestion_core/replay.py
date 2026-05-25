"""Historical scenario replay for demos and detection regression testing."""

from __future__ import annotations

import json
import logging
import os
from pathlib import Path

from aegis_common.idempotency import IdempotencyStore
from aegis_common.kafka.producer import AegisProducer
from aegis_common.schema.events import resolve_telemetry_source
from aegis_common.utils.helpers import utcnow

from ingestion_core.ingest import process_envelope
from ingestion_core.models import RawEnvelope, ReplayResult

logger = logging.getLogger("aegis.ingestion.replay")


def scenarios_dir() -> Path:
    return Path(os.getenv("AEGIS_DATA_DIR", "./data")) / "scenarios"


def list_scenarios() -> list[dict]:
    out = []
    directory = scenarios_dir()
    if not directory.exists():
        return out
    for path in sorted(directory.glob("*.json")):
        try:
            data = json.loads(path.read_text())
            out.append(
                {
                    "scenario_id": data.get("scenario_id", path.stem),
                    "title": data.get("title", path.stem),
                    "description": data.get("description", ""),
                    "expected_outcome": data.get("expected_outcome"),
                    "event_count": len(data.get("events", [])),
                    "file": path.name,
                }
            )
        except Exception as exc:
            logger.warning("failed_to_read_scenario file=%s err=%s", path, exc)
    return out


def load_scenario(scenario_id: str) -> dict:
    directory = scenarios_dir()
    candidate = directory / f"{scenario_id}.json"
    if candidate.exists():
        return json.loads(candidate.read_text())
    for path in directory.glob("*.json"):
        data = json.loads(path.read_text())
        if data.get("scenario_id") == scenario_id:
            return data
    raise FileNotFoundError(f"scenario_not_found: {scenario_id}")


async def replay_scenario(
    scenario_id: str,
    producer: AegisProducer,
    idempotency: IdempotencyStore,
    tenant_id: str = "default",
) -> ReplayResult:
    data = load_scenario(scenario_id)
    started_at = utcnow()
    published = 0
    duplicates = 0

    for raw_event in data.get("events", []):
        envelope = RawEnvelope(
            tenant_id=tenant_id,
            source=resolve_telemetry_source(raw_event["source"]),
            timestamp=raw_event.get("timestamp"),
            payload=raw_event.get("raw") or raw_event.get("payload") or {},
        )
        result = await process_envelope(envelope, producer, idempotency)
        if result.status == "accepted":
            published += 1
        elif result.status == "duplicate":
            duplicates += 1

    finished_at = utcnow()
    logger.info(
        "scenario_replayed scenario_id=%s published=%d duplicates=%d",
        scenario_id,
        published,
        duplicates,
    )
    return ReplayResult(
        scenario_id=data.get("scenario_id", scenario_id),
        title=data.get("title", scenario_id),
        events_published=published,
        duplicates_skipped=duplicates,
        started_at=started_at,
        finished_at=finished_at,
    )
