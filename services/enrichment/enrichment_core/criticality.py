"""Asset criticality enrichment from a local asset inventory JSON file."""

from __future__ import annotations

import json
import logging
import os
import time
from pathlib import Path
from typing import Any

logger = logging.getLogger("aegis.enrichment.criticality")

_CACHE: dict[str, Any] = {"loaded_at": 0.0, "data": {}}
_TTL_SECONDS = 60


def data_dir() -> Path:
    return Path(os.getenv("AEGIS_DATA_DIR", "./data"))


def _load() -> dict[str, Any]:
    path = data_dir() / "assets" / "asset_criticality.json"
    if not path.exists():
        return {"hosts": {}, "users": {}, "default_host_criticality": 0.3, "default_user_criticality": 0.3}
    return json.loads(path.read_text())


def _ensure_fresh() -> dict[str, Any]:
    if time.time() - _CACHE["loaded_at"] > _TTL_SECONDS:
        try:
            _CACHE["data"] = _load()
            _CACHE["loaded_at"] = time.time()
        except Exception:
            logger.exception("failed_to_reload_asset_inventory")
    return _CACHE["data"]


def host_criticality(host: str | None) -> tuple[float, dict]:
    data = _ensure_fresh()
    if not host:
        return data.get("default_host_criticality", 0.3), {}
    record = data.get("hosts", {}).get(host)
    if record:
        return record.get("criticality", 0.3), record
    return data.get("default_host_criticality", 0.3), {}


def user_criticality(user: str | None) -> tuple[float, dict]:
    data = _ensure_fresh()
    if not user:
        return data.get("default_user_criticality", 0.3), {}
    record = data.get("users", {}).get(user.lower())
    if record:
        return record.get("criticality", 0.3), record
    return data.get("default_user_criticality", 0.3), {}


def combined_criticality(host: str | None, user: str | None) -> float:
    h, _ = host_criticality(host)
    u, _ = user_criticality(user)
    return round(max(h, u), 3)
