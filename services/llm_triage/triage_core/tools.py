"""Evidence retrieval tools -- the ONLY way the LLM triage pipeline touches data.

The LLM never queries a database or the graph directly; it only ever sees
what these tools return, and the tools only ever return data (never
instructions). Two implementations are provided:

* ``HTTPEvidenceTools`` -- calls case_management / graph_builder over the
  network (used by the standalone service and in async/production mode).
* ``InProcessEvidenceTools`` -- wraps in-memory pipeline state directly
  (used by the frontend_gateway demo orchestrator so the full pipeline can
  run without any of the other containers being up).
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any

import httpx


class EvidenceTools(ABC):
    @abstractmethod
    async def get_case(self, case_id: str) -> dict[str, Any] | None: ...

    @abstractmethod
    async def get_alerts(self, case_id: str) -> list[dict[str, Any]]: ...

    @abstractmethod
    async def get_events(self, entity_id: str, limit: int = 50) -> list[dict[str, Any]]: ...

    @abstractmethod
    async def get_graph_neighborhood(self, entity_id: str, depth: int = 1) -> dict[str, Any]: ...


class HTTPEvidenceTools(EvidenceTools):
    def __init__(self, case_management_url: str, graph_builder_url: str, timeout: float = 8.0) -> None:
        self.case_management_url = case_management_url.rstrip("/")
        self.graph_builder_url = graph_builder_url.rstrip("/")
        self.timeout = timeout
        # Internal service identity presented to RBAC-protected endpoints.
        # In production this would be a scoped service-account JWT, not a
        # trusted header -- see docs note in aegis_common.auth.rbac.
        self._headers = {"X-Aegis-User": "llm_triage-service", "X-Aegis-Role": "admin"}

    async def get_case(self, case_id: str) -> dict[str, Any] | None:
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            resp = await client.get(
                f"{self.case_management_url}/api/v1/cases/{case_id}", headers=self._headers
            )
            if resp.status_code == 404:
                return None
            resp.raise_for_status()
            return resp.json()

    async def get_alerts(self, case_id: str) -> list[dict[str, Any]]:
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            resp = await client.get(f"{self.case_management_url}/api/v1/internal/cases/{case_id}/alerts")
            if resp.status_code == 404:
                return []
            resp.raise_for_status()
            return resp.json()

    async def get_events(self, entity_id: str, limit: int = 50) -> list[dict[str, Any]]:
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            resp = await client.get(
                f"{self.graph_builder_url}/api/v1/graph/timeline/{entity_id}", params={"limit": limit}
            )
            if resp.status_code == 404:
                return []
            resp.raise_for_status()
            return resp.json()

    async def get_graph_neighborhood(self, entity_id: str, depth: int = 1) -> dict[str, Any]:
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            resp = await client.get(
                f"{self.graph_builder_url}/api/v1/graph/neighborhood/{entity_id}", params={"depth": depth}
            )
            if resp.status_code == 404:
                return {"root": entity_id, "nodes": [], "edges": []}
            resp.raise_for_status()
            return resp.json()


class InProcessEvidenceTools(EvidenceTools):
    """Backs evidence retrieval with in-memory objects for the demo pipeline."""

    def __init__(self, case: dict[str, Any] | None, alerts: list[dict[str, Any]], graph_store) -> None:
        self._case = case
        self._alerts = alerts
        self._graph_store = graph_store

    async def get_case(self, case_id: str) -> dict[str, Any] | None:
        if self._case and self._case.get("case_id") == case_id:
            return self._case
        return None

    async def get_alerts(self, case_id: str) -> list[dict[str, Any]]:
        return self._alerts

    async def get_events(self, entity_id: str, limit: int = 50) -> list[dict[str, Any]]:
        if self._graph_store is None:
            return []
        return await self._graph_store.entity_timeline(entity_id, limit=limit)

    async def get_graph_neighborhood(self, entity_id: str, depth: int = 1) -> dict[str, Any]:
        if self._graph_store is None:
            return {"root": entity_id, "nodes": [], "edges": []}
        return await self._graph_store.neighborhood(entity_id, depth=depth)
