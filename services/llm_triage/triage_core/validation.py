"""Post-generation output validation: strips/flags claims not tied to evidence.

This is the safety net that applies regardless of whether the real LLM or
the mock summarizer produced the draft report: any citation that doesn't
resolve to a retrieved evidence_id is treated as unsupported and removed
from the trusted fields, and a groundedness score is computed from the
fraction of sentences that do carry a valid citation.
"""

from __future__ import annotations

import re

from aegis_common.schema.events import EvidenceItem

CITATION_RE = re.compile(r"\[([A-Za-z0-9_-]+)\]")
SENTENCE_SPLIT_RE = re.compile(r"(?<=[.!?])\s+")


def _sentences(text: str) -> list[str]:
    return [s.strip() for s in SENTENCE_SPLIT_RE.split(text) if s.strip()]


def validate_and_ground(raw: dict, evidence: list[EvidenceItem]) -> dict:
    valid_ids = {item.evidence_id for item in evidence}
    unsupported_claims = list(raw.get("unsupported_claims", []) or [])
    evidence_cited: set[str] = set()

    summary = raw.get("summary", "") or ""
    grounded_sentences = 0
    sentences = _sentences(summary)
    for sentence in sentences:
        cites = CITATION_RE.findall(sentence)
        valid_cites = [c for c in cites if c in valid_ids]
        evidence_cited.update(valid_cites)
        if valid_cites:
            grounded_sentences += 1
        elif cites:
            unsupported_claims.append(f"Unresolvable citation removed from: {sentence}")
        else:
            unsupported_claims.append(f"Uncited claim flagged: {sentence}")

    groundedness_score = round(grounded_sentences / len(sentences), 3) if sentences else 0.0

    filtered_attack_mapping = []
    for mapping in raw.get("attack_mapping", []) or []:
        eid = mapping.get("evidence_id")
        if eid in valid_ids:
            evidence_cited.add(eid)
            filtered_attack_mapping.append(mapping)
        else:
            unsupported_claims.append(
                f"Dropped ATT&CK mapping {mapping.get('technique_id')} (no valid evidence citation)"
            )

    for field in ("containment_recommendation", "confidence_explanation"):
        for cite in CITATION_RE.findall(raw.get(field, "") or ""):
            if cite in valid_ids:
                evidence_cited.add(cite)

    return {
        **raw,
        "attack_mapping": filtered_attack_mapping,
        "unsupported_claims": unsupported_claims,
        "evidence_cited": sorted(evidence_cited),
        "groundedness_score": groundedness_score,
    }
