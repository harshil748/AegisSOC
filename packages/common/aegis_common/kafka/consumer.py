"""Unified consumer that talks to real Kafka or the sync-mode file bus."""

from __future__ import annotations

import asyncio
import logging
from typing import Any, AsyncIterator, Callable, Awaitable

from aegis_common.config import is_sync_mode
from aegis_common.kafka.bus import get_bus
from aegis_common.utils.helpers import json_loads

logger = logging.getLogger("aegis.kafka.consumer")


class AegisConsumer:
    """Async-friendly Kafka consumer with an automatic file-bus fallback."""

    def __init__(
        self,
        topic: str,
        bootstrap_servers: str,
        group_id: str,
    ) -> None:
        self.topic = topic
        self.bootstrap_servers = bootstrap_servers
        self.group_id = group_id
        self._kafka_consumer: Any | None = None
        self._sync_mode = is_sync_mode()
        self._bus = get_bus()

    async def start(self) -> None:
        if self._sync_mode:
            logger.info("consumer_sync_mode_enabled topic=%s", self.topic)
            return
        try:
            from aiokafka import AIOKafkaConsumer

            self._kafka_consumer = AIOKafkaConsumer(
                self.topic,
                bootstrap_servers=self.bootstrap_servers,
                group_id=self.group_id,
                value_deserializer=lambda v: json_loads(v),
                auto_offset_reset="earliest",
                enable_auto_commit=True,
            )
            await self._kafka_consumer.start()
            logger.info("consumer_kafka_connected topic=%s", self.topic)
        except Exception as exc:
            logger.warning("kafka_unavailable_falling_back_to_bus err=%s", exc)
            self._kafka_consumer = None
            self._sync_mode = True

    async def stop(self) -> None:
        if self._kafka_consumer is not None:
            await self._kafka_consumer.stop()

    async def poll_batch(self, max_records: int = 100) -> list[dict[str, Any]]:
        if self._kafka_consumer is not None:
            result = await self._kafka_consumer.getmany(timeout_ms=500, max_records=max_records)
            batch: list[dict[str, Any]] = []
            for records in result.values():
                for record in records:
                    batch.append(record.value)
            return batch
        records = self._bus.poll(self.topic, self.group_id, max_records=max_records)
        return [r["value"] for r in records]

    async def run(
        self,
        handler: Callable[[dict[str, Any]], Awaitable[None]],
        poll_interval: float = 1.0,
        stop_event: asyncio.Event | None = None,
    ) -> None:
        """Continuously poll and invoke ``handler`` for each message."""

        while stop_event is None or not stop_event.is_set():
            batch = await self.poll_batch()
            if not batch:
                await asyncio.sleep(poll_interval)
                continue
            for message in batch:
                try:
                    await handler(message)
                except Exception:
                    logger.exception("consumer_handler_error topic=%s", self.topic)

    def lag(self) -> int:
        if self._kafka_consumer is not None:
            return -1
        return self._bus.lag(self.topic, self.group_id)
