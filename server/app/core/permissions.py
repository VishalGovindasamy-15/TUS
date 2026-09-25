from __future__ import annotations
from fastapi import Depends, Header
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import err
from app.core.security import decode_token
from app.db import get_session
from app.models import ApprovalStatus, Org, User, UserRole


async def get_current_user(
    authorization: str | None = Header(default=None),
    db: AsyncSession = Depends(get_session),
) -> User:
    if not authorization or not authorization.lower().startswith("bearer "):
        raise err(401, "UNAUTHENTICATED", "Missing bearer token")
    payload = decode_token(authorization.split(" ", 1)[1].strip())
    if not payload or payload.get("type") != "access":
        raise err(401, "UNAUTHENTICATED", "Invalid or expired access token")
    user = await db.get(User, payload.get("sub"))
    if not user or not user.is_active:
        raise err(401, "UNAUTHENTICATED", "User not found or deactivated")
    return user


def require_role(*roles: str):
    async def dep(user: User = Depends(get_current_user)) -> User:
        if user.role not in roles:
            raise err(403, "FORBIDDEN", f"Requires role: {', '.join(roles)}")
        return user

    return dep


require_admin = require_role(UserRole.platform_admin.value)


async def require_active_org(user: User = Depends(get_current_user), db: AsyncSession = Depends(get_session)) -> Org:
    if not user.org_id:
        raise err(409, "NO_ORG", "User has no organisation yet (onboarding required)")
    org = await db.get(Org, user.org_id)
    if not org:
        raise err(409, "NO_ORG", "Organisation not found")
    if org.approval_status != ApprovalStatus.approved.value:
        raise err(403, "ORG_NOT_APPROVED", f"Organisation is {org.approval_status}")
    return org


async def get_my_org_row(user: User = Depends(get_current_user), db: AsyncSession = Depends(get_session)) -> Org | None:
    if not user.org_id:
        return None
    return await db.get(Org, user.org_id)


async def last_active_org_admin(db: AsyncSession, org_id: str, exclude_user_id: str | None = None) -> bool:
    """True if removing/demoting exclude_user_id would leave zero active org_admins."""
    q = select(User).where(
        User.org_id == org_id,
        User.role == UserRole.org_admin.value,
        User.is_active.is_(True),
    )
    if exclude_user_id:
        q = q.where(User.id != exclude_user_id)
    res = await db.execute(q)
    return res.scalars().first() is None
