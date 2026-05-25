"""Ingestion-layer request/response models.

``RawEnvelope`` is the wire format accepted at the ingestion boundary before
any per-source parsing happens (that's the normalization service's job).
It intentionally keeps ``payload`` as a free-form dict since each telemetry
source has its own native shape (Sysmon XML-ish fields, Zeek conn.log JSON,
CloudTrail API call records, etc).
"""

from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import uuid4

from pydantic import BaseModel, Field

from aegis_common.schema.events import TelemetrySource
from aegis_common.utils.helpers import stable_hash, utcnow


class RawEnvelope(BaseModel):
    event_id: str | None = None
    tenant_id: str = "default"
    source: TelemetrySource
    timestamp: datetime | None = None
    received_at: datetime = Field(default_factory=utcnow)
    payload: dict[str, Any] = Field(default_factory=dict)

    def compute_event_id(self) -> str:
        if self.event_id:
            return self.event_id
        basis = f"{self.tenant_id}:{self.source.value}:{self.timestamp}:{sorted(self.payload.items())}"
        return f"{self.source.value}-{stable_hash(basis)}"


class IngestResult(BaseModel):
    event_id: str
    status: str  # accepted | duplicate | dead_lettered
    topic: str | None = None
    reason: str | None = None


class BatchIngestRequest(BaseModel):
    events: list[RawEnvelope]


class BatchIngestResult(BaseModel):
    accepted: int
    duplicates: int
    dead_lettered: int
    results: list[IngestResult]


class ReplayRequest(BaseModel):
    scenario_id: str | None = None  # optional — path param is authoritative
    speed_multiplier: float = Field(default=1000.0, ge=0.001)
    compress_timestamps: bool = True
    tenant_id: str = "default"


class ReplayResult(BaseModel):
    scenario_id: str
    title: str
    events_published: int
    duplicates_skipped: int
    started_at: datetime
    finished_at: datetime


def new_id() -> str:
    return str(uuid4())
