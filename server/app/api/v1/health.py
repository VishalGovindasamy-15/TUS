from __future__ import annotations
from fastapi import APIRouter, Depends
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_redis
from app.db import get_session

router = APIRouter(tags=["health"])


@router.get("/health")
async def health(db: AsyncSession = Depends(get_session), redis=Depends(get_redis)):
    db_ok = True
    try:
        await db.execute(text("SELECT 1"))
    except Exception:  # noqa: BLE001
        db_ok = False
    redis_ok: bool | None = None
    if redis is not None:
        try:
            await redis.ping()
            redis_ok = True
        except Exception:  # noqa: BLE001
            redis_ok = False
    return {"status": "ok" if db_ok else "degraded", "db": db_ok, "redis": redis_ok}
