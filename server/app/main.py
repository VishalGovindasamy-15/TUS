"""TrustUs API — FastAPI + PostgreSQL + Redis.

Disables /docs in production. Structured logging + request-ID correlation are
configured before anything else in the app factory.
"""
from __future__ import annotations
import os
import uuid
from contextlib import asynccontextmanager

import structlog
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles

from app.api.v1 import admin, alerts, auth, containers, disclosures, events, health, integrations, network, orgs, products, social, transfers, units
from app.config import get_settings
from app.core.logging_config import configure_logging
from app.db import init_db

settings = get_settings()
configure_logging()
log = structlog.get_logger("api")


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings.validate_security()
    init_db(
        os.getenv("DATABASE_URL", settings.DATABASE_URL),
        pool_size=settings.DB_POOL_SIZE,
        max_overflow=settings.DB_MAX_OVERFLOW,
    )
    try:
        import redis.asyncio as redis_async

        client = redis_async.from_url(os.getenv("REDIS_URL", settings.REDIS_URL))
        await client.ping()
        app.state.redis = client
        log.info("redis_connected")
    except Exception as exc:  # noqa: BLE001
        app.state.redis = None
        log.warning("redis_unavailable", error=str(exc))
    os.makedirs(settings.STORAGE_DIR, exist_ok=True)
    log.info("startup", env=settings.ENV)
    yield
    if getattr(app.state, "redis", None) is not None:
        await app.state.redis.close()


def create_app() -> FastAPI:
    app = FastAPI(
        title="TrustUs API",
        version="1.0.0",
        docs_url=None if settings.is_production else "/docs",
        redoc_url=None if settings.is_production else "/redoc",
        openapi_url=None if settings.is_production else "/openapi.json",
        lifespan=lifespan,
    )

    @app.middleware("http")
    async def request_id_middleware(request: Request, call_next):
        request_id = request.headers.get("x-request-id", uuid.uuid4().hex[:12])
        structlog.contextvars.bind_contextvars(request_id=request_id)
        response = await call_next(request)
        response.headers["x-request-id"] = request_id
        structlog.contextvars.clear_contextvars()
        return response

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origin_list,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    for router in (
        admin.router, alerts.router, auth.router, containers.router, disclosures.router,
        events.router, health.router, integrations.router, network.router, orgs.router,
        products.router, social.router, transfers.router, units.router,
    ):
        app.include_router(router, prefix="/api/v1")

    @app.get("/health")
    async def root_health():
        return {"status": "ok"}

    @app.exception_handler(Exception)
    async def unhandled_handler(request: Request, exc: Exception):  # noqa: ARG001
        log.error("unhandled_exception", error=str(exc))
        return JSONResponse(
            status_code=500,
            content={"detail": {"code": "INTERNAL_ERROR", "message": "Something went wrong"}},
        )

    if os.path.isdir(settings.STORAGE_DIR):
        app.mount("/files", StaticFiles(directory=settings.STORAGE_DIR), name="files")
    return app


app = create_app()
