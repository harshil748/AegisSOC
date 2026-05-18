"""Logging, hashing, time, and PII helpers."""

from __future__ import annotations

import hashlib
import logging
import re
from datetime import datetime, timezone
from typing import Any

import orjson


EMAIL_RE = re.compile(r"[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+")
IP_RE = re.compile(r"\b(?:\d{1,3}\.){3}\d{1,3}\b")


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def setup_logging(name: str, level: str = "INFO") -> logging.Logger:
    logger = logging.getLogger(name)
    if not logger.handlers:
        handler = logging.StreamHandler()
        handler.setFormatter(
            logging.Formatter(
                '{"ts":"%(asctime)s","level":"%(levelname)s","logger":"%(name)s","msg":%(message)s}'
            )
        )
        logger.addHandler(handler)
    logger.setLevel(level.upper())
    return logger


def stable_hash(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()[:32]


def json_dumps(obj: Any) -> bytes:
    return orjson.dumps(obj, option=orjson.OPT_UTC_Z)


def json_loads(data: bytes | str) -> Any:
    if isinstance(data, str):
        data = data.encode("utf-8")
    return orjson.loads(data)


def redact_pii(text: str) -> str:
    text = EMAIL_RE.sub("[REDACTED_EMAIL]", text)
    # Keep IPs for investigation value; only partially mask last octet
    def _mask_ip(m: re.Match[str]) -> str:
        parts = m.group(0).split(".")
        return f"{parts[0]}.{parts[1]}.{parts[2]}.xxx"

    return IP_RE.sub(_mask_ip, text)


def entity_id(node_type: str, key: str, tenant_id: str = "default") -> str:
    return f"{tenant_id}:{node_type}:{stable_hash(key.lower().strip())}"
