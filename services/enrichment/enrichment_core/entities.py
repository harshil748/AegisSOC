"""Entity extraction: derive graph EntityRef objects from a CanonicalEvent."""

from __future__ import annotations

from aegis_common.schema.events import CanonicalEvent, EntityRef, NodeType
from aegis_common.utils.helpers import entity_id


def extract_entities(event: CanonicalEvent) -> list[EntityRef]:
    tenant = event.tenant_id
    entities: list[EntityRef] = []

    def add(node_type: NodeType, key: str | None, display: str | None = None, **attrs) -> None:
        if not key:
            return
        entities.append(
            EntityRef(
                type=node_type,
                id=entity_id(node_type.value, key, tenant),
                display_name=display or key,
                attributes={k: v for k, v in attrs.items() if v is not None},
            )
        )

    add(NodeType.HOST, event.host)
    add(NodeType.USER, event.user)
    if event.process:
        add(
            NodeType.PROCESS,
            f"{event.host}:{event.process}:{event.process_id}",
            display=event.process,
            process_id=event.process_id,
            host=event.host,
        )
    if event.parent_process:
        add(
            NodeType.PROCESS,
            f"{event.host}:{event.parent_process}:{event.parent_process_id}",
            display=event.parent_process,
            process_id=event.parent_process_id,
            host=event.host,
        )
    if event.file_path:
        add(NodeType.FILE, event.file_path, host=event.host)
    if event.file_hash:
        add(NodeType.HASH, event.file_hash)
    add(NodeType.IP, event.src_ip)
    add(NodeType.IP, event.dst_ip)
    add(NodeType.DOMAIN, event.domain)
    add(NodeType.URL, event.url)
    if event.registry_key:
        add(NodeType.REGISTRY_KEY, event.registry_key, host=event.host)
    if event.email_from or event.email_to:
        add(
            NodeType.EMAIL,
            f"{event.email_from}->{event.email_to}:{event.email_subject}",
            display=event.email_subject,
            email_from=event.email_from,
            email_to=event.email_to,
        )
    if event.cloud_resource:
        add(NodeType.CLOUD_RESOURCE, event.cloud_resource, cloud_account=event.cloud_account)
    if event.k8s_pod:
        add(NodeType.K8S_WORKLOAD, f"{event.k8s_namespace}/{event.k8s_pod}", display=event.k8s_pod)
    for technique_id in event.technique_ids:
        add(NodeType.ATTACK_TECHNIQUE, technique_id, display=technique_id)

    return entities
