"""Database wiring for case_management."""

from __future__ import annotations

from aegis_common.db import Base, get_engine, get_sessionmaker, session_scope
from aegis_common.db.base import init_models

from case_core import models  # noqa: F401  (registers tables on Base.metadata)

SERVICE_NAME = "case_management"


def sessionmaker_for(dsn: str):
    return get_sessionmaker(dsn, SERVICE_NAME)


async def init_db(dsn: str) -> None:
    engine = get_engine(dsn, SERVICE_NAME)
    await init_models(engine, Base)


__all__ = ["sessionmaker_for", "init_db", "session_scope"]
