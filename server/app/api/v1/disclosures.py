from __future__ import annotations
from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import err
from app.core.ids import uid
from app.core.permissions import get_current_user, require_active_org, require_admin
from app.db import get_session
from app.models import (
    DisclosureFieldDefinition, KycRequirement, Org, Product, ProductDisclosure, User,
)
from app.schemas import (
    DisclosureFieldCreate, DisclosureFieldOut, DisclosuresPut, DisclosureItemOut,
    KycReqCreate, KycReqOut,
)

router = APIRouter(tags=["disclosures"])


@router.get("/disclosure-fields", response_model=list[DisclosureFieldOut])
async def list_fields(category: str, user: User = Depends(get_current_user),
                      db: AsyncSession = Depends(get_session)):
    await require_active_org(user, db)
    rows = (
        await db.execute(
            select(DisclosureFieldDefinition)
            .where(DisclosureFieldDefinition.category == category)
            .order_by(DisclosureFieldDefinition.display_order)
        )
    ).scalars().all()
    return [DisclosureFieldOut.model_validate(r) for r in rows]


@router.post("/disclosure-fields", response_model=DisclosureFieldOut)
async def create_field(body: DisclosureFieldCreate, user: User = Depends(require_admin),
                       db: AsyncSession = Depends(get_session)):
    existing = (
        await db.execute(
            select(DisclosureFieldDefinition).where(
                DisclosureFieldDefinition.category == body.category,
                DisclosureFieldDefinition.field_key == body.field_key,
            )
        )
    ).scalars().first()
    if existing:
        raise err(409, "FIELD_EXISTS", "Field already defined for this category")
    field = DisclosureFieldDefinition(
        id=uid("fld"), category=body.category, field_key=body.field_key,
        label=body.label, field_type=body.field_type, required=body.required,
        display_order=body.display_order,
    )
    db.add(field)
    await db.commit()
    await db.refresh(field)
    return DisclosureFieldOut.model_validate(field)


@router.put("/products/{product_id}/disclosures", response_model=list[DisclosureItemOut])
async def put_disclosures(product_id: str, body: DisclosuresPut,
                          user: User = Depends(get_current_user),
                          db: AsyncSession = Depends(get_session)):
    org: Org = await require_active_org(user, db)
    product = await db.get(Product, product_id)
    if not product or product.org_id != org.id:
        raise err(404, "PRODUCT_NOT_FOUND", "Product not found in your organisation")
    fields = (
        await db.execute(
            select(DisclosureFieldDefinition)
            .where(DisclosureFieldDefinition.category == product.category)
            .order_by(DisclosureFieldDefinition.display_order)
        )
    ).scalars().all()
    by_key = {f.field_key: f for f in fields}
    # batch_number / mfg_date / expiry_date map to first-class Batch columns
    # (Fix Plan 1.4) — never require callers to submit them as disclosure values.
    BATCH_MAPPED = {"batch_number", "mfg_date", "expiry_date"}
    missing = [
        f.field_key for f in fields
        if f.required and f.field_key not in BATCH_MAPPED and not body.values.get(f.field_key)
    ]
    if missing:
        raise err(400, "DISCLOSURE_MISSING", f"Missing required fields: {', '.join(missing)}")
    for key, value in body.values.items():
        field = by_key.get(key)
        if not field:
            raise err(400, "UNKNOWN_FIELD", f"Unknown field for category: {key}")
        row = (
            await db.execute(
                select(ProductDisclosure).where(
                    ProductDisclosure.product_id == product.id,
                    ProductDisclosure.field_id == field.id,
                )
            )
        ).scalars().first()
        if row:
            row.value = value
        else:
            db.add(ProductDisclosure(id=uid("dis"), product_id=product.id,
                                     field_id=field.id, value=value))
    await db.commit()
    return await get_disclosures(product_id, user, db)


@router.get("/products/{product_id}/disclosures", response_model=list[DisclosureItemOut])
async def get_disclosures(product_id: str, user: User = Depends(get_current_user),
                          db: AsyncSession = Depends(get_session)):
    await require_active_org(user, db)
    product = await db.get(Product, product_id)
    if not product:
        raise err(404, "PRODUCT_NOT_FOUND", "Product not found")
    fields = (
        await db.execute(
            select(DisclosureFieldDefinition)
            .where(DisclosureFieldDefinition.category == product.category)
            .order_by(DisclosureFieldDefinition.display_order)
        )
    ).scalars().all()
    values = (
        await db.execute(
            select(ProductDisclosure).where(ProductDisclosure.product_id == product.id)
        )
    ).scalars().all()
    by_field = {v.field_id: v.value for v in values}
    return [
        DisclosureItemOut(field_key=f.field_key, label=f.label, value=by_field.get(f.id, ""))
        for f in fields
    ]


@router.get("/kyc-requirements", response_model=list[KycReqOut])
async def list_kyc_requirements(category: str, user: User = Depends(get_current_user),
                                db: AsyncSession = Depends(get_session)):
    await require_active_org(user, db)
    rows = (
        await db.execute(select(KycRequirement).where(KycRequirement.category == category))
    ).scalars().all()
    return [KycReqOut.model_validate(r) for r in rows]


@router.post("/kyc-requirements", response_model=KycReqOut)
async def create_kyc_requirement(body: KycReqCreate, user: User = Depends(require_admin),
                                 db: AsyncSession = Depends(get_session)):
    existing = (
        await db.execute(
            select(KycRequirement).where(
                KycRequirement.category == body.category,
                KycRequirement.document_type == body.document_type,
            )
        )
    ).scalars().first()
    if existing:
        raise err(409, "REQUIREMENT_EXISTS", "Requirement already defined")
    row = KycRequirement(
        id=uid("kyc"), category=body.category, document_type=body.document_type,
        label=body.label, required=body.required,
    )
    db.add(row)
    await db.commit()
    await db.refresh(row)
    return KycReqOut.model_validate(row)
