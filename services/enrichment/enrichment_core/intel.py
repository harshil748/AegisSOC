"""Local threat-intel feeds (MISP-style IOC list + CISA-KEV-style feed).

Feeds are loaded from ``data/intel/*.json`` and refreshed on a TTL so a demo
operator can edit the JSON files and see updated matches without restarting
the service. Live connectors (VirusTotal, real MISP API, real CISA feed)
are intentionally out of scope for the offline demo and are the one
legitimate "optional enterprise connector" TODO called out in the spec.
"""

from __future__ import annotations

import json
import logging
import os
import time
from pathlib import Path
from typing import Any

logger = logging.getLogger("aegis.enrichment.intel")

_CACHE: dict[str, Any] = {"loaded_at": 0.0, "iocs_by_value": {}, "kev_by_cve": {}}
_TTL_SECONDS = 30


def data_dir() -> Path:
    return Path(os.getenv("AEGIS_DATA_DIR", "./data"))


def _load_iocs() -> dict[str, dict]:
    path = data_dir() / "intel" / "misp_iocs.json"
    if not path.exists():
        return {}
    feed = json.loads(path.read_text())
    records = feed.get("indicators", []) if isinstance(feed, dict) else feed
    return {r["value"].lower(): r for r in records}


def _load_kev() -> dict[str, dict]:
    path = data_dir() / "intel" / "cisa_kev_sample.json"
    if not path.exists():
        return {}
    feed = json.loads(path.read_text())
    records = feed.get("vulnerabilities", []) if isinstance(feed, dict) else feed
    return {r["cve_id"]: r for r in records}


def _ensure_fresh() -> None:
    if time.time() - _CACHE["loaded_at"] > _TTL_SECONDS:
        try:
            _CACHE["iocs_by_value"] = _load_iocs()
            _CACHE["kev_by_cve"] = _load_kev()
            _CACHE["loaded_at"] = time.time()
        except Exception:
            logger.exception("failed_to_reload_intel_feeds")


def match_indicator(value: str | None) -> dict | None:
    if not value:
        return None
    _ensure_fresh()
    return _CACHE["iocs_by_value"].get(value.lower())


def all_iocs() -> list[dict]:
    _ensure_fresh()
    return list(_CACHE["iocs_by_value"].values())


def all_kev() -> list[dict]:
    _ensure_fresh()
    return list(_CACHE["kev_by_cve"].values())


def match_event_indicators(candidates: list[str | None]) -> list[dict]:
    matches = []
    for candidate in candidates:
        hit = match_indicator(candidate)
        if hit:
            matches.append({**hit, "matched_value": candidate})
    return matches
