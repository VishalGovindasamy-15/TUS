from __future__ import annotations
from fastapi import APIRouter, Depends, File, Form, UploadFile
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import err
from app.core.ids import uid
from app.core.permissions import (
    get_current_user, get_my_org_row, last_active_org_admin, require_active_org,
)
from app.core.storage import save_upload
from app.db import get_session
from app.models import ApprovalStatus, KycDocument, Org, User, UserRole
from app.schemas import (
    KycDocOut, NotificationSettings, OrgCreate, OrgOut, UserInviteIn, UserOut, UserPatch,
)

router = APIRouter(prefix="/orgs", tags=["orgs"])


def _org_out(org: Org, include_secret: bool) -> OrgOut:
    out = OrgOut.model_validate(org)
    out.webhook_secret = org.webhook_secret if include_secret else None
    return out


@router.post("", response_model=OrgOut)
async def create_org(body: OrgCreate, user: User = Depends(get_current_user),
                     db: AsyncSession = Depends(get_session)):
    if user.org_id:
        raise err(409, "ALREADY_IN_ORG", "User already belongs to an organisation")
    org = Org(
        id=uid("org"), name=body.name.strip(), org_type=body.org_type,
        approval_status=ApprovalStatus.pending.value,
        categories=body.categories or ["pharma"],
    )
    db.add(org)
    user.org_id = org.id
    user.role = UserRole.org_admin.value
    await db.commit()
    await db.refresh(org)
    return _org_out(org, True)


@router.get("/me", response_model=OrgOut)
async def get_my_org(user: User = Depends(get_current_user),
                     db: AsyncSession = Depends(get_session)):
    org = await get_my_org_row(user, db)
    if not org:
        raise err(404, "NO_ORG", "User has no organisation yet")
    return _org_out(org, user.role == UserRole.org_admin.value)


@router.get("/me/notification-settings", response_model=NotificationSettings)
async def get_notif_settings(org: Org = Depends(require_active_org)):
    return NotificationSettings(channels=org.notif_channels, language=org.notif_language)


@router.patch("/me/notification-settings", response_model=NotificationSettings)
async def patch_notif_settings(
    body: NotificationSettings,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_session),
):
    org = await require_active_org(user, db)
    org.notif_channels = body.channels
    org.notif_language = body.language
    await db.commit()
    return NotificationSettings(channels=org.notif_channels, language=org.notif_language)


@router.post("/me/webhook-secret/rotate", response_model=OrgOut)
async def rotate_webhook_secret(user: User = Depends(get_current_user),
                                db: AsyncSession = Depends(get_session)):
    org = await require_active_org(user, db)
    if user.role != UserRole.org_admin.value:
        raise err(403, "FORBIDDEN", "Only org_admin can rotate the webhook secret")
    org.webhook_secret = uid("whsec")
    await db.commit()
    return _org_out(org, True)


@router.post("/{org_id}/kyc-documents", response_model=KycDocOut)
async def upload_kyc(
    org_id: str,
    document_type: str = Form(...),
    file: UploadFile = File(...),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_session),
):
    if user.org_id != org_id and user.role != UserRole.platform_admin.value:
        raise err(403, "FORBIDDEN", "Can only upload KYC for your own organisation")
    org = await db.get(Org, org_id)
    if not org:
        raise err(404, "ORG_NOT_FOUND", "Organisation not found")
    content = await file.read()
    if not content:
        raise err(400, "EMPTY_FILE", "Uploaded file is empty")
    url = save_upload(content, file.filename or "kyc.bin", subdir="kyc")
    doc = KycDocument(
        id=uid("doc"), org_id=org_id, document_type=document_type.strip(),
        file_url=url, status="pending_review",
    )
    db.add(doc)
    await db.commit()
    await db.refresh(doc)
    return KycDocOut.model_validate(doc)


@router.get("/{org_id}/kyc-documents", response_model=list[KycDocOut])
async def list_kyc(org_id: str, user: User = Depends(get_current_user),
                   db: AsyncSession = Depends(get_session)):
    if user.org_id != org_id and user.role != UserRole.platform_admin.value:
        raise err(403, "FORBIDDEN", "Cannot view another organisation's documents")
    rows = (
        await db.execute(
            select(KycDocument).where(KycDocument.org_id == org_id)
            .order_by(KycDocument.uploaded_at.desc())
        )
    ).scalars().all()
    return [KycDocOut.model_validate(r) for r in rows]


@router.get("/me/users", response_model=list[UserOut])
async def list_users(user: User = Depends(get_current_user),
                     db: AsyncSession = Depends(get_session)):
    org = await require_active_org(user, db)
    rows = (
        await db.execute(select(User).where(User.org_id == org.id).order_by(User.created_at))
    ).scalars().all()
    return [UserOut.model_validate(r) for r in rows]


@router.post("/me/users/invite", response_model=UserOut)
async def invite_user(body: UserInviteIn, user: User = Depends(get_current_user),
                      db: AsyncSession = Depends(get_session)):
    org = await require_active_org(user, db)
    if user.role != UserRole.org_admin.value:
        raise err(403, "FORBIDDEN", "Only org_admin can invite staff")
    phone = body.phone.strip()
    existing = (await db.execute(select(User).where(User.phone == phone))).scalars().first()
    if existing:
        if existing.org_id and existing.org_id != org.id:
            raise err(409, "USER_ELSEWHERE", "This phone already belongs to another organisation")
        existing.org_id = org.id
        existing.role = body.role
        existing.is_active = True
        await db.commit()
        return UserOut.model_validate(existing)
    new_user = User(id=uid("usr"), phone=phone, org_id=org.id, role=body.role)
    db.add(new_user)
    await db.commit()
    return UserOut.model_validate(new_user)


@router.patch("/me/users/{user_id}", response_model=UserOut)
async def patch_user(user_id: str, body: UserPatch,
                     user: User = Depends(get_current_user),
                     db: AsyncSession = Depends(get_session)):
    org = await require_active_org(user, db)
    if user.role != UserRole.org_admin.value:
        raise err(403, "FORBIDDEN", "Only org_admin can manage staff")
    target = await db.get(User, user_id)
    if not target or target.org_id != org.id:
        raise err(404, "USER_NOT_FOUND", "User not found in your organisation")
    demoting = body.role is not None and target.role == UserRole.org_admin.value and body.role != UserRole.org_admin.value
    deactivating = body.is_active is False and target.is_active
    if (demoting or deactivating) and await last_active_org_admin(db, org.id, target.id):
        raise err(409, "LAST_ADMIN", "Cannot remove the last active org_admin")
    if body.role is not None:
        target.role = body.role
    if body.is_active is not None:
        target.is_active = body.is_active
    await db.commit()
    return UserOut.model_validate(target)
