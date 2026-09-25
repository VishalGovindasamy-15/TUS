from __future__ import annotations
from datetime import datetime, timedelta, timezone

import pyotp
from fastapi import APIRouter, Depends, Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_redis
from app.config import get_settings
from app.core.errors import err
from app.core.ids import uid
from app.core.permissions import get_current_user
from app.core.rate_limit import check_rate_limit
from app.core.security import (
    access_token, decode_token, generate_otp, hash_otp, mfa_token,
    refresh_token, sha256_hex, verify_otp_hash,
)
from app.core.sms import send_otp
from app.core.time import as_aware, utcnow
from app.db import get_session
from app.models import OtpCode, Session, User, UserRole
from app.schemas import (
    LogoutIn, MfaChallengeIn, MfaConfirmIn, MfaEnrollOut, OtpRequestIn,
    OtpRequestOut, OtpVerifyIn, RefreshIn, SessionOut, TokenOut, UserOut,
)

settings = get_settings()
router = APIRouter(prefix="/auth", tags=["auth"])

MFA_ROLES = {UserRole.org_admin.value, UserRole.platform_admin.value}


def _client_ip(request: Request) -> str:
    fwd = request.headers.get("x-forwarded-for")
    if fwd:
        return fwd.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


async def _issue_pair(db: AsyncSession, user: User, device_info: str | None) -> tuple[str, str]:
    jti = uid("jti")
    refresh = refresh_token(user.id, jti)
    db.add(
        Session(
            id=jti,
            user_id=user.id,
            refresh_hash=sha256_hex(refresh),
            device_info=device_info,
            expires_at=datetime.now(timezone.utc) + timedelta(days=settings.JWT_REFRESH_TTL_DAYS),
        )
    )
    return access_token(user.id, user.org_id, user.role), refresh


@router.post("/otp/request", response_model=OtpRequestOut)
async def otp_request(body: OtpRequestIn, request: Request,
                      db: AsyncSession = Depends(get_session),
                      redis=Depends(get_redis)):
    phone = body.phone.strip()
    if not phone:
        raise err(400, "INVALID_PHONE", "Phone number is required")
    if not await check_rate_limit(redis, f"rl:otp:phone:{phone}", settings.OTP_RATE_PER_MIN, 60):
        raise err(429, "RATE_LIMITED", "Too many OTP requests for this number")
    if not await check_rate_limit(redis, f"rl:otp:ip:{_client_ip(request)}", 20, 60):
        raise err(429, "RATE_LIMITED", "Too many OTP requests")
    otp = generate_otp()
    db.add(
        OtpCode(
            id=uid("otp"), phone=phone, otp_hash=hash_otp(otp),
            expires_at=datetime.now(timezone.utc) + timedelta(minutes=settings.OTP_TTL_MIN),
        )
    )
    await db.commit()
    await send_otp(phone, otp)
    out = OtpRequestOut()
    if not settings.is_production and settings.SMS_PROVIDER == "dummy":
        out.debug_otp = otp
    return out


@router.post("/otp/verify", response_model=TokenOut)
async def otp_verify(body: OtpVerifyIn, db: AsyncSession = Depends(get_session)):
    phone = body.phone.strip()
    q = (
        select(OtpCode)
        .where(OtpCode.phone == phone)
        .order_by(OtpCode.created_at.desc())
        .limit(1)
    )
    row = (await db.execute(q)).scalars().first()
    if not row or as_aware(row.expires_at) <= utcnow():
        raise err(401, "INVALID_OTP", "Code expired or not requested")
    if row.attempts >= settings.OTP_MAX_ATTEMPTS:
        raise err(401, "INVALID_OTP", "Too many attempts — request a new code")
    if not verify_otp_hash(body.otp.strip(), row.otp_hash):
        row.attempts += 1
        await db.commit()
        raise err(401, "INVALID_OTP", "Incorrect code")
    await db.delete(row)

    user = (await db.execute(select(User).where(User.phone == phone))).scalars().first()
    if not user:
        user = User(id=uid("usr"), phone=phone, role=UserRole.member.value)
        db.add(user)
        await db.flush()
    if not user.is_active:
        raise err(403, "USER_DEACTIVATED", "User is deactivated")

    if user.mfa_enabled and user.role in MFA_ROLES:
        await db.commit()
        return TokenOut(mfa_required=True, mfa_token=mfa_token(user.id),
                        user=UserOut.model_validate(user))
    access, refresh = await _issue_pair(db, user, body.device_info)
    await db.commit()
    return TokenOut(access_token=access, refresh_token=refresh, user=UserOut.model_validate(user))


@router.post("/mfa/enroll", response_model=MfaEnrollOut)
async def mfa_enroll(user: User = Depends(get_current_user),
                     db: AsyncSession = Depends(get_session)):
    if user.role not in MFA_ROLES:
        raise err(403, "FORBIDDEN", "MFA enrollment is for org_admin / platform_admin roles")
    secret = pyotp.random_base32()
    user.totp_secret = secret
    await db.commit()
    uri = pyotp.totp.TOTP(secret).provisioning_uri(name=user.phone, issuer_name="TrustUs")
    return MfaEnrollOut(secret=secret, otpauth_uri=uri)


@router.post("/mfa/confirm")
async def mfa_confirm(body: MfaConfirmIn, user: User = Depends(get_current_user),
                      db: AsyncSession = Depends(get_session)):
    if not user.totp_secret:
        raise err(400, "MFA_NOT_ENROLLED", "Call /auth/mfa/enroll first")
    if not pyotp.TOTP(user.totp_secret).verify(body.code.strip(), valid_window=1):
        raise err(401, "INVALID_MFA_CODE", "Incorrect authenticator code")
    user.mfa_enabled = True
    await db.commit()
    return {"mfa_enabled": True}


@router.post("/mfa/challenge", response_model=TokenOut)
async def mfa_challenge(body: MfaChallengeIn, db: AsyncSession = Depends(get_session)):
    payload = decode_token(body.mfa_token)
    if not payload or payload.get("type") != "mfa":
        raise err(401, "INVALID_MFA_TOKEN", "MFA session expired — verify OTP again")
    user = await db.get(User, payload.get("sub"))
    if not user or not user.totp_secret:
        raise err(401, "INVALID_MFA_TOKEN", "MFA is not set up for this user")
    if not pyotp.TOTP(user.totp_secret).verify(body.code.strip(), valid_window=1):
        raise err(401, "INVALID_MFA_CODE", "Incorrect authenticator code")
    access, refresh = await _issue_pair(db, user, None)
    await db.commit()
    return TokenOut(access_token=access, refresh_token=refresh, user=UserOut.model_validate(user))


@router.post("/refresh", response_model=TokenOut)
async def refresh(body: RefreshIn, db: AsyncSession = Depends(get_session)):
    payload = decode_token(body.refresh_token)
    if not payload or payload.get("type") != "refresh":
        raise err(401, "INVALID_REFRESH", "Invalid refresh token")
    session = await db.get(Session, payload.get("jti"))
    now = datetime.now(timezone.utc)
    if (
        not session
        or session.revoked_at is not None
        or as_aware(session.expires_at) < now
        or session.refresh_hash != sha256_hex(body.refresh_token)
    ):
        raise err(401, "INVALID_REFRESH", "Refresh token revoked or expired")
    user = await db.get(User, session.user_id)
    if not user or not user.is_active:
        raise err(401, "INVALID_REFRESH", "User not found or deactivated")
    session.revoked_at = now  # rotation
    access, new_refresh = await _issue_pair(db, user, session.device_info)
    await db.commit()
    return TokenOut(access_token=access, refresh_token=new_refresh,
                    user=UserOut.model_validate(user))


@router.post("/logout")
async def logout(body: LogoutIn, user: User = Depends(get_current_user),
                 db: AsyncSession = Depends(get_session)):
    now = datetime.now(timezone.utc)
    if body.refresh_token:
        payload = decode_token(body.refresh_token)
        if payload and payload.get("type") == "refresh":
            session = await db.get(Session, payload.get("jti"))
            if session and session.user_id == user.id:
                session.revoked_at = now
    else:
        rows = (
            await db.execute(
                select(Session).where(Session.user_id == user.id, Session.revoked_at.is_(None))
            )
        ).scalars().all()
        for row in rows:
            row.revoked_at = now
    await db.commit()
    return {"logged_out": True}


@router.get("/sessions", response_model=list[SessionOut])
async def list_sessions(user: User = Depends(get_current_user),
                        db: AsyncSession = Depends(get_session)):
    rows = (
        await db.execute(
            select(Session).where(Session.user_id == user.id).order_by(Session.created_at.desc())
        )
    ).scalars().all()
    return [SessionOut.model_validate(r) for r in rows]


@router.post("/sessions/{session_id}/revoke")
async def revoke_session(session_id: str, user: User = Depends(get_current_user),
                         db: AsyncSession = Depends(get_session)):
    session = await db.get(Session, session_id)
    if not session or session.user_id != user.id:
        raise err(404, "SESSION_NOT_FOUND", "Session not found")
    session.revoked_at = datetime.now(timezone.utc)
    await db.commit()
    return {"revoked": True}
