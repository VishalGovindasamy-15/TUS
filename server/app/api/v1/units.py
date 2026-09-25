from __future__ import annotations
import json
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, Request
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_redis
from app.config import get_settings
from app.core.detection import check_multi_location_verify, grid_cell
from app.core.errors import err
from app.core.ids import uid
from app.core.permissions import get_current_user, require_active_org
from app.core.rate_limit import check_rate_limit
from app.db import get_session
from app.models import (
    Alert, Batch, DisclosureFieldDefinition, Event, Product, ProductDisclosure,
    Unit, User, VerifySignal,
)
from app.schemas import DisclosureItemOut, EventOut, UnitOut, VerifyEventOut, VerifyOut

settings = get_settings()
router = APIRouter(tags=["units"])


def _client_ip(request: Request) -> str:
    fwd = request.headers.get("x-forwarded-for")
    if fwd:
        return fwd.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


async def _disclosures_for_product(db: AsyncSession, product: Product, batch: Batch) -> list[DisclosureItemOut]:
    fields = (
        await db.execute(
            select(DisclosureFieldDefinition)
            .where(DisclosureFieldDefinition.category == product.category)
            .order_by(DisclosureFieldDefinition.display_order)
        )
    ).scalars().all()
    if not fields:
        return []
    values = (
        await db.execute(
            select(ProductDisclosure).where(ProductDisclosure.product_id == product.id)
        )
    ).scalars().all()
    by_field = {v.field_id: v.value for v in values}
    # batch_number / mfg / expiry map to first-class Batch columns (Fix Plan 1.4)
    batch_map = {
        "batch_number": batch.batch_number,
        "mfg_date": str(batch.mfg_date) if batch.mfg_date else "",
        "expiry_date": str(batch.expiry_date) if batch.expiry_date else "",
    }
    items: list[DisclosureItemOut] = []
    for f in fields:
        value = batch_map.get(f.field_key, by_field.get(f.id, ""))
        items.append(DisclosureItemOut(field_key=f.field_key, label=f.label, value=value or ""))
    return items


async def _last_events(db: AsyncSession, unit_id: str, limit: int = 3) -> list[VerifyEventOut]:
    rows = (
        await db.execute(
            select(Event).where(Event.target_type == "unit", Event.target_id == unit_id)
            .order_by(Event.created_at.desc()).limit(limit)
        )
    ).scalars().all()
    return [
        VerifyEventOut(event_type=e.event_type, actor_org_id=e.actor_org_id,
                       timestamp=e.created_at, resulting_state=e.resulting_state)
        for e in rows
    ]


@router.get("/units/{unit_id}", response_model=UnitOut)
async def get_unit(unit_id: str, user: User = Depends(get_current_user),
                   db: AsyncSession = Depends(get_session)):
    await require_active_org(user, db)
    unit = await db.get(Unit, unit_id)
    if not unit:
        raise err(404, "UNIT_NOT_FOUND", "Unit not found")
    return UnitOut.model_validate(unit)


@router.get("/units/{unit_id}/history", response_model=list[EventOut])
async def unit_history(unit_id: str, user: User = Depends(get_current_user),
                       db: AsyncSession = Depends(get_session)):
    await require_active_org(user, db)
    unit = await db.get(Unit, unit_id)
    if not unit:
        raise err(404, "UNIT_NOT_FOUND", "Unit not found")
    rows = (
        await db.execute(
            select(Event).where(Event.target_type == "unit", Event.target_id == unit_id)
            .order_by(Event.created_at.desc()).limit(500)
        )
    ).scalars().all()
    return [EventOut.model_validate(e) for e in rows]


@router.get("/verify/{unit_id}", response_model=VerifyOut)
async def verify_unit(unit_id: str, request: Request,
                      lat: float | None = None, lng: float | None = None,
                      db: AsyncSession = Depends(get_session),
                      redis=Depends(get_redis)):
    """Public, no-login verification. Enumeration-resistant: unknown IDs get a
    generic 404; per-IP rate limit + short Redis cache (Prod Ref Section 1)."""
    if not await check_rate_limit(redis, f"rl:verify:{_client_ip(request)}",
                                  settings.VERIFY_RATE_PER_MIN, 60):
        raise err(429, "RATE_LIMITED", "Too many verification requests")
    cache_key = f"verify:{unit_id}"
    if redis is not None:
        try:
            cached = await redis.get(cache_key)
            if cached:
                return VerifyOut(**json.loads(cached))
        except Exception:  # noqa: BLE001
            pass

    unit = await db.get(Unit, unit_id)
    if not unit:
        raise err(404, "NOT_FOUND", "Invalid or unknown code")
    batch = await db.get(Batch, unit.batch_id)
    product = await db.get(Product, unit.product_id) if batch else None
    if not batch or not product:
        raise err(404, "NOT_FOUND", "Invalid or unknown code")

    event_count = (
        await db.execute(
            select(func.count()).select_from(Event)
            .where(Event.target_type == "unit", Event.target_id == unit.id)
        )
    ).scalar() or 0

    flag_reason: str | None = None
    if batch.recalled:
        status = "recalled"
    elif unit.current_state == "FLAGGED":
        status = "flagged"
        alert = (
            await db.execute(
                select(Alert).where(Alert.target_type == "unit", Alert.target_id == unit.id)
                .order_by(Alert.created_at.desc()).limit(1)
            )
        ).scalars().first()
        flag_reason = (alert.reason if alert else None) or (alert.detail if alert else None)
    elif unit.current_state == "ISSUED" and event_count == 0:
        status = "not_yet_in_circulation"
    else:
        status = "genuine"

    out = VerifyOut(
        status=status,
        unit_id=unit.id,
        product_code=product.product_code,
        product_name=product.name,
        batch_number=batch.batch_number,
        flag_reason=flag_reason,
        disclosures=await _disclosures_for_product(db, product, batch),
        last_events=await _last_events(db, unit.id),
    )

    # Anonymous aggregate counting only (Fix Plan 2.3) — never touches scan-freq.
    unit.verify_count += 1
    unit.last_verified_at = datetime.now(timezone.utc)
    if lat is not None and lng is not None:
        glat, glng = grid_cell(lat, lng)
        db.add(VerifySignal(id=uid("vrf"), unit_id=unit.id, grid_lat=glat, grid_lng=glng))
        await db.flush()
        await check_multi_location_verify(db, unit.id)
    await db.commit()

    if redis is not None:
        try:
            await redis.set(cache_key, out.model_dump_json(), ex=settings.VERIFY_CACHE_TTL_S)
        except Exception:  # noqa: BLE001
            pass
    return out
