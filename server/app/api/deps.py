from __future__ import annotations
from fastapi import Request


def get_redis(request: Request):
    return getattr(request.app.state, "redis", None)
