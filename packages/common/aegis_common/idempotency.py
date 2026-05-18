"""Lightweight SQLite-backed idempotency store.

Used by services that must guarantee at-most-once side effects for a given
key (e.g. ``event_id``) even though the underlying transport (Kafka or the
sync-mode file bus) only guarantees at-least-once delivery.
"""

from __future__ import annotations

import os
import sqlite3
import threading
import time
from pathlib import Path


class IdempotencyStore:
    def __init__(self, db_path: str, ttl_seconds: int = 7 * 24 * 3600) -> None:
        Path(db_path).parent.mkdir(parents=True, exist_ok=True)
        self.ttl_seconds = ttl_seconds
        self._lock = threading.Lock()
        self._conn = sqlite3.connect(db_path, check_same_thread=False)
        self._conn.execute(
            "CREATE TABLE IF NOT EXISTS seen_keys (key TEXT PRIMARY KEY, seen_at REAL)"
        )
        self._conn.commit()

    def seen_before(self, key: str) -> bool:
        """Return True if key was already seen; records it if not (atomic check-and-set)."""

        now = time.time()
        with self._lock:
            cur = self._conn.execute("SELECT seen_at FROM seen_keys WHERE key = ?", (key,))
            row = cur.fetchone()
            if row is not None:
                return True
            self._conn.execute(
                "INSERT INTO seen_keys (key, seen_at) VALUES (?, ?)", (key, now)
            )
            self._conn.commit()
            return False

    def cleanup_expired(self) -> int:
        cutoff = time.time() - self.ttl_seconds
        with self._lock:
            cur = self._conn.execute("DELETE FROM seen_keys WHERE seen_at < ?", (cutoff,))
            self._conn.commit()
            return cur.rowcount

    def close(self) -> None:
        self._conn.close()


def default_store(service_name: str) -> IdempotencyStore:
    base = os.getenv("AEGIS_IDEMPOTENCY_DIR", "./data/idempotency")
    return IdempotencyStore(os.path.join(base, f"{service_name}.db"))
