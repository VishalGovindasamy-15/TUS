from __future__ import annotations
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import err
from app.core.ids import uid
from app.core.permissions import require_admin
from app.core.time import as_aware
from app.db import get_session
from app.models import Alert, ApprovalStatus, Batch, KycDocument, Org, RegulatorGrant, User
from app.schemas import (
    AdminOrgOut, FraudPatternsOut, KycDocOut, OrgOut, RegulatorGrantCreate, RegulatorGrantOut,
    RejectIn,
)

router = APIRouter(prefix="/admin", tags=["admin"])


async def _admin_org_out(db, org: Org) -> AdminOrgOut:
    docs = (
        await db.execute(
            select(KycDocument).where(KycDocument.org_id == org.id)
            .order_by(KycDocument.uploaded_at.desc())
        )
    ).scalars().all()
    out = AdminOrgOut.model_validate(org)
    out.kyc_documents = [KycDocOut.model_validate(d) for d in docs]
    return out


@router.get("/orgs", response_model=list[AdminOrgOut])
async def list_orgs(status: str | None = None, user: User = Depends(require_admin),
                    db: AsyncSession = Depends(get_session)):
    q = select(Org).order_by(Org.created_at.desc()).limit(500)
    if status:
        q = q.where(Org.approval_status == status)
    rows = (await db.execute(q)).scalars().all()
    return [await _admin_org_out(db, r) for r in rows]


@router.post("/orgs/{org_id}/approve", response_model=OrgOut)
async def approve_org(org_id: str, user: User = Depends(require_admin),
                      db: AsyncSession = Depends(get_session)):
    org = await db.get(Org, org_id)
    if not org:
        raise err(404, "ORG_NOT_FOUND", "Organisation not found")
    org.approval_status = ApprovalStatus.approved.value
    org.rejection_reason = None
    await db.commit()
    out = OrgOut.model_validate(org)
    out.webhook_secret = None
    return out


@router.post("/orgs/{org_id}/reject", response_model=OrgOut)
async def reject_org(org_id: str, body: RejectIn, user: User = Depends(require_admin),
                     db: AsyncSession = Depends(get_session)):
    org = await db.get(Org, org_id)
    if not org:
        raise err(404, "ORG_NOT_FOUND", "Organisation not found")
    org.approval_status = ApprovalStatus.rejected.value
    org.rejection_reason = body.reason.strip()
    await db.commit()
    out = OrgOut.model_validate(org)
    out.webhook_secret = None
    return out


@router.get("/fraud-patterns", response_model=FraudPatternsOut)
async def fraud_patterns(user: User = Depends(require_admin),
                         db: AsyncSession = Depends(get_session)):
    reasons = (
        await db.execute(
            select(Alert.reason, func.count()).group_by(Alert.reason)
            .order_by(func.count().desc()).limit(20)
        )
    ).all()
    severities = (
        await db.execute(select(Alert.severity, func.count()).group_by(Alert.severity))
    ).all()
    # by_day computed in Python for sqlite/postgres portability
    since = datetime.now(timezone.utc) - timedelta(days=14)
    stamps = (
        await db.execute(select(Alert.created_at).where(Alert.created_at >= since))
    ).scalars().all()
    by_day: dict[str, int] = {}
    for stamp in stamps:
        day = as_aware(stamp).astimezone(timezone.utc).date().isoformat()
        by_day[day] = by_day.get(day, 0) + 1
    return FraudPatternsOut(
        top_flag_reasons=[{"reason": r, "count": c} for r, c in reasons],
        by_severity=[{"severity": s, "count": c} for s, c in severities],
        by_day=[{"day": d, "count": by_day[d]} for d in sorted(by_day)],
    )


@router.post("/regulator-access", response_model=RegulatorGrantOut)
async def grant_regulator_access(body: RegulatorGrantCreate, user: User = Depends(require_admin),
                                 db: AsyncSession = Depends(get_session)):
    batch = await db.get(Batch, body.batch_id)
    if not batch:
        raise err(404, "BATCH_NOT_FOUND", "Batch not found")
    grant = RegulatorGrant(
        id=uid("reg"), regulator_user_id=body.regulator_user_id.strip(),
        batch_id=batch.id, reason=body.reason.strip(),
        expires_at=datetime.now(timezone.utc) + timedelta(hours=body.expires_in_hours),
    )
    db.add(grant)
    await db.commit()
    await db.refresh(grant)
    return RegulatorGrantOut.model_validate(grant)


@router.get("/regulator-access", response_model=list[RegulatorGrantOut])
async def list_regulator_access(user: User = Depends(require_admin),
                                db: AsyncSession = Depends(get_session)):
    rows = (
        await db.execute(select(RegulatorGrant).order_by(RegulatorGrant.created_at.desc()).limit(500))
    ).scalars().all()
    return [RegulatorGrantOut.model_validate(r) for r in rows]


@router.post("/regulator-access/{grant_id}/revoke", response_model=RegulatorGrantOut)
async def revoke_regulator_access(grant_id: str, user: User = Depends(require_admin),
                                  db: AsyncSession = Depends(get_session)):
    grant = await db.get(RegulatorGrant, grant_id)
    if not grant:
        raise err(404, "GRANT_NOT_FOUND", "Grant not found")
    grant.revoked_at = datetime.now(timezone.utc)
    await db.commit()
    return RegulatorGrantOut.model_validate(grant)
