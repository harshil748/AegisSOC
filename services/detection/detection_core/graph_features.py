"""Graph feature extraction: degree, rare-edge exposure, path-to-known-bad."""

from __future__ import annotations

import re

from aegis_common.graphstore.base import GraphStore
from aegis_common.schema.events import CanonicalEvent, EntityRef, NodeType
from aegis_common.utils.helpers import entity_id

_IP_RE = re.compile(r"^\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}$")
_HASH_RE = re.compile(r"^[a-f0-9]{32,64}$")


def guess_node_id_for_indicator(indicator: str, tenant_id: str = "default") -> str:
    if _IP_RE.match(indicator):
        return entity_id(NodeType.IP.value, indicator, tenant_id)
    if _HASH_RE.match(indicator):
        return entity_id(NodeType.HASH.value, indicator, tenant_id)
    if "." in indicator and not indicator.replace(".", "").isdigit():
        return entity_id(NodeType.DOMAIN.value, indicator, tenant_id)
    return entity_id(NodeType.DOMAIN.value, indicator, tenant_id)


def primary_entity(event: CanonicalEvent) -> EntityRef | None:
    for node_type in (NodeType.PROCESS, NodeType.HOST, NodeType.USER):
        for e in event.entities:
            if e.type == node_type:
                return e
    return event.entities[0] if event.entities else None


async def compute_graph_features(store: GraphStore, event: CanonicalEvent) -> dict:
    entity = primary_entity(event)
    if entity is None:
        return {
            "node_id": None,
            "degree": 0,
            "path_length_to_known_bad": None,
            "rare_edge_score": 0.5,
        }

    known_bad_ids = [
        guess_node_id_for_indicator(indicator, event.tenant_id) for indicator in event.intel_matches
    ]

    degree = await store.degree(entity.id)
    path_len = await store.path_length_to_known_bad(entity.id, known_bad_ids, max_depth=4)

    rarity_scores = []
    neighborhood = await store.neighborhood(entity.id, depth=1, limit=50)
    for edge in neighborhood.get("edges", []):
        edge_type = edge.get("edge_type", "")
        if edge_type:
            rarity_scores.append(await store.rare_edge_score(edge_type))
    avg_rarity = sum(rarity_scores) / len(rarity_scores) if rarity_scores else 0.5

    return {
        "node_id": entity.id,
        "degree": degree,
        "path_length_to_known_bad": path_len,
        "rare_edge_score": round(avg_rarity, 3),
        "neighbor_count": len(neighborhood.get("nodes", [])),
    }


def graph_score_from_features(features: dict) -> float:
    degree_norm = min(features.get("degree", 0) / 20.0, 1.0)
    rare_edge = features.get("rare_edge_score", 0.5)
    path_len = features.get("path_length_to_known_bad")
    path_to_bad_norm = 0.0 if path_len is None else max(0.0, 1.0 - (path_len / 4.0))
    return round(0.4 * degree_norm + 0.3 * rare_edge + 0.3 * path_to_bad_norm, 4)
