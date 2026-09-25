from __future__ import annotations
from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import err
from app.core.permissions import get_current_user, require_active_org, require_admin
from app.db import get_session
from app.models import Alert, Org, User, UserRole
from app.schemas import AlertOut, AlertPatch

router = APIRouter(tags=["alerts"])


@router.get("/alerts", response_model=list[AlertOut])
async def list_alerts(severity: str | None = None, status: str | None = None,
                      target_id: str | None = None,
                      user: User = Depends(get_current_user),
                      db: AsyncSession = Depends(get_session)):
    org: Org = await require_active_org(user, db)
    q = (
        select(Alert).where(Alert.org_id == org.id)
        .order_by(Alert.created_at.desc()).limit(500)
    )
    if severity:
        q = q.where(Alert.severity == severity)
    if status:
        q = q.where(Alert.status == status)
    if target_id:
        q = q.where(Alert.target_id == target_id)
    rows = (await db.execute(q)).scalars().all()
    return [AlertOut.model_validate(r) for r in rows]


@router.get("/alerts/{alert_id}", response_model=AlertOut)
async def get_alert(alert_id: str, user: User = Depends(get_current_user),
                    db: AsyncSession = Depends(get_session)):
    org = await require_active_org(user, db)
    alert = await db.get(Alert, alert_id)
    if not alert or (alert.org_id != org.id and user.role != UserRole.platform_admin.value):
        raise err(404, "ALERT_NOT_FOUND", "Alert not found")
    return AlertOut.model_validate(alert)


@router.patch("/alerts/{alert_id}", response_model=AlertOut)
async def patch_alert(alert_id: str, body: AlertPatch,
                      user: User = Depends(get_current_user),
                      db: AsyncSession = Depends(get_session)):
    org = await require_active_org(user, db)
    if user.role != UserRole.org_admin.value and user.role != UserRole.platform_admin.value:
        raise err(403, "FORBIDDEN", "Only org_admin can review alerts")
    alert = await db.get(Alert, alert_id)
    if not alert or (alert.org_id != org.id and user.role != UserRole.platform_admin.value):
        raise err(404, "ALERT_NOT_FOUND", "Alert not found")
    alert.status = body.status
    await db.commit()
    return AlertOut.model_validate(alert)


@router.get("/admin/alerts", response_model=list[AlertOut])
async def admin_alerts(severity: str | None = None, reason: str | None = None,
                       date_from: str | None = None, date_to: str | None = None,
                       org_type: str | None = None,
                       user: User = Depends(require_admin),
                       db: AsyncSession = Depends(get_session)):
    from app.models import Org as OrgModel
    q = select(Alert).order_by(Alert.created_at.desc()).limit(1000)
    if severity:
        q = q.where(Alert.severity == severity)
    if reason:
        q = q.where(Alert.reason == reason)
    if date_from:
        q = q.where(Alert.created_at >= date_from)
    if date_to:
        q = q.where(Alert.created_at <= date_to)
    if org_type:
        org_ids = select(OrgModel.id).where(OrgModel.org_type == org_type)
        q = q.where(Alert.org_id.in_(org_ids))
    rows = (await db.execute(q)).scalars().all()
    return [AlertOut.model_validate(r) for r in rows]
