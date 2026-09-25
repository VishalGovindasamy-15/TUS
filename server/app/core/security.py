from __future__ import annotations
import hashlib
import hmac
import secrets
from datetime import datetime, timedelta, timezone

import jwt

from app.config import get_settings
from app.core.time import utcnow

settings = get_settings()


# ------------------------------------------------------------- OTP
def generate_otp() -> str:
    return f"{secrets.randbelow(900_000) + 100_000:06d}"


def hash_otp(otp: str) -> str:
    return hmac.new(settings.JWT_SECRET.encode(), otp.encode(), hashlib.sha256).hexdigest()


def verify_otp_hash(otp: str, otp_hash: str) -> bool:
    return hmac.compare_digest(hash_otp(otp), otp_hash)


def sha256_hex(value: str) -> str:
    return hashlib.sha256(value.encode()).hexdigest()


# ------------------------------------------------------------- JWT
def _encode(payload: dict, ttl: timedelta) -> str:
    now = utcnow()
    payload = {**payload, "iat": now, "exp": now + ttl}
    return jwt.encode(payload, settings.JWT_SECRET, algorithm="HS256")


def decode_token(token: str) -> dict | None:
    try:
        return jwt.decode(token, settings.JWT_SECRET, algorithms=["HS256"])
    except jwt.PyJWTError:
        return None


def access_token(user_id: str, org_id: str | None, role: str) -> str:
    return _encode(
        {"sub": user_id, "org_id": org_id, "role": role, "type": "access"},
        timedelta(minutes=settings.JWT_ACCESS_TTL_MIN),
    )


def refresh_token(user_id: str, jti: str) -> str:
    return _encode(
        {"sub": user_id, "jti": jti, "type": "refresh"},
        timedelta(days=settings.JWT_REFRESH_TTL_DAYS),
    )


def mfa_token(user_id: str) -> str:
    return _encode({"sub": user_id, "type": "mfa"}, timedelta(minutes=5))
