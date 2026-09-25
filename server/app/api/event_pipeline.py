"""Shared custody-event submission pipeline (Fix Plan 2.1).

Used identically by POST /events and both machine webhooks so manual scans and
integrations pass through the same synchronous authorization check.
"""
from __future__ import annotations
from datetime import datetime, timezone

from sqlalchemy import and_, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.core.errors import err
from app.core.ids import uid
from app.core.state_machine import InvalidTransition, apply_transition
from app.core.time import as_aware, utcnow
from app.models import (
    Batch, Container, Event, NetworkEdge, Product, TransferException, Unit,
)

settings = get_settings()


async def resolve_manufacturer(
    db: AsyncSession, target_type: str, target_id: str
) -> tuple[str, str | None]:
    """Return (manufacturer_org_id, product_code|None) for a unit or container."""
    if target_type == "unit":
        unit = await db.get(Unit, target_id)
        if not unit:
            raise err(404, "TARGET_NOT_FOUND", "Unit not found")
        product = await db.get(Product, unit.product_id)
        if not product:
            raise err(404, "TARGET_NOT_FOUND", "Unit product not found")
        return product.org_id, product.product_code
    container = await db.get(Container, target_id)
    if not container:
        raise err(404, "TARGET_NOT_FOUND", "Container not found")
    return container.created_by_org_id, None


async def authorize_custody(
    db: AsyncSession,
    *,
    target_type: str,
    target_id: str,
    actor_org_id: str,
    manufacturer_org_id: str,
    product_code: str | None,
) -> None:
    """Synchronous authorization — raise 403 unless allowed (Fix Plan 2.1)."""
    if actor_org_id == manufacturer_org_id:
        return
    now = utcnow()
    q = select(TransferException).where(
        TransferException.target_type == target_type,
        TransferException.target_id == target_id,
        TransferException.recipient_org_id == actor_org_id,
        TransferException.used_at.is_(None),
    )
    candidates = (await db.execute(q)).scalars().all()
    live = next((e for e in candidates if as_aware(e.expires_at) > now), None)
    if live:
        live.used_at = now  # single-use
        return
    edge_q = select(NetworkEdge).where(
        NetworkEdge.manufacturer_org_id == manufacturer_org_id,
        NetworkEdge.partner_org_id == actor_org_id,
        or_(
            NetworkEdge.product_code.is_(None),
            NetworkEdge.product_code == product_code,
        ) if product_code else NetworkEdge.product_code.is_(None),
    )
    edge = (await db.execute(edge_q)).scalars().first()
    if edge:
        return  # soft case (unauthorized tier) is flagged async, never blocked
    raise err(
        403, "UNAUTHORIZED_ROUTE",
        "No network relationship with the manufacturer for this product",
    )


async def submit_event(
    db: AsyncSession,
    *,
    client_event_id: str,
    target_type: str,
    target_id: str,
    event_type: str,
    actor_org_id: str | None,
    actor_user_id: str | None,
    gps_lat: float | None = None,
    gps_lng: float | None = None,
    skip_authz: bool = False,
) -> Event:
    """Validate, authorize, apply, and persist a custody event (no commit)."""
    existing = (
        await db.execute(select(Event).where(Event.client_event_id == client_event_id))
    ).scalars().first()
    if existing:
        return existing  # idempotent retry

    manufacturer_org_id, product_code = await resolve_manufacturer(db, target_type, target_id)
    if actor_org_id and not skip_authz:
        await authorize_custody(
            db,
            target_type=target_type,
            target_id=target_id,
            actor_org_id=actor_org_id,
            manufacturer_org_id=manufacturer_org_id,
            product_code=product_code,
        )

    if target_type == "unit":
        target = await db.get(Unit, target_id)
        current = target.current_state
    else:
        target = await db.get(Container, target_id)
        if target.disaggregated:
            raise err(409, "CONTAINER_DISAGGREGATED", "Container was disaggregated")
        current = target.state

    try:
        resulting = apply_transition(current, event_type)
    except InvalidTransition as exc:
        raise err(409, "INVALID_TRANSITION", str(exc))

    if target_type == "unit":
        target.current_state = resulting
        if actor_org_id:
            target.holder_org_id = actor_org_id
    else:
        target.state = resulting
        if actor_org_id:
            target.holder_org_id = actor_org_id

    event = Event(
        id=uid("evt"),
        client_event_id=client_event_id,
        target_type=target_type,
        target_id=target_id,
        event_type=event_type,
        actor_org_id=actor_org_id,
        actor_user_id=actor_user_id,
        gps_lat=gps_lat,
        gps_lng=gps_lng,
        resulting_state=resulting,
    )
    db.add(event)
    return event


def trigger_detection(event_id: str) -> None:
    """Enqueue async detection, or run inline when EAGER_DETECTION=true.

    Inline mode is executed by the caller (which owns the DB session); here we only
    enqueue the Celery task. Callers check settings.EAGER_DETECTION themselves.
    """
    if settings.EAGER_DETECTION:
        return
    try:
        from app.worker import celery  # deferred: celery import is optional at runtime
        celery.send_task("app.worker.run_detection", args=[event_id])
    except Exception:  # noqa: BLE001 - detection must never break event submission
        pass
