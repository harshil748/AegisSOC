"""Common FastAPI app factory: health checks, metrics, CORS, logging."""

from __future__ import annotations

import os
from typing import Any

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from aegis_common.config import is_sync_mode
from aegis_common.observability import instrument_app
from aegis_common.utils.helpers import setup_logging


def sync_mode_enabled() -> bool:
    return is_sync_mode()


def create_service_app(
    *,
    service_name: str,
    version: str = "1.0.0",
    description: str = "",
    lifespan: Any = None,
) -> FastAPI:
    setup_logging(service_name, os.getenv("LOG_LEVEL", "INFO"))
    app = FastAPI(
        title=f"AegisSOC - {service_name}",
        version=version,
        description=description,
        lifespan=lifespan,
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    instrument_app(app, service_name)

    @app.get("/health", tags=["ops"])
    async def health() -> dict:
        return {
            "status": "ok",
            "service": service_name,
            "version": version,
            "sync_mode": sync_mode_enabled(),
        }

    @app.get("/", include_in_schema=False)
    async def root() -> dict:
        return {"service": service_name, "status": "ok"}

    return app
