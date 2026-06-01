"""SQLAlchemy models for the case_management service (Postgres, sqlite in sync mode)."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import JSON, DateTime, Float, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from aegis_common.db import Base
from aegis_common.utils.helpers import utcnow


class CaseORM(Base):
    __tablename__ = "cases"

    case_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    tenant_id: Mapped[str] = mapped_column(String(64), default="default", index=True)
    title: Mapped[str] = mapped_column(String(500))
    status: Mapped[str] = mapped_column(String(32), default="new", index=True)
    severity: Mapped[str] = mapped_column(String(32), default="medium", index=True)
    risk_score: Mapped[float] = mapped_column(Float, default=0.0)
    alert_ids: Mapped[list] = mapped_column(JSON, default=list)
    entity_ids: Mapped[list] = mapped_column(JSON, default=list)
    technique_ids: Mapped[list] = mapped_column(JSON, default=list)
    timeline: Mapped[list] = mapped_column(JSON, default=list)
    attack_story: Mapped[str | None] = mapped_column(Text, nullable=True)
    assignee: Mapped[str | None] = mapped_column(String(128), nullable=True)
    tags: Mapped[list] = mapped_column(JSON, default=list)
    cluster_id: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class CaseFeedbackORM(Base):
    __tablename__ = "case_feedback"

    feedback_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    case_id: Mapped[str] = mapped_column(String(64), index=True)
    analyst: Mapped[str] = mapped_column(String(128))
    verdict: Mapped[str] = mapped_column(String(32))  # true_positive | false_positive | benign | needs_more_info
    comment: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class AlertRecordORM(Base):
    """Local copy of alerts landed from the detection service, for search/join."""

    __tablename__ = "alerts_landed"

    alert_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    tenant_id: Mapped[str] = mapped_column(String(64), default="default", index=True)
    cluster_id: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    case_id: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    title: Mapped[str] = mapped_column(String(500))
    severity: Mapped[str] = mapped_column(String(32))
    calibrated_score: Mapped[float] = mapped_column(Float, default=0.0)
    payload: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
