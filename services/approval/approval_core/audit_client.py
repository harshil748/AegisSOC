"""Mirrors every approval decision, execution, and rollback into the audit
service for non-repudiation. Two implementations, matching the pattern used
by llm_triage's evidence tools:

* ``HTTPAuditSink`` -- posts to the standalone audit service (default).
* ``InProcessAuditSink`` -- wraps a callable so the frontend_gateway demo
  orchestrator can record audit events in-process, without the audit
  container running, when ``AEGIS_SYNC_MODE`` is on.

Audit writes are best-effort from approval's point of view: a slow/down
audit service must never block or fail an approval decision, but failures
are logged loudly since audit is the compliance system of record.
"""

from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from datetime import datetime, timezone
from typing import Any, Awaitable, Callable

import httpx

logger = logging.getLogger("aegis.approval.audit_client")


class AuditSink(ABC):
    @abstractmethod
    async def send(self, event: dict[str, Any]) -> None: ...


class HTTPAuditSink(AuditSink):
    def __init__(self, audit_url: str, timeout: float = 5.0) -> None:
        self.audit_url = audit_url.rstrip("/")
        self.timeout = timeout

    async def send(self, event: dict[str, Any]) -> None:
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                resp = await client.post(f"{self.audit_url}/api/v1/audit", json=event)
                resp.raise_for_status()
        except Exception:
            logger.exception("audit_sink_write_failed action=%s resource_id=%s", event.get("action"), event.get("resource_id"))


class InProcessAuditSink(AuditSink):
    def __init__(self, callback: Callable[[dict[str, Any]], Awaitable[None]]) -> None:
        self._callback = callback

    async def send(self, event: dict[str, Any]) -> None:
        try:
            await self._callback(event)
        except Exception:
            logger.exception("in_process_audit_sink_failed action=%s", event.get("action"))


def build_event(
    *,
    actor: str,
    actor_type: str,
    action: str,
    resource_type: str,
    resource_id: str,
    details: dict[str, Any] | None = None,
    evidence_refs: list[str] | None = None,
    tenant_id: str = "default",
) -> dict[str, Any]:
    return {
        "tenant_id": tenant_id,
        "actor": actor,
        "actor_type": actor_type,
        "action": action,
        "resource_type": resource_type,
        "resource_id": resource_id,
        "details": details or {},
        "evidence_refs": evidence_refs or [],
    }
