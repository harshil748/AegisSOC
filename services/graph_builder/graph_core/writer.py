"""Derives GraphNode/GraphEdge upserts from an enriched CanonicalEvent."""

from __future__ import annotations

from typing import Any

from aegis_common.schema.events import CanonicalEvent, EdgeType, EntityRef, GraphEdge, GraphNode, NodeType
from aegis_common.utils.helpers import utcnow

LOGON_EVENT_TYPES = {"logon", "logon_failure", "special_privileges_assigned"}
NETWORK_EVENT_TYPES = {"network_connection", "network_alert", "zeek_conn", "firewall_connection"}


def _find_entity(entities: list[EntityRef], node_type: NodeType) -> EntityRef | None:
    for entity in entities:
        if entity.type == node_type:
            return entity
    return None


def _all_entities(entities: list[EntityRef], node_type: NodeType) -> list[EntityRef]:
    return [e for e in entities if e.type == node_type]


def build_node(entity: EntityRef, event: CanonicalEvent) -> GraphNode:
    return GraphNode(
        node_id=entity.id,
        node_type=entity.type,
        tenant_id=event.tenant_id,
        labels=[entity.type.value],
        properties={"display_name": entity.display_name, **entity.attributes},
        first_seen=event.timestamp,
        last_seen=event.timestamp,
        count=1,
        confidence=event.source_confidence,
        sources=[event.source],
        provenance_ids=[event.provenance.raw_event_id] if event.provenance else [],
    )


def build_edge(
    src: EntityRef, dst: EntityRef, edge_type: EdgeType, event: CanonicalEvent, **props: Any
) -> GraphEdge:
    return GraphEdge(
        edge_type=edge_type,
        src_id=src.id,
        dst_id=dst.id,
        tenant_id=event.tenant_id,
        first_seen=event.timestamp,
        last_seen=event.timestamp,
        count=1,
        confidence=event.source_confidence,
        sources=[event.source],
        properties=props,
        provenance_ids=[event.provenance.raw_event_id] if event.provenance else [],
        labels=[event.event_type],
    )


def observation_for(event: CanonicalEvent) -> dict[str, Any]:
    return {
        "event_id": event.event_id,
        "event_type": event.event_type,
        "timestamp": event.timestamp.isoformat(),
        "source": event.source.value,
        "severity": event.severity.value,
    }


def derive_graph_updates(event: CanonicalEvent) -> tuple[list[GraphNode], list[GraphEdge]]:
    entities = event.entities
    nodes: list[GraphNode] = [build_node(e, event) for e in entities]
    edges: list[GraphEdge] = []

    user = _find_entity(entities, NodeType.USER)
    host = _find_entity(entities, NodeType.HOST)
    processes = _all_entities(entities, NodeType.PROCESS)
    files = _all_entities(entities, NodeType.FILE)
    ips = _all_entities(entities, NodeType.IP)
    domain = _find_entity(entities, NodeType.DOMAIN)
    url = _find_entity(entities, NodeType.URL)
    registry = _find_entity(entities, NodeType.REGISTRY_KEY)
    email = _find_entity(entities, NodeType.EMAIL)
    techniques = _all_entities(entities, NodeType.ATTACK_TECHNIQUE)
    hash_entity = _find_entity(entities, NodeType.HASH)

    if user and host:
        if event.event_type in LOGON_EVENT_TYPES:
            edges.append(build_edge(user, host, EdgeType.AUTHENTICATED_TO, event, logon_type=event.raw.get("LogonType")))
        edges.append(build_edge(user, host, EdgeType.LOGGED_IN_TO, event))

    if len(processes) >= 2:
        # entities are appended [process, parent_process] order per enrichment_core.entities
        child, parent = processes[0], processes[1]
        edges.append(build_edge(parent, child, EdgeType.SPAWNED, event, command_line=event.command_line))
    elif len(processes) == 1 and host:
        edges.append(build_edge(host, processes[0], EdgeType.EXECUTED, event))

    primary_process = processes[0] if processes else None

    if primary_process and event.event_type == "process_access":
        for f in files:
            edges.append(build_edge(primary_process, f, EdgeType.ACCESSED, event))

    for f in files:
        if event.event_type in {"file_create"}:
            actor = primary_process or host
            if actor:
                edges.append(build_edge(actor, f, EdgeType.CREATED, event))
        elif event.event_type in {"file_modify", "file_delete"}:
            actor = primary_process or host
            if actor:
                edges.append(build_edge(actor, f, EdgeType.MODIFIED, event))

    if len(ips) == 2:
        edges.append(build_edge(ips[0], ips[1], EdgeType.CONNECTED_TO, event, dst_port=event.dst_port))
    elif len(ips) == 1 and host and event.event_type in NETWORK_EVENT_TYPES:
        edges.append(build_edge(host, ips[0], EdgeType.CONNECTED_TO, event, dst_port=event.dst_port))

    if domain and ips:
        edges.append(build_edge(domain, ips[-1], EdgeType.RESOLVED_TO, event))

    if url:
        actor = primary_process or user or host
        if actor:
            edge_type = EdgeType.DOWNLOADED if primary_process else EdgeType.ACCESSED
            edges.append(build_edge(actor, url, edge_type, event))

    if registry and primary_process:
        edges.append(build_edge(primary_process, registry, EdgeType.MODIFIED, event))

    if email and user:
        edges.append(build_edge(email, user, EdgeType.EMAILED, event))

    if hash_entity and primary_process:
        edges.append(build_edge(primary_process, hash_entity, EdgeType.CREATED, event))

    primary_entity = primary_process or host or user
    if primary_entity:
        for tech in techniques:
            edges.append(build_edge(primary_entity, tech, EdgeType.MAPPED_TO_TECHNIQUE, event))

    return nodes, edges
