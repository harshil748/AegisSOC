"""Shared temporal security graph store (Neo4j-backed, with an in-memory fallback).

Used by graph_builder (writes), detection (feature extraction), llm_triage
(evidence retrieval), and the frontend_gateway demo orchestrator (in-process
pipeline). Centralizing this here -- rather than inside graph_builder alone
-- lets every service read the same graph state without requiring an HTTP
round-trip when running in sync/demo mode.
"""

from aegis_common.graphstore.base import GraphStore
from aegis_common.graphstore.factory import get_store, reset_store_for_tests
from aegis_common.graphstore.memory import InMemoryGraphStore

__all__ = ["GraphStore", "get_store", "reset_store_for_tests", "InMemoryGraphStore"]
