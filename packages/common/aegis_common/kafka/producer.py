"""Unified producer that talks to real Kafka or the sync-mode file bus."""

from __future__ import annotations

import logging
from typing import Any

from aegis_common.config import is_sync_mode
from aegis_common.kafka.bus import get_bus
from aegis_common.utils.helpers import json_dumps

logger = logging.getLogger("aegis.kafka.producer")


class AegisProducer:
    """Async-friendly Kafka producer with an automatic file-bus fallback.

    Usage::

        producer = AegisProducer(bootstrap_servers="localhost:9092")
        await producer.start()
        await producer.send("aegis.raw.events", value={...}, key="evt-1")
        await producer.stop()
    """

    def __init__(self, bootstrap_servers: str, client_id: str = "aegis") -> None:
        self.bootstrap_servers = bootstrap_servers
        self.client_id = client_id
        self._kafka_producer: Any | None = None
        self._sync_mode = is_sync_mode()
        self._bus = get_bus()

    async def start(self) -> None:
        if self._sync_mode:
            logger.info("producer_sync_mode_enabled")
            return
        try:
            from aiokafka import AIOKafkaProducer

            self._kafka_producer = AIOKafkaProducer(
                bootstrap_servers=self.bootstrap_servers,
                client_id=self.client_id,
                value_serializer=lambda v: json_dumps(v),
                key_serializer=lambda k: k.encode("utf-8") if k else None,
            )
            await self._kafka_producer.start()
            logger.info("producer_kafka_connected")
        except Exception as exc:  # broker unavailable -> demo fallback
            logger.warning("kafka_unavailable_falling_back_to_bus err=%s", exc)
            self._kafka_producer = None
            self._sync_mode = True

    async def stop(self) -> None:
        if self._kafka_producer is not None:
            await self._kafka_producer.stop()

    async def send(self, topic: str, value: dict[str, Any], key: str | None = None) -> None:
        if self._kafka_producer is not None:
            await self._kafka_producer.send_and_wait(topic, value=value, key=key)
        else:
            self._bus.publish(topic, value, key=key)

    async def send_dlq(self, dlq_topic: str, original_topic: str, payload: Any, error: str) -> None:
        await self.send(
            dlq_topic,
            value={"original_topic": original_topic, "payload": payload, "error": error},
        )
