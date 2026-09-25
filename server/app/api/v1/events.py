from __future__ import annotations
from datetime import datetime

from fastapi import APIRouter, Depends
from sqlalchemy import and_, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_redis
from app.api.event_pipeline import submit_event, trigger_detection
from app.config import get_settings
from app.core.detection import run_detection_for_event
from app.core.errors import err
from app.core.permissions import get_current_user, require_active_org
from app.db import get_session
from app.models import Event, Org, Product, Unit, User, UserRole
from app.schemas import EventCreate, EventOut

settings = get_settings()
router = APIRouter(tags=["events"])


@router.post("/events", response_model=EventOut)
async def post_event(body: EventCreate, user: User = Depends(get_current_user),
                     db: AsyncSession = Depends(get_session),
                     redis=Depends(get_redis)):
    org_id: str | None = None
    if body.event_type in ("FLAG", "UNFLAG"):
        if user.role != UserRole.platform_admin.value:
            raise err(403, "FORBIDDEN", "FLAG/UNFLAG is restricted to platform_admin (or detection)")
        # platform_admin has no org — recorded as an org-less system action
    else:
        org: Org = await require_active_org(user, db)
        org_id = org.id
    event = await submit_event(
        db,
        client_event_id=body.client_event_id.strip(),
        target_type=body.target_type,
        target_id=body.target_id,
        event_type=body.event_type,
        actor_org_id=org_id,
        actor_user_id=user.id,
        gps_lat=body.gps_lat,
        gps_lng=body.gps_lng,
    )
    await db.commit()
    await db.refresh(event)
    if settings.EAGER_DETECTION:
        await run_detection_for_event(db, redis, event.id)
    else:
        trigger_detection(event.id)
    return EventOut.model_validate(event)


@router.get("/events", response_model=list[EventOut])
async def list_events(
    target_id: str | None = None,
    event_type: str | None = None,
    date_from: datetime | None = None,
    date_to: datetime | None = None,
    limit: int = 100,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_session),
):
    org = await require_active_org(user, db)
    limit = max(1, min(limit, 500))
    q = select(Event).order_by(Event.created_at.desc()).limit(limit)
    if user.role != UserRole.platform_admin.value:
        my_product_ids = select(Product.id).where(Product.org_id == org.id)
        my_unit_ids = select(Unit.id).where(Unit.product_id.in_(my_product_ids))
        q = q.where(
            or_(
                Event.actor_org_id == org.id,
                and_(Event.target_type == "unit", Event.target_id.in_(my_unit_ids)),
            )
        )
    if target_id:
        q = q.where(Event.target_id == target_id)
    if event_type:
        q = q.where(Event.event_type == event_type)
    if date_from:
        q = q.where(Event.created_at >= date_from)
    if date_to:
        q = q.where(Event.created_at <= date_to)
    rows = (await db.execute(q)).scalars().all()
    return [EventOut.model_validate(e) for e in rows]
