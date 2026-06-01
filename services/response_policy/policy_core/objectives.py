"""Infer a coarse response objective from MITRE technique IDs / tactics so
callers (case_management, frontend_gateway demo pipeline) don't have to
duplicate ATT&CK knowledge just to get a playbook recommendation."""

from __future__ import annotations

import json
import os
from functools import lru_cache
from pathlib import Path

TACTIC_TO_OBJECTIVE = {
    "impact": "ransomware",
    "credential-access": "credential_access",
    "lateral-movement": "lateral_movement",
    "initial-access": "phishing",
    "command-and-control": "c2_beacon",
    "discovery": "recon",
    "collection": "recon",
    "persistence": "credential_access",
    "privilege-escalation": "credential_access",
    "defense-evasion": "recon",
    "execution": "recon",
}

# Highest-priority objective wins when multiple techniques map to different
# tactics (ransomware/impact is the most urgent to contain).
OBJECTIVE_PRIORITY = [
    "ransomware",
    "credential_access",
    "lateral_movement",
    "c2_beacon",
    "phishing",
    "recon",
    "benign",
]


@lru_cache(maxsize=1)
def _technique_map() -> dict:
    path = Path(os.getenv("AEGIS_DATA_DIR", "./data")) / "mitre" / "technique_map.json"
    if not path.exists():
        return {}
    return json.loads(path.read_text())


def infer_objective(technique_ids: list[str] | None, risk_score: float = 0.0) -> str:
    technique_ids = technique_ids or []
    if not technique_ids:
        return "benign" if risk_score < 0.3 else "recon"

    tmap = _technique_map()
    candidate_objectives = set()
    for tid in technique_ids:
        entry = tmap.get(tid)
        tactic = entry["tactic"] if entry else None
        objective = TACTIC_TO_OBJECTIVE.get(tactic, "recon")
        candidate_objectives.add(objective)

    for objective in OBJECTIVE_PRIORITY:
        if objective in candidate_objectives:
            return objective
    return "recon"
