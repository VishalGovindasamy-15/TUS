from __future__ import annotations
from typing import Any


async def check_rate_limit(redis: Any | None, key: str, limit: int, window_s: int) -> bool:
    """Fixed-window rate limit. Fail-open when Redis is unavailable (logged by caller)."""
    if redis is None:
        return True
    try:
        count = await redis.incr(key)
        if count == 1:
            await redis.expire(key, window_s)
        return count <= limit
    except Exception:
        return True
