"""Shared configuration and Kafka topic constants."""

from __future__ import annotations

import os

from pydantic_settings import BaseSettings, SettingsConfigDict

_SYNC_TRUE_VALUES = {"1", "true", "yes", "on", "sync"}
_SYNC_FALSE_VALUES = {"0", "false", "no", "off", "async"}


def is_sync_mode() -> bool:
    """True if the platform should run in offline/in-memory demo mode.

    Accepts both a plain boolean-ish value (``true``/``false``) and the
    docker-compose convention of ``sync``/``async`` for readability in
    ``.env`` files.
    """

    value = os.getenv("AEGIS_SYNC_MODE", "false").strip().lower()
    if value in _SYNC_FALSE_VALUES:
        return False
    return value in _SYNC_TRUE_VALUES


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    app_name: str = "AegisSOC"
    environment: str = "local"
    tenant_id: str = "default"
    log_level: str = "INFO"

    kafka_bootstrap: str = "localhost:9092"
    redis_url: str = "redis://localhost:6379/0"
    postgres_dsn: str = "postgresql+asyncpg://aegis:aegis@localhost:5432/aegis"
    neo4j_uri: str = "bolt://localhost:7687"
    neo4j_user: str = "neo4j"
    neo4j_password: str = "aegispassword"
    opensearch_url: str = "http://localhost:9200"
    object_store_path: str = "./data/lake"

    openai_api_key: str | None = None
    openai_base_url: str | None = None
    llm_model: str = "gpt-4o-mini"
    llm_enabled: bool = True
    llm_max_evidence_items: int = 40

    jwt_secret: str = "dev-only-change-me"
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 480

    otel_endpoint: str | None = None
    prometheus_port: int = 9100


# Kafka topics
TOPIC_RAW_EVENTS = "aegis.raw.events"
TOPIC_RAW_DLQ = "aegis.raw.dlq"
TOPIC_NORMALIZED = "aegis.normalized.events"
TOPIC_ENRICHED = "aegis.enriched.events"
TOPIC_GRAPH_UPDATES = "aegis.graph.updates"
TOPIC_DETECTIONS = "aegis.detections"
TOPIC_ALERTS = "aegis.alerts"
TOPIC_CASES = "aegis.cases"
TOPIC_TRIAGE = "aegis.triage.requests"
TOPIC_ACTIONS = "aegis.actions"
TOPIC_AUDIT = "aegis.audit"
TOPIC_REPLAY = "aegis.replay.events"
