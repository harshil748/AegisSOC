"""SQLAlchemy models for the approval service (Postgres, sqlite in sync mode)."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import JSON, Boolean, DateTime, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from aegis_common.db import Base
from aegis_common.utils.helpers import utcnow


class ApprovalRequestORM(Base):
    __tablename__ = "approval_requests"

    approval_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    tenant_id: Mapped[str] = mapped_column(String(64), default="default", index=True)
    action_id: Mapped[str] = mapped_column(String(64), index=True)
    case_id: Mapped[str] = mapped_column(String(64), index=True)
    action_class: Mapped[str] = mapped_column(String(64), index=True)
    title: Mapped[str] = mapped_column(String(500), default="")
    description: Mapped[str] = mapped_column(Text, default="")
    disruptive: Mapped[bool] = mapped_column(Boolean, default=True)
    dry_run: Mapped[bool] = mapped_column(Boolean, default=True)
    requested_by: Mapped[str] = mapped_column(String(128), default="system")
    status: Mapped[str] = mapped_column(String(32), default="pending", index=True)
    # pending | approved | rejected | executed | rolled_back
    decided_by: Mapped[str | None] = mapped_column(String(128), nullable=True)
    decision: Mapped[str | None] = mapped_column(String(32), nullable=True)
    rationale: Mapped[str | None] = mapped_column(Text, nullable=True)
    decided_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    payload: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class ExecutionRecordORM(Base):
    __tablename__ = "execution_records"

    execution_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    approval_id: Mapped[str] = mapped_column(String(64), index=True)
    action_class: Mapped[str] = mapped_column(String(64))
    adapter: Mapped[str] = mapped_column(String(64))
    dry_run: Mapped[bool] = mapped_column(Boolean, default=True)
    status: Mapped[str] = mapped_column(String(32))  # success | failed
    result: Mapped[dict] = mapped_column(JSON, default=dict)
    rollback_token: Mapped[str | None] = mapped_column(String(128), nullable=True)
    executed_by: Mapped[str] = mapped_column(String(128))
    executed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class RollbackRecordORM(Base):
    __tablename__ = "rollback_records"

    rollback_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    execution_id: Mapped[str] = mapped_column(String(64), index=True)
    approval_id: Mapped[str] = mapped_column(String(64), index=True)
    initiated_by: Mapped[str] = mapped_column(String(128))
    reason: Mapped[str] = mapped_column(Text, default="")
    status: Mapped[str] = mapped_column(String(32))  # success | failed | unsupported
    result: Mapped[dict] = mapped_column(JSON, default=dict)
    rolled_back_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
