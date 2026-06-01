"""Pydantic request/response schemas for the audit service."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class AuditEventIn(BaseModel):
    tenant_id: str = "default"
    actor: str
    actor_type: str  # user | system | llm | service
    action: str
    resource_type: str
    resource_id: str
    details: dict[str, Any] = Field(default_factory=dict)
    prompt_hash: str | None = None
    evidence_refs: list[str] = Field(default_factory=list)


class AuditEventOut(AuditEventIn):
    audit_id: str
    sequence: int
    timestamp: datetime
    prev_hash: str
    record_hash: str

    model_config = {"from_attributes": True}


class ChainVerificationResult(BaseModel):
    tenant_id: str | None
    events_checked: int
    valid: bool
    first_broken_sequence: int | None = None
    detail: str
