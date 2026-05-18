"""File-backed append-only event bus used as the sync-mode Kafka fallback.

Each topic is an append-only JSON-lines file under ``AEGIS_BUS_DIR``
(default ``./data/bus``). Consumer groups track their own read offset in a
sibling ``.offset`` file, mirroring Kafka's consumer-group semantics closely
enough to demo idempotent, replayable, at-least-once processing without
requiring a real broker. Writes are simple ``O_APPEND`` writes which are
atomic for line-sized payloads on POSIX, which is sufficient for demo/local
use across multiple processes/containers sharing a bind-mounted volume.
"""

from __future__ import annotations

import asyncio
import os
import time
from pathlib import Path
from typing import Any, AsyncIterator

from aegis_common.utils.helpers import json_dumps, json_loads


class EventBus:
    def __init__(self, base_dir: str | None = None) -> None:
        self.base_dir = Path(base_dir or os.getenv("AEGIS_BUS_DIR", "./data/bus"))
        (self.base_dir / "offsets").mkdir(parents=True, exist_ok=True)

    def _topic_path(self, topic: str) -> Path:
        return self.base_dir / f"{topic}.jsonl"

    def _offset_path(self, topic: str, group: str) -> Path:
        return self.base_dir / "offsets" / f"{topic}__{group}.offset"

    def publish(self, topic: str, value: dict[str, Any], key: str | None = None) -> None:
        record = {"key": key, "value": value, "ts": time.time()}
        path = self._topic_path(topic)
        with open(path, "ab") as fh:
            fh.write(json_dumps(record) + b"\n")

    def _read_offset(self, topic: str, group: str) -> int:
        path = self._offset_path(topic, group)
        if not path.exists():
            return 0
        try:
            return int(path.read_text().strip() or "0")
        except ValueError:
            return 0

    def _write_offset(self, topic: str, group: str, offset: int) -> None:
        self._offset_path(topic, group).write_text(str(offset))

    def poll(self, topic: str, group: str, max_records: int = 100) -> list[dict[str, Any]]:
        path = self._topic_path(topic)
        if not path.exists():
            return []
        offset = self._read_offset(topic, group)
        records: list[dict[str, Any]] = []
        with open(path, "rb") as fh:
            for i, line in enumerate(fh):
                if i < offset:
                    continue
                if not line.strip():
                    continue
                records.append(json_loads(line))
                if len(records) >= max_records:
                    break
        new_offset = offset + len(records)
        if records:
            self._write_offset(topic, group, new_offset)
        return records

    def lag(self, topic: str, group: str) -> int:
        path = self._topic_path(topic)
        if not path.exists():
            return 0
        with open(path, "rb") as fh:
            total = sum(1 for line in fh if line.strip())
        return max(0, total - self._read_offset(topic, group))

    async def consume_forever(
        self, topic: str, group: str, poll_interval: float = 0.5
    ) -> AsyncIterator[dict[str, Any]]:
        while True:
            records = self.poll(topic, group)
            if not records:
                await asyncio.sleep(poll_interval)
                continue
            for record in records:
                yield record


_bus: EventBus | None = None


def get_bus() -> EventBus:
    global _bus
    if _bus is None:
        _bus = EventBus()
    return _bus
