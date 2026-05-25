"""Heuristic MITRE ATT&CK tagging for a CanonicalEvent.

This is intentionally separate from (and lighter than) the detection
service's Sigma-like rule engine: enrichment tags events with *candidate*
techniques as metadata for the graph/analyst, while the detection service
uses full rule definitions to raise alerts. Keeping both means an alert can
be generated even without an enrichment tag matching, and vice versa the
graph carries technique context on every event, not just alerted ones.
"""

from __future__ import annotations

import json
import os
import time
from pathlib import Path
from typing import Any

from aegis_common.schema.events import CanonicalEvent

_CACHE: dict[str, Any] = {"loaded_at": 0.0, "map": {}}
_TTL_SECONDS = 300


def data_dir() -> Path:
    return Path(os.getenv("AEGIS_DATA_DIR", "./data"))


def technique_catalog() -> dict[str, dict]:
    if time.time() - _CACHE["loaded_at"] > _TTL_SECONDS:
        path = data_dir() / "mitre" / "technique_map.json"
        if path.exists():
            _CACHE["map"] = json.loads(path.read_text())
        _CACHE["loaded_at"] = time.time()
    return _CACHE["map"]


def technique_name(technique_id: str) -> str:
    return technique_catalog().get(technique_id, {}).get("name", technique_id)


_KEYWORD_RULES: list[tuple[str, list[str]]] = [
    ("T1566.001", ["email_received", "attachment"]),
    ("T1566.002", ["email_link_click"]),
    ("T1204.002", ["docm", "macro"]),
    ("T1059.001", ["-enc ", "-encodedcommand", "frombase64string", "powershell"]),
    ("T1027", ["-enc ", "frombase64string", "obfuscat"]),
    ("T1003.001", ["lsass", "sekurlsa", "mimikatz", "procdump"]),
    ("T1021.002", ["admin$", "\\\\c$", "psexec", "wmic /node"]),
    ("T1570", ["wmic /node", "psexec"]),
    ("T1486", [".locked", ".encrypted", ".aegis_locked", "howtodecrypt", "how_to_decrypt"]),
    ("T1071.004", ["dns_query"]),
    ("T1078", ["logon", "valid account"]),
    ("T1098", ["root", "stoplogging", "deletetrail"]),
    ("T1562.001", ["stoplogging", "deletetrail", "disassociateencryptionconfig", "deletedetector"]),
    ("T1609", ["pods/exec"]),
    ("T1610", ["privileged", "hostpath"]),
    ("T1082", ["systeminfo", "uname -a"]),
    ("T1087", ["net user", "net group"]),
]


def infer_techniques(event: CanonicalEvent) -> list[str]:
    haystack = " ".join(
        str(v).lower()
        for v in [
            event.event_type,
            event.command_line,
            event.file_path,
            event.email_subject,
            event.url,
        ]
        if v
    )
    hits: list[str] = []
    for technique_id, keywords in _KEYWORD_RULES:
        if any(keyword.lower() in haystack for keyword in keywords):
            hits.append(technique_id)
    return sorted(set(hits))
