"""Fraud detection engine (Production Reference Section 4 + Fix Plan 2.3).

Rules run on the background worker via Celery (see app/worker.py). Set
EAGER_DETECTION=true to run inline (tests / single-process dev).
"""
from __future__ import annotations
import math
from datetime import datetime, timedelta, timezone

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.core.ids import uid
from app.core.time import as_aware, utcnow
from app.core.logging_config import get_logger
from app.models import Alert, Event, NetworkEdge, Unit, VerifySignal

settings = get_settings()
log = get_logger("detection")


def haversine_km(lat1: float, lng1: float, lat2: float, lng2: float) -> float:
    r = 6371.0
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp = math.radians(lat2 - lat1)
    dl = math.radians(lng2 - lng1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * r * math.asin(math.sqrt(a))


def grid_cell(lat: float, lng: float) -> tuple[float, float]:
    return (round(lat, 1), round(lng, 1))


async def _raise_alert(
    db: AsyncSession,
    *,
    org_ids: set[str],
    target_type: str,
    target_id: str,
    reason: str,
    severity: str,
    detail: str,
) -> None:
    for org_id in {o for o in org_ids if o}:
        db.add(
            Alert(
                id=uid("alr"),
                org_id=org_id,
                target_type=target_type,
                target_id=target_id,
                reason=reason,
                severity=severity,
                status="open",
                detail=detail,
            )
        )


async def _auto_flag(db: AsyncSession, event: Event, reason: str) -> None:
    """Detection-originated FLAG: direct insert (bypasses the admin-only API guard)."""
    if event.target_type != "unit":
        return
    unit = await db.get(Unit, event.target_id)
    if not unit or unit.current_state == "FLAGGED":
        return
    unit.current_state = "FLAGGED"
    db.add(
        Event(
            id=uid("evt"),
            client_event_id=f"sys-{reason}-{event.id}",
            target_type="unit",
            target_id=unit.id,
            event_type="FLAG",
            actor_org_id=None,
            actor_user_id=None,
            resulting_state="FLAGGED",
        )
    )


async def run_detection_for_event(db: AsyncSession, redis, event_id: str) -> list[str]:
    """Apply async rules to a stored event. Returns list of reasons raised."""
    raised: list[str] = []
    event = await db.get(Event, event_id)
    if not event:
        return raised
    if event.target_type != "unit":
        return raised
    unit = await db.get(Unit, event.target_id)
    if not unit:
        return raised

    from app.models import Batch, Product  # local import to avoid cycles

    batch = await db.get(Batch, unit.batch_id)
    product = await db.get(Product, unit.product_id) if batch else None
    manufacturer_org_id = product.org_id if product else None
    scope_orgs = {manufacturer_org_id, event.actor_org_id}

    # --- rule 1: impossible_travel (uses the configurable km/h threshold) ---
    if event.gps_lat is not None and event.gps_lng is not None:
        q = (
            select(Event)
            .where(
                Event.target_type == "unit",
                Event.target_id == unit.id,
                Event.id != event.id,
                Event.gps_lat.is_not(None),
            )
            .order_by(Event.created_at.desc())
            .limit(1)
        )
        prev = (await db.execute(q)).scalars().first()
        if prev and prev.gps_lat is not None and prev.gps_lng is not None:
            km = haversine_km(prev.gps_lat, prev.gps_lng, event.gps_lat, event.gps_lng)
            hours = max(
                (event.created_at - prev.created_at).total_seconds() / 3600.0, 1 / 3600.0
            )
            if km / hours > settings.IMPOSSIBLE_TRAVEL_KMH_THRESHOLD:
                detail = f"{km:.1f}km in {hours:.2f}h ({km / hours:.0f} km/h)"
                await _raise_alert(
                    db, org_ids=scope_orgs, target_type="unit", target_id=unit.id,
                    reason="impossible_travel", severity="high", detail=detail,
                )
                await _auto_flag(db, event, "impossible_travel")
                raised.append("impossible_travel")

    # --- rule 2: unauthorized_route (soft) — edge exists but marked unauthorized ---
    if manufacturer_org_id and event.actor_org_id and event.actor_org_id != manufacturer_org_id:
        product_code = product.product_code if product else None
        q = select(NetworkEdge).where(
            NetworkEdge.manufacturer_org_id == manufacturer_org_id,
            NetworkEdge.partner_org_id == event.actor_org_id,
        )
        edges = (await db.execute(q)).scalars().all()
        scoped = [e for e in edges if e.product_code in (None, product_code)]
        if scoped and not any(e.authorized for e in scoped):
            await _raise_alert(
                db, org_ids=scope_orgs, target_type="unit", target_id=unit.id,
                reason="unauthorized_route", severity="medium",
                detail="Actor org transacts on an unauthorized-tier edge",
            )
            raised.append("unauthorized_route")

    # --- rule 3: excessive_scan_freq — per-UNIT redis counter (never verify scans) ---
    if event.event_type in ("DISPATCH", "RECEIVE", "SALE", "RETURN") and redis is not None:
        try:
            window = settings.EXCESSIVE_SCAN_WINDOW_MIN
            bucket = int(datetime.now(timezone.utc).timestamp() // (window * 60))
            key = f"scanfreq:{unit.id}:{bucket}"
            count = await redis.incr(key)
            if count == 1:
                await redis.expire(key, window * 60)
            if count > settings.EXCESSIVE_SCAN_MAX:
                await _raise_alert(
                    db, org_ids=scope_orgs, target_type="unit", target_id=unit.id,
                    reason="excessive_scan_freq", severity="medium",
                    detail=f"{count} custody scans in a {window}-minute window",
                )
                raised.append("excessive_scan_freq")
        except Exception as exc:  # noqa: BLE001
            log.error("scan_freq_counter_failed", error=str(exc))

    await db.commit()
    if raised:
        log.info("detection_raised", unit=unit.id, reasons=raised)
    return raised


async def check_multi_location_verify(db: AsyncSession, unit_id: str) -> bool:
    """Fix Plan 2.3: one retail unit verified from many distinct places is suspicious."""
    cutoff = utcnow() - timedelta(days=settings.MULTI_LOCATION_DAYS)
    rows = (
        await db.execute(select(VerifySignal).where(VerifySignal.unit_id == unit_id))
    ).scalars().all()
    cells = {(r.grid_lat, r.grid_lng) for r in rows if as_aware(r.created_at) >= cutoff}
    if len(cells) < settings.MULTI_LOCATION_MIN_CELLS:
        return False
    unit = await db.get(Unit, unit_id)
    if not unit:
        return False
    from app.models import Batch, Product

    batch = await db.get(Batch, unit.batch_id)
    product = await db.get(Product, unit.product_id) if batch else None
    await _raise_alert(
        db,
        org_ids={product.org_id if product else None},
        target_type="unit",
        target_id=unit_id,
        reason="multi_location_verify",
        severity="medium",
        detail=f"Verified from {len(cells)} distinct areas in {settings.MULTI_LOCATION_DAYS} days",
    )
    await db.commit()
    return True
