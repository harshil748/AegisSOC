"""File-backed in-memory graph store (Neo4j fallback for sync/demo mode).

Persists to a single JSON document under ``AEGIS_DATA_DIR/graph`` so that
multiple processes (the graph_builder consumer and the frontend_gateway
demo orchestrator running in-process) observe the same graph without
requiring Neo4j to be up. Adjacency is rebuilt on load; this trades some
performance for zero external dependencies, which is the right trade-off
at demo scale (thousands, not billions, of nodes/edges).
"""

from __future__ import annotations

import json
import os
import threading
from collections import defaultdict, deque
from pathlib import Path
from typing import Any

from aegis_common.schema.events import GraphEdge, GraphNode
from aegis_common.utils.helpers import utcnow

from aegis_common.graphstore.base import GraphStore

MAX_OBSERVATIONS = 25


class InMemoryGraphStore(GraphStore):
    backend_name = "in_memory_json"

    def __init__(self, path: str | None = None) -> None:
        base = Path(os.getenv("AEGIS_DATA_DIR", "./data")) / "graph"
        base.mkdir(parents=True, exist_ok=True)
        self.path = Path(path or (base / "state.json"))
        self._lock = threading.Lock()
        if not self.path.exists():
            self._write({"nodes": {}, "edges": {}})

    def _read(self) -> dict[str, Any]:
        with self._lock:
            if not self.path.exists():
                return {"nodes": {}, "edges": {}}
            try:
                return json.loads(self.path.read_text() or "{}") or {"nodes": {}, "edges": {}}
            except json.JSONDecodeError:
                return {"nodes": {}, "edges": {}}

    def _write(self, data: dict[str, Any]) -> None:
        with self._lock:
            tmp = self.path.with_suffix(".tmp")
            tmp.write_text(json.dumps(data, default=str))
            tmp.replace(self.path)

    @staticmethod
    def _edge_key(edge: GraphEdge) -> str:
        return f"{edge.src_id}|{edge.edge_type.value}|{edge.dst_id}"

    async def upsert_node(self, node: GraphNode, observation: dict[str, Any] | None = None) -> None:
        data = self._read()
        existing = data["nodes"].get(node.node_id)
        now_iso = utcnow().isoformat()
        if existing:
            existing["last_seen"] = node.last_seen.isoformat()
            existing["count"] = existing.get("count", 1) + 1
            existing["properties"].update(node.properties)
            existing["sources"] = sorted(set(existing.get("sources", [])) | {s for s in node.sources})
            if observation:
                obs = existing.setdefault("observations", [])
                obs.append(observation)
                del obs[:-MAX_OBSERVATIONS]
        else:
            payload = node.model_dump(mode="json")
            payload["observations"] = [observation] if observation else []
            data["nodes"][node.node_id] = payload
        data["nodes"][node.node_id]["updated_at"] = now_iso
        self._write(data)

    async def upsert_edge(self, edge: GraphEdge, observation: dict[str, Any] | None = None) -> None:
        data = self._read()
        key = self._edge_key(edge)
        existing = data["edges"].get(key)
        if existing:
            existing["last_seen"] = edge.last_seen.isoformat()
            existing["count"] = existing.get("count", 1) + 1
            existing["properties"].update(edge.properties)
            existing["sources"] = sorted(set(existing.get("sources", [])) | {s for s in edge.sources})
            if observation:
                obs = existing.setdefault("observations", [])
                obs.append(observation)
                del obs[:-MAX_OBSERVATIONS]
        else:
            payload = edge.model_dump(mode="json")
            payload["observations"] = [observation] if observation else []
            data["edges"][key] = payload
        self._write(data)

    async def get_node(self, node_id: str) -> dict[str, Any] | None:
        return self._read()["nodes"].get(node_id)

    def _adjacency(self, data: dict[str, Any]) -> dict[str, list[dict]]:
        adjacency: dict[str, list[dict]] = defaultdict(list)
        for edge in data["edges"].values():
            adjacency[edge["src_id"]].append(edge)
            reverse = dict(edge)
            reverse["src_id"], reverse["dst_id"] = edge["dst_id"], edge["src_id"]
            reverse["_reversed"] = True
            adjacency[edge["dst_id"]].append(reverse)
        return adjacency

    async def neighborhood(self, node_id: str, depth: int = 1, limit: int = 100) -> dict[str, Any]:
        data = self._read()
        adjacency = self._adjacency(data)
        visited_nodes: dict[str, dict] = {}
        visited_edges: list[dict] = []
        frontier = {node_id}
        seen_edge_keys: set[str] = set()

        for _ in range(max(depth, 0)):
            next_frontier: set[str] = set()
            for nid in frontier:
                if nid in data["nodes"] and nid not in visited_nodes:
                    visited_nodes[nid] = data["nodes"][nid]
                for edge in adjacency.get(nid, []):
                    ek = f"{edge['src_id']}|{edge['edge_type']}|{edge['dst_id']}"
                    if ek not in seen_edge_keys:
                        seen_edge_keys.add(ek)
                        visited_edges.append(edge)
                        if len(visited_edges) >= limit:
                            break
                    other = edge["dst_id"] if not edge.get("_reversed") else edge["dst_id"]
                    next_frontier.add(edge["dst_id"])
            frontier = next_frontier - set(visited_nodes.keys())
            if len(visited_edges) >= limit:
                break

        for nid in list(frontier) + [node_id]:
            if nid in data["nodes"]:
                visited_nodes[nid] = data["nodes"][nid]

        return {
            "root": node_id,
            "nodes": list(visited_nodes.values()),
            "edges": visited_edges[:limit],
        }

    async def attack_path(self, src_id: str, dst_id: str, max_depth: int = 6) -> dict[str, Any]:
        data = self._read()
        adjacency = self._adjacency(data)
        queue: deque[tuple[str, list[dict]]] = deque([(src_id, [])])
        visited = {src_id}
        while queue:
            current, path = queue.popleft()
            if current == dst_id:
                return {"found": True, "path": path, "length": len(path)}
            if len(path) >= max_depth:
                continue
            for edge in adjacency.get(current, []):
                nxt = edge["dst_id"]
                if nxt not in visited:
                    visited.add(nxt)
                    queue.append((nxt, path + [edge]))
        return {"found": False, "path": [], "length": -1}

    async def entity_timeline(self, node_id: str, limit: int = 200) -> list[dict[str, Any]]:
        data = self._read()
        events: list[dict[str, Any]] = []
        for edge in data["edges"].values():
            if edge["src_id"] == node_id or edge["dst_id"] == node_id:
                for obs in edge.get("observations", []):
                    events.append({**obs, "edge_type": edge["edge_type"], "src_id": edge["src_id"], "dst_id": edge["dst_id"]})
        node = data["nodes"].get(node_id)
        if node:
            for obs in node.get("observations", []):
                events.append({**obs, "node_type": node["node_type"]})
        events.sort(key=lambda e: e.get("timestamp") or "")
        return events[-limit:]

    async def stats(self) -> dict[str, Any]:
        data = self._read()
        return {
            "backend": self.backend_name,
            "node_count": len(data["nodes"]),
            "edge_count": len(data["edges"]),
        }

    async def rare_edge_score(self, edge_type: str) -> float:
        data = self._read()
        counts: dict[str, int] = defaultdict(int)
        for edge in data["edges"].values():
            counts[edge["edge_type"]] += 1
        total = sum(counts.values())
        if total == 0:
            return 0.5
        freq = counts.get(edge_type, 0) / total
        return round(max(0.0, 1.0 - freq * len(counts)), 3) if counts else 0.5

    async def degree(self, node_id: str) -> int:
        data = self._read()
        return sum(
            1 for e in data["edges"].values() if e["src_id"] == node_id or e["dst_id"] == node_id
        )

    async def path_length_to_known_bad(
        self, node_id: str, known_bad_ids: list[str], max_depth: int = 4
    ) -> int | None:
        if not known_bad_ids:
            return None
        data = self._read()
        adjacency = self._adjacency(data)
        bad_set = set(known_bad_ids)
        if node_id in bad_set:
            return 0
        queue: deque[tuple[str, int]] = deque([(node_id, 0)])
        visited = {node_id}
        while queue:
            current, dist = queue.popleft()
            if dist >= max_depth:
                continue
            for edge in adjacency.get(current, []):
                nxt = edge["dst_id"]
                if nxt in bad_set:
                    return dist + 1
                if nxt not in visited:
                    visited.add(nxt)
                    queue.append((nxt, dist + 1))
        return None
