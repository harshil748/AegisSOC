"""Selects the Neo4j backend when reachable, else the in-memory fallback."""

from __future__ import annotations

import logging

from aegis_common.config import is_sync_mode
from aegis_common.graphstore.base import GraphStore
from aegis_common.graphstore.memory import InMemoryGraphStore

logger = logging.getLogger("aegis.graph_builder.factory")

_store: GraphStore | None = None


async def get_store(uri: str, user: str, password: str) -> GraphStore:
    global _store
    if _store is not None:
        return _store

    if is_sync_mode():
        logger.info("graph_store_sync_mode_in_memory")
        _store = InMemoryGraphStore()
        return _store

    try:
        from aegis_common.graphstore.neo4j_backend import Neo4jGraphStore

        store = Neo4jGraphStore(uri, user, password)
        await store.verify_connectivity()
        logger.info("graph_store_neo4j_connected uri=%s", uri)
        _store = store
    except Exception as exc:
        logger.warning("neo4j_unavailable_falling_back_to_memory err=%s", exc)
        _store = InMemoryGraphStore()
    return _store


def reset_store_for_tests() -> None:
    global _store
    _store = None
