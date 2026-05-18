"""Async SQLAlchemy engine/session factory with a SQLite fallback.

Every service uses PostgreSQL in production. For local development or the
in-memory demo path (AEGIS_SYNC_MODE=true) a service can instead point at a
local SQLite file (or in-memory DB) without changing any application code -
only the DSN changes. This keeps the persistence layer real (actual SQL,
actual transactions) while removing the hard dependency on a running
Postgres instance for the single-box demo.
"""

from __future__ import annotations

import os
from contextlib import asynccontextmanager
from typing import AsyncIterator

from aegis_common.config import is_sync_mode
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    """Shared declarative base. Each service defines its own tables."""


_engines: dict[str, AsyncEngine] = {}
_sessionmakers: dict[str, async_sessionmaker[AsyncSession]] = {}


def resolve_dsn(dsn: str, service_name: str) -> str:
    """Resolve a DSN, honoring sync-mode/sqlite fallbacks.

    If AEGIS_SYNC_MODE is enabled and the DSN still points at postgres
    (i.e. the operator hasn't explicitly overridden it), fall back to a
    local SQLite file so the service works with zero external
    dependencies for demos.
    """

    override = os.getenv("AEGIS_SQLITE_FALLBACK", "true").lower() in {"1", "true", "yes"}
    if is_sync_mode() and override and dsn.startswith("postgresql"):
        os.makedirs("./data/db", exist_ok=True)
        return f"sqlite+aiosqlite:///./data/db/{service_name}.db"
    return dsn


def get_engine(dsn: str, service_name: str) -> AsyncEngine:
    resolved = resolve_dsn(dsn, service_name)
    if resolved not in _engines:
        connect_args = {}
        if resolved.startswith("sqlite"):
            connect_args["check_same_thread"] = False
        _engines[resolved] = create_async_engine(
            resolved, echo=False, future=True, connect_args=connect_args
        )
    return _engines[resolved]


def get_sessionmaker(dsn: str, service_name: str) -> async_sessionmaker[AsyncSession]:
    resolved = resolve_dsn(dsn, service_name)
    if resolved not in _sessionmakers:
        engine = get_engine(dsn, service_name)
        _sessionmakers[resolved] = async_sessionmaker(
            engine, expire_on_commit=False, class_=AsyncSession
        )
    return _sessionmakers[resolved]


@asynccontextmanager
async def session_scope(
    sessionmaker: async_sessionmaker[AsyncSession],
) -> AsyncIterator[AsyncSession]:
    async with sessionmaker() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise


async def init_models(engine: AsyncEngine, base: type[DeclarativeBase]) -> None:
    async with engine.begin() as conn:
        await conn.run_sync(base.metadata.create_all)
