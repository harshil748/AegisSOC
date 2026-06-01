"""Pydantic request/response schemas for the approval service."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class CreateApprovalRequest(BaseModel):
    action_id: str
    case_id: str
    action_class: str
    title: str = ""
    description: str = ""
    disruptive: bool = True
    dry_run: bool = True
    requested_by: str = "system"
    tenant_id: str = "default"
    payload: dict[str, Any] = Field(default_factory=dict)


class DecisionRequest(BaseModel):
    decision: str = Field(pattern="^(approved|rejected)$")
    rationale: str


class ExecuteRequest(BaseModel):
    executed_by: str = "system"


class RollbackRequest(BaseModel):
    initiated_by: str
    reason: str


class ApprovalOut(BaseModel):
    approval_id: str
    tenant_id: str
    action_id: str
    case_id: str
    action_class: str
    title: str
    description: str
    disruptive: bool
    dry_run: bool
    requested_by: str
    status: str
    decided_by: str | None
    decision: str | None
    rationale: str | None
    decided_at: datetime | None
    payload: dict[str, Any]
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class ExecutionOut(BaseModel):
    execution_id: str
    approval_id: str
    action_class: str
    adapter: str
    dry_run: bool
    status: str
    result: dict[str, Any]
    rollback_token: str | None
    executed_by: str
    executed_at: datetime

    model_config = {"from_attributes": True}


class RollbackOut(BaseModel):
    rollback_id: str
    execution_id: str
    approval_id: str
    initiated_by: str
    reason: str
    status: str
    result: dict[str, Any]
    rolled_back_at: datetime

    model_config = {"from_attributes": True}
