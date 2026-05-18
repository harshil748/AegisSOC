"""Neo4j-backed implementation of the AegisSOC temporal security graph."""

from __future__ import annotations

import json
import logging
from typing import Any

from aegis_common.schema.events import GraphEdge, GraphNode
from aegis_common.utils.helpers import json_dumps

from aegis_common.graphstore.base import GraphStore

logger = logging.getLogger("aegis.graph_builder.neo4j")

MAX_OBSERVATIONS = 25


class Neo4jGraphStore(GraphStore):
    backend_name = "neo4j"

    def __init__(self, uri: str, user: str, password: str) -> None:
        from neo4j import AsyncGraphDatabase

        self._driver = AsyncGraphDatabase.driver(uri, auth=(user, password))

    async def verify_connectivity(self) -> None:
        await self._driver.verify_connectivity()

    async def close(self) -> None:
        await self._driver.close()

    async def upsert_node(self, node: GraphNode, observation: dict[str, Any] | None = None) -> None:
        label = node.node_type.value
        obs_json = json.dumps(observation, default=str) if observation else None
        query = f"""
        MERGE (n:{label} {{node_id: $node_id}})
        ON CREATE SET n.tenant_id = $tenant_id, n.first_seen = $first_seen, n.last_seen = $last_seen,
                      n.count = 1, n.confidence = $confidence, n.sources = $merged_sources,
                      n.properties_json = $properties_json, n.observations = CASE WHEN $obs_json IS NULL THEN [] ELSE [$obs_json] END
        ON MATCH SET n.last_seen = $last_seen, n.count = n.count + 1,
                      n.confidence = (n.confidence + $confidence) / 2.0,
                      n.sources = $merged_sources,
                      n.observations = CASE WHEN $obs_json IS NULL THEN n.observations
                                            ELSE (coalesce(n.observations, [])[-{MAX_OBSERVATIONS - 1}..] + [$obs_json]) END
        """
        async with self._driver.session() as session:
            existing = await session.run(
                "MATCH (n {node_id: $node_id}) RETURN n.sources AS sources", node_id=node.node_id
            )
            record = await existing.single()
            merged_sources = sorted(
                set((record["sources"] if record else []) or [])
                | set(s.value if hasattr(s, "value") else s for s in node.sources)
            )
            await session.run(
                query,
                node_id=node.node_id,
                tenant_id=node.tenant_id,
                first_seen=node.first_seen.isoformat(),
                last_seen=node.last_seen.isoformat(),
                confidence=node.confidence,
                merged_sources=merged_sources,
                properties_json=json_dumps(node.properties).decode(),
                obs_json=obs_json,
            )

    async def upsert_edge(self, edge: GraphEdge, observation: dict[str, Any] | None = None) -> None:
        rel_type = edge.edge_type.value.upper()
        obs_json = json.dumps(observation, default=str) if observation else None
        async with self._driver.session() as session:
            existing = await session.run(
                "MATCH ()-[r {edge_id_key: $key}]->() RETURN r.sources AS sources",
                key=f"{edge.src_id}|{edge.edge_type.value}|{edge.dst_id}",
            )
            record = await existing.single()
            merged_sources = sorted(
                set((record["sources"] if record else []) or []) | set(s.value if hasattr(s, "value") else s for s in edge.sources)
            )
            query = f"""
            MATCH (src {{node_id: $src_id}})
            MATCH (dst {{node_id: $dst_id}})
            MERGE (src)-[r:{rel_type} {{edge_id_key: $key}}]->(dst)
            ON CREATE SET r.tenant_id = $tenant_id, r.first_seen = $first_seen, r.last_seen = $last_seen,
                          r.count = 1, r.confidence = $confidence, r.sources = $merged_sources,
                          r.properties_json = $properties_json,
                          r.observations = CASE WHEN $obs_json IS NULL THEN [] ELSE [$obs_json] END
            ON MATCH SET r.last_seen = $last_seen, r.count = r.count + 1,
                          r.confidence = (r.confidence + $confidence) / 2.0,
                          r.sources = $merged_sources,
                          r.observations = CASE WHEN $obs_json IS NULL THEN r.observations
                                               ELSE (coalesce(r.observations, [])[-{MAX_OBSERVATIONS - 1}..] + [$obs_json]) END
            """
            await session.run(
                query,
                src_id=edge.src_id,
                dst_id=edge.dst_id,
                key=f"{edge.src_id}|{edge.edge_type.value}|{edge.dst_id}",
                tenant_id=edge.tenant_id,
                first_seen=edge.first_seen.isoformat(),
                last_seen=edge.last_seen.isoformat(),
                confidence=edge.confidence,
                merged_sources=merged_sources,
                properties_json=json_dumps(edge.properties).decode(),
                obs_json=obs_json,
            )

    async def get_node(self, node_id: str) -> dict[str, Any] | None:
        async with self._driver.session() as session:
            result = await session.run("MATCH (n {node_id: $id}) RETURN n", id=node_id)
            record = await result.single()
            return dict(record["n"]) if record else None

    async def neighborhood(self, node_id: str, depth: int = 1, limit: int = 100) -> dict[str, Any]:
        depth = max(1, min(depth, 4))
        query = f"""
        MATCH (n {{node_id: $id}})
        OPTIONAL MATCH path = (n)-[*1..{depth}]-(m)
        WITH n, collect(DISTINCT m) AS neighbors, collect(DISTINCT path) AS paths
        RETURN n, neighbors, paths
        LIMIT 1
        """
        async with self._driver.session() as session:
            result = await session.run(query, id=node_id)
            record = await result.single()
            if not record:
                return {"root": node_id, "nodes": [], "edges": []}
            nodes = [dict(record["n"])] + [dict(n) for n in record["neighbors"]]
            edges: list[dict] = []
            for path in record["paths"] or []:
                for rel in path.relationships:
                    edges.append(dict(rel))
            return {"root": node_id, "nodes": nodes[:limit], "edges": edges[:limit]}

    async def attack_path(self, src_id: str, dst_id: str, max_depth: int = 6) -> dict[str, Any]:
        query = f"""
        MATCH (s {{node_id: $src}}), (d {{node_id: $dst}})
        MATCH path = shortestPath((s)-[*..{max_depth}]-(d))
        RETURN path
        LIMIT 1
        """
        async with self._driver.session() as session:
            result = await session.run(query, src=src_id, dst=dst_id)
            record = await result.single()
            if not record:
                return {"found": False, "path": [], "length": -1}
            path = record["path"]
            edges = [dict(rel) for rel in path.relationships]
            return {"found": True, "path": edges, "length": len(edges)}

    async def entity_timeline(self, node_id: str, limit: int = 200) -> list[dict[str, Any]]:
        query = """
        MATCH (n {node_id: $id})
        OPTIONAL MATCH (n)-[r]-()
        RETURN n.observations AS node_obs, collect(r.observations) AS edge_obs
        """
        events: list[dict[str, Any]] = []
        async with self._driver.session() as session:
            result = await session.run(query, id=node_id)
            record = await result.single()
            if record:
                for raw in record["node_obs"] or []:
                    events.append(json.loads(raw))
                for edge_list in record["edge_obs"] or []:
                    for raw in edge_list or []:
                        events.append(json.loads(raw))
        events.sort(key=lambda e: e.get("timestamp") or "")
        return events[-limit:]

    async def stats(self) -> dict[str, Any]:
        async with self._driver.session() as session:
            node_count = await (await session.run("MATCH (n) RETURN count(n) AS c")).single()
            edge_count = await (await session.run("MATCH ()-[r]->() RETURN count(r) AS c")).single()
            return {
                "backend": self.backend_name,
                "node_count": node_count["c"],
                "edge_count": edge_count["c"],
            }

    async def rare_edge_score(self, edge_type: str) -> float:
        async with self._driver.session() as session:
            total_res = await session.run("MATCH ()-[r]->() RETURN count(r) AS c")
            total = (await total_res.single())["c"]
            type_res = await session.run(
                f"MATCH ()-[r:{edge_type.upper()}]->() RETURN count(r) AS c"
            )
            type_count = (await type_res.single())["c"]
            if total == 0:
                return 0.5
            return round(max(0.0, 1.0 - (type_count / total) * 10), 3)

    async def degree(self, node_id: str) -> int:
        async with self._driver.session() as session:
            result = await session.run(
                "MATCH (n {node_id: $id})-[r]-() RETURN count(r) AS c", id=node_id
            )
            record = await result.single()
            return record["c"] if record else 0

    async def path_length_to_known_bad(
        self, node_id: str, known_bad_ids: list[str], max_depth: int = 4
    ) -> int | None:
        if not known_bad_ids:
            return None
        query = f"""
        MATCH (s {{node_id: $id}})
        MATCH (bad) WHERE bad.node_id IN $bad_ids
        MATCH path = shortestPath((s)-[*..{max_depth}]-(bad))
        RETURN length(path) AS len
        ORDER BY len ASC
        LIMIT 1
        """
        async with self._driver.session() as session:
            result = await session.run(query, id=node_id, bad_ids=known_bad_ids)
            record = await result.single()
            return record["len"] if record else None
