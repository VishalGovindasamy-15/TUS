"""Celery background worker — runs the fraud detection engine off the request path."""
from __future__ import annotations
import asyncio
import os

from celery import Celery

from app.config import get_settings

settings = get_settings()

celery = Celery("trustus", broker=os.getenv("CELERY_BROKER_URL", settings.CELERY_BROKER_URL))
celery.conf.update(task_acks_late=True, worker_prefetch_multiplier=1)


@celery.task(name="app.worker.run_detection")
def run_detection(event_id: str) -> list[str]:
    from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

    from app.core.detection import run_detection_for_event

    async def _run() -> list[str]:
        url = os.getenv("DATABASE_URL", settings.DATABASE_URL)
        engine = create_async_engine(url, future=True)
        redis = None
        try:
            import redis.asyncio as redis_async

            redis = redis_async.from_url(os.getenv("REDIS_URL", settings.REDIS_URL))
        except Exception:  # noqa: BLE001
            redis = None
        try:
            factory = async_sessionmaker(engine, expire_on_commit=False)
            async with factory() as db:
                return await run_detection_for_event(db, redis, event_id)
        finally:
            if redis is not None:
                await redis.close()
            await engine.dispose()

    return asyncio.run(_run())
