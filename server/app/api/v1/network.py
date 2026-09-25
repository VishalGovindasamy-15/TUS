from __future__ import annotations
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import err
from app.core.ids import invite_code
from app.core.permissions import get_current_user, require_active_org
from app.core.time import as_aware
from app.db import get_session
from app.models import INVITE_CAPABLE_ORG_TYPES, NetworkEdge, NetworkInvite, Org, User, UserRole
from app.schemas import InviteCreate, InviteOut, TreeEdge, TreeNode, TreeOut

router = APIRouter(prefix="/network", tags=["network"])


@router.post("/invites", response_model=InviteOut)
async def create_invite(body: InviteCreate, user: User = Depends(get_current_user),
                        db: AsyncSession = Depends(get_session)):
    org = await require_active_org(user, db)
    if org.org_type not in INVITE_CAPABLE_ORG_TYPES:
        raise err(403, "FORBIDDEN", f"{org.org_type} cannot extend the network")
    if user.role != UserRole.org_admin.value:
        raise err(403, "FORBIDDEN", "Only org_admin can create invites")
    manufacturer_org_id = org.id
    if org.org_type != "manufacturer":
        inbound = (
            await db.execute(
                select(NetworkEdge).where(NetworkEdge.partner_org_id == org.id)
            )
        ).scalars().first()
        if not inbound:
            raise err(409, "NO_UPSTREAM", "No upstream manufacturer relationship found")
        manufacturer_org_id = inbound.manufacturer_org_id
    expires_at = None
    if body.expires_in_days:
        expires_at = datetime.now(timezone.utc) + timedelta(days=body.expires_in_days)
    invite = NetworkInvite(
        code=invite_code(), created_by_org_id=org.id,
        manufacturer_org_id=manufacturer_org_id,
        product_code=body.product_code, authorized=body.authorized,
        expires_at=expires_at,
    )
    db.add(invite)
    await db.commit()
    await db.refresh(invite)
    return InviteOut.model_validate(invite)


@router.post("/invites/{invite_code_str}/accept", response_model=InviteOut)
async def accept_invite(invite_code_str: str, user: User = Depends(get_current_user),
                        db: AsyncSession = Depends(get_session)):
    invite = await db.get(NetworkInvite, invite_code_str)
    now = datetime.now(timezone.utc)
    if not invite:
        raise err(404, "INVITE_NOT_FOUND", "Invite code is invalid")
    if invite.used_by_org_id:
        raise err(409, "INVITE_USED", "Invite code was already used")
    if invite.expires_at and as_aware(invite.expires_at) < now:
        raise err(410, "INVITE_EXPIRED", "Invite code has expired")
    if not user.org_id:
        raise err(409, "NO_ORG", "Create an organisation before accepting an invite")
    if user.org_id == invite.manufacturer_org_id:
        raise err(409, "SELF_INVITE", "Cannot accept your own network's invite")
    existing = (
        await db.execute(
            select(NetworkEdge).where(
                NetworkEdge.manufacturer_org_id == invite.manufacturer_org_id,
                NetworkEdge.partner_org_id == user.org_id,
            )
        )
    ).scalars().first()
    if not existing:
        db.add(
            NetworkEdge(
                manufacturer_org_id=invite.manufacturer_org_id,
                partner_org_id=user.org_id,
                product_code=invite.product_code,
                authorized=invite.authorized,
            )
        )
    invite.used_by_org_id = user.org_id
    invite.used_at = now
    await db.commit()
    await db.refresh(invite)
    return InviteOut.model_validate(invite)


@router.get("/tree", response_model=TreeOut)
async def network_tree(user: User = Depends(get_current_user),
                       db: AsyncSession = Depends(get_session)):
    org = await require_active_org(user, db)
    manufacturer_org_id: str | None = None
    if org.org_type == "manufacturer":
        manufacturer_org_id = org.id
    else:
        inbound = (
            await db.execute(
                select(NetworkEdge).where(NetworkEdge.partner_org_id == org.id)
            )
        ).scalars().first()
        if inbound:
            manufacturer_org_id = inbound.manufacturer_org_id
    if not manufacturer_org_id:
        return TreeOut(manufacturer_org_id=None)
    edges = (
        await db.execute(
            select(NetworkEdge).where(NetworkEdge.manufacturer_org_id == manufacturer_org_id)
        )
    ).scalars().all()
    org_ids = {manufacturer_org_id} | {e.partner_org_id for e in edges}
    nodes: list[TreeNode] = []
    for oid in org_ids:
        row = await db.get(Org, oid)
        if row:
            nodes.append(TreeNode(org_id=row.id, name=row.name, org_type=row.org_type))
    return TreeOut(
        manufacturer_org_id=manufacturer_org_id,
        nodes=nodes,
        edges=[
            TreeEdge(from_org_id=e.manufacturer_org_id, to_org_id=e.partner_org_id,
                     product_code=e.product_code, authorized=e.authorized)
            for e in edges
        ],
    )
