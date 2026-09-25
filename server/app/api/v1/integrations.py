"""3PL + e-commerce webhooks (Fix Plan 9). Authenticated per-org via webhook secret,
off by default, and flowing through the same sync authorization as manual scans."""
from __future__ import annotations
from fastapi import APIRouter, Depends, Header
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_redis
from app.api.event_pipeline import submit_event, trigger_detection
from app.config import get_settings
from app.core.detection import run_detection_for_event
from app.core.errors import err
from app.core.ids import uid
from app.core.permissions import get_current_user, require_active_org
from app.db import get_session
from app.models import Event, Org, ProductListingLink, Unit, User
from app.schemas import (
    EcommerceWebhookIn, EventOut, ListingLinkCreate, ListingLinkOut, TransporterWebhookIn,
)

settings = get_settings()
router = APIRouter(tags=["integrations"])


async def _webhook_org(db: AsyncSession, org_id: str, secret: str | None) -> Org:
    org = await db.get(Org, org_id)
    if not org or not secret or secret != org.webhook_secret:
        raise err(401, "BAD_WEBHOOK_SECRET", "Invalid webhook credentials")
    if org.approval_status != "approved":
        raise err(403, "ORG_NOT_APPROVED", "Organisation is not approved")
    return org


@router.post("/integrations/webhooks/transporter/{org_id}", response_model=list[EventOut])
async def transporter_webhook(
    org_id: str,
    body: TransporterWebhookIn,
    x_webhook_secret: str | None = Header(default=None),
    db: AsyncSession = Depends(get_session),
    redis=Depends(get_redis),
):
    org = await _webhook_org(db, org_id, x_webhook_secret)
    event_type = "DISPATCH" if body.action == "pickup" else "RECEIVE"
    events: list[Event] = []
    for target_id in body.target_ids:
        events.append(
            await submit_event(
                db,
                client_event_id=f"3pl-{body.action}-{target_id}-{uid('w')}",
                target_type=body.target_type,
                target_id=target_id,
                event_type=event_type,
                actor_org_id=org.id,
                actor_user_id=None,
                gps_lat=body.gps_lat,
                gps_lng=body.gps_lng,
            )
        )
    await db.commit()
    for e in events:
        if settings.EAGER_DETECTION:
            await run_detection_for_event(db, redis, e.id)
        else:
            trigger_detection(e.id)
    return [EventOut.model_validate(e) for e in events]


@router.post("/integrations/listing-links", response_model=ListingLinkOut)
async def create_listing_link(body: ListingLinkCreate, user: User = Depends(get_current_user),
                              db: AsyncSession = Depends(get_session)):
    org = await require_active_org(user, db)
    if org.org_type != "manufacturer":
        raise err(403, "FORBIDDEN", "Only manufacturers link e-commerce SKUs")
    for unit_id in body.unit_ids:
        if not await db.get(Unit, unit_id):
            raise err(404, "UNIT_NOT_FOUND", f"Unit {unit_id} not found")
    existing = (
        await db.execute(
            select(ProductListingLink).where(
                ProductListingLink.org_id == org.id,
                ProductListingLink.channel == body.channel,
                ProductListingLink.sku == body.sku,
            )
        )
    ).scalars().first()
    if existing:
        merged = list(dict.fromkeys(existing.reserved_unit_ids + body.unit_ids))
        existing.reserved_unit_ids = merged
        await db.commit()
        return ListingLinkOut.model_validate(existing)
    link = ProductListingLink(
        id=uid("lnk"), org_id=org.id, channel=body.channel, sku=body.sku,
        reserved_unit_ids=body.unit_ids, consumed_unit_ids=[],
    )
    db.add(link)
    await db.commit()
    await db.refresh(link)
    return ListingLinkOut.model_validate(link)


@router.post("/integrations/webhooks/ecommerce/{org_id}", response_model=EventOut)
async def ecommerce_webhook(
    org_id: str,
    body: EcommerceWebhookIn,
    x_webhook_secret: str | None = Header(default=None),
    db: AsyncSession = Depends(get_session),
    redis=Depends(get_redis),
):
    org = await _webhook_org(db, org_id, x_webhook_secret)
    link = (
        await db.execute(
            select(ProductListingLink).where(
                ProductListingLink.org_id == org.id,
                ProductListingLink.channel == body.channel,
                ProductListingLink.sku == body.sku,
            )
        )
    ).scalars().first()
    if not link:
        raise err(404, "SKU_NOT_LINKED", "No listing link for this channel/SKU")
    remaining = [u for u in link.reserved_unit_ids if u not in link.consumed_unit_ids]
    if not remaining:
        raise err(409, "POOL_EMPTY", "Reserved unit pool for this SKU is exhausted")
    unit_id = remaining[0]
    event = await submit_event(
        db,
        client_event_id=f"eco-{body.channel}-{body.sku}-{unit_id}",
        target_type="unit",
        target_id=unit_id,
        event_type="DISPATCH",
        actor_org_id=org.id,
        actor_user_id=None,
        gps_lat=body.gps_lat,
        gps_lng=body.gps_lng,
    )
    link.consumed_unit_ids = link.consumed_unit_ids + [unit_id]
    await db.commit()
    await db.refresh(event)
    if settings.EAGER_DETECTION:
        await run_detection_for_event(db, redis, event.id)
    else:
        trigger_detection(event.id)
    return EventOut.model_validate(event)
