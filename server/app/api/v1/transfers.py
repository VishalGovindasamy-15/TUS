from __future__ import annotations
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.event_pipeline import resolve_manufacturer
from app.core.errors import err
from app.core.ids import uid
from app.core.permissions import get_current_user, require_active_org
from app.db import get_session
from app.models import NetworkEdge, Org, TransferException, User
from app.schemas import TransferExceptionCreate, TransferExceptionOut

router = APIRouter(tags=["transfers"])


async def _has_authorized_standing(db: AsyncSession, org_id: str, manufacturer_org_id: str,
                                   product_code: str | None) -> bool:
    if org_id == manufacturer_org_id:
        return True
    q = select(NetworkEdge).where(
        NetworkEdge.manufacturer_org_id == manufacturer_org_id,
        NetworkEdge.partner_org_id == org_id,
        NetworkEdge.authorized.is_(True),
    )
    edges = (await db.execute(q)).scalars().all()
    return any(e.product_code in (None, product_code) for e in edges)


async def _grant(db: AsyncSession, org: Org, target_type: str, target_id: str,
                 body: TransferExceptionCreate) -> TransferException:
    manufacturer_org_id, product_code = await resolve_manufacturer(db, target_type, target_id)
    if not await _has_authorized_standing(db, org.id, manufacturer_org_id, product_code):
        raise err(403, "FORBIDDEN", "Only an org with authorized standing can grant exceptions")
    exc = TransferException(
        id=uid("exc"), target_type=target_type, target_id=target_id,
        granted_by_org_id=org.id, recipient_org_id=body.recipient_org_id,
        reason=body.reason.strip(),
        expires_at=datetime.now(timezone.utc) + timedelta(hours=body.expires_in_hours),
    )
    db.add(exc)
    await db.commit()
    await db.refresh(exc)
    return exc


@router.post("/units/{unit_id}/transfer-exception", response_model=TransferExceptionOut)
async def grant_unit_exception(unit_id: str, body: TransferExceptionCreate,
                               user: User = Depends(get_current_user),
                               db: AsyncSession = Depends(get_session)):
    org = await require_active_org(user, db)
    exc = await _grant(db, org, "unit", unit_id, body)
    return TransferExceptionOut.model_validate(exc)


@router.post("/containers/{container_id}/transfer-exception", response_model=TransferExceptionOut)
async def grant_container_exception(container_id: str, body: TransferExceptionCreate,
                                    user: User = Depends(get_current_user),
                                    db: AsyncSession = Depends(get_session)):
    org = await require_active_org(user, db)
    exc = await _grant(db, org, "container", container_id, body)
    return TransferExceptionOut.model_validate(exc)
