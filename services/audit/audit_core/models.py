"""SQLAlchemy models for the audit service (Postgres, sqlite in sync mode).

``audit_events`` is intentionally append-only at the application layer: no
repository function ever issues an UPDATE or DELETE against this table.
Each row also carries a hash-chain link (``sequence`` + ``prev_hash`` +
``record_hash``) so any out-of-band tampering (e.g. a direct DB edit that
bypasses the API) can be detected by ``audit_core.hashchain.verify_chain``.
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import JSON, BigInteger, DateTime, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from aegis_common.db import Base
from aegis_common.utils.helpers import utcnow


class AuditEventORM(Base):
    __tablename__ = "audit_events"

    audit_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    sequence: Mapped[int] = mapped_column(BigInteger, index=True, unique=True, autoincrement=False)
    tenant_id: Mapped[str] = mapped_column(String(64), default="default", index=True)
    actor: Mapped[str] = mapped_column(String(128), index=True)
    actor_type: Mapped[str] = mapped_column(String(32), index=True)  # user | system | llm | service
    action: Mapped[str] = mapped_column(String(128), index=True)
    resource_type: Mapped[str] = mapped_column(String(64), index=True)
    resource_id: Mapped[str] = mapped_column(String(128), index=True)
    timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, index=True)
    details: Mapped[dict] = mapped_column(JSON, default=dict)
    prompt_hash: Mapped[str | None] = mapped_column(String(128), nullable=True)
    evidence_refs: Mapped[list] = mapped_column(JSON, default=list)
    prev_hash: Mapped[str] = mapped_column(String(64))
    record_hash: Mapped[str] = mapped_column(String(64), index=True)
