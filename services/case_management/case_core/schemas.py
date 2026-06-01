"""Pydantic request/response schemas for case_management."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field


class CreateCaseRequest(BaseModel):
    tenant_id: str = "default"
    title: str
    severity: str = "medium"
    alert_ids: list[str] = Field(default_factory=list)
    entity_ids: list[str] = Field(default_factory=list)
    technique_ids: list[str] = Field(default_factory=list)
    tags: list[str] = Field(default_factory=list)


class CaseOut(BaseModel):
    case_id: str
    tenant_id: str
    title: str
    status: str
    severity: str
    risk_score: float
    alert_ids: list[str]
    entity_ids: list[str]
    technique_ids: list[str]
    timeline: list[dict]
    attack_story: str | None
    assignee: str | None
    tags: list[str]
    cluster_id: str | None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class StatusUpdateRequest(BaseModel):
    status: str
    note: str | None = None


class AssignRequest(BaseModel):
    assignee: str


class FeedbackRequest(BaseModel):
    analyst: str
    verdict: str  # true_positive | false_positive | benign | needs_more_info
    comment: str | None = None


class FeedbackOut(BaseModel):
    feedback_id: str
    case_id: str
    analyst: str
    verdict: str
    comment: str | None
    created_at: datetime

    model_config = {"from_attributes": True}


class CaseSearchParams(BaseModel):
    status: str | None = None
    severity: str | None = None
    assignee: str | None = None
    text: str | None = None
    tenant_id: str | None = None
    limit: int = 50
    offset: int = 0
