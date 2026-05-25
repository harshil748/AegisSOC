"""Enrichment orchestration: MITRE tagging, criticality, identity, intel, entities."""

from __future__ import annotations

from aegis_common.schema.events import CanonicalEvent

from enrichment_core import criticality, identity, intel, mitre
from enrichment_core.entities import extract_entities


def enrich_event(event: CanonicalEvent) -> CanonicalEvent:
    event.user = identity.resolve_user(event.user)
    event.host = identity.resolve_host(event.host)

    inferred = mitre.infer_techniques(event)
    event.technique_ids = sorted(set(event.technique_ids) | set(inferred))

    event.asset_criticality = criticality.combined_criticality(event.host, event.user)

    intel_candidates = [event.src_ip, event.dst_ip, event.domain, event.url, event.file_hash]
    intel_matches = intel.match_event_indicators(intel_candidates)
    event.intel_matches = [m["matched_value"] for m in intel_matches]

    event.entities = extract_entities(event)

    host_crit, host_meta = criticality.host_criticality(event.host)
    user_crit, user_meta = criticality.user_criticality(event.user)
    event.enrichment = {
        "host_criticality": host_crit,
        "host_meta": host_meta,
        "user_criticality": user_crit,
        "user_meta": user_meta,
        "intel_hits": intel_matches,
        "technique_names": {tid: mitre.technique_name(tid) for tid in event.technique_ids},
        "entity_count": len(event.entities),
    }
    return event
