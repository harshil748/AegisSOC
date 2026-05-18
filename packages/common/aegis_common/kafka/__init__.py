"""Kafka producer/consumer helpers with an in-memory fallback bus.

When AEGIS_SYNC_MODE=true (or a Kafka broker simply isn't reachable),
services transparently fall back to a local, file-backed queue so the
platform is fully demoable on a single box without Kafka/Zookeeper.
"""

from aegis_common.kafka.bus import EventBus, get_bus
from aegis_common.kafka.consumer import AegisConsumer
from aegis_common.kafka.producer import AegisProducer

__all__ = ["EventBus", "get_bus", "AegisConsumer", "AegisProducer"]
