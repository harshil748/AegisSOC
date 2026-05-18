"""Graph store interface implemented by both the Neo4j and in-memory backends."""

from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import datetime
from typing import Any

from aegis_common.schema.events import GraphEdge, GraphNode


class GraphStore(ABC):
    backend_name: str = "abstract"

    @abstractmethod
    async def upsert_node(self, node: GraphNode, observation: dict[str, Any] | None = None) -> None: ...

    @abstractmethod
    async def upsert_edge(self, edge: GraphEdge, observation: dict[str, Any] | None = None) -> None: ...

    @abstractmethod
    async def get_node(self, node_id: str) -> dict[str, Any] | None: ...

    @abstractmethod
    async def neighborhood(self, node_id: str, depth: int = 1, limit: int = 100) -> dict[str, Any]: ...

    @abstractmethod
    async def attack_path(self, src_id: str, dst_id: str, max_depth: int = 6) -> dict[str, Any]: ...

    @abstractmethod
    async def entity_timeline(self, node_id: str, limit: int = 200) -> list[dict[str, Any]]: ...

    @abstractmethod
    async def stats(self) -> dict[str, Any]: ...

    @abstractmethod
    async def rare_edge_score(self, edge_type: str) -> float:
        """Return a rarity score in [0, 1] for an edge type (1 = very rare)."""
        ...

    @abstractmethod
    async def degree(self, node_id: str) -> int: ...

    @abstractmethod
    async def path_length_to_known_bad(self, node_id: str, known_bad_ids: list[str], max_depth: int = 4) -> int | None: ...

    async def close(self) -> None:  # pragma: no cover - optional override
        return None
