from __future__ import annotations
from fastapi import APIRouter, Depends, Response
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.core.errors import err
from app.core.ids import uid, unit_id
from app.core.labels import EXPORT_FORMATS, export_csv, export_pdf_sheet, export_zpl
from app.core.permissions import get_current_user, require_active_org
from app.db import get_session
from app.models import Batch, Org, Product, Unit, User, UserRole
from app.schemas import (
    BatchCreate, BatchLookupOut, BatchOut, ExportLabelsIn, ProductCreate, ProductOut,
    RecallIn, RecallOut, UnitsGenerateIn, UnitsGeneratedOut, UnitOut,
)

settings = get_settings()
router = APIRouter(tags=["products"])


async def _units_count(db: AsyncSession, batch_id: str) -> int:
    q = select(func.count()).select_from(Unit).where(Unit.batch_id == batch_id)
    return (await db.execute(q)).scalar() or 0


def _require_manufacturer(org: Org) -> None:
    if org.org_type != "manufacturer":
        raise err(403, "FORBIDDEN", "Only manufacturer organisations manage products/batches")


@router.post("/products", response_model=ProductOut)
async def create_product(body: ProductCreate, user: User = Depends(get_current_user),
                         db: AsyncSession = Depends(get_session)):
    org = await require_active_org(user, db)
    _require_manufacturer(org)
    existing = (
        await db.execute(
            select(Product).where(Product.org_id == org.id, Product.product_code == body.product_code)
        )
    ).scalars().first()
    if existing:
        raise err(409, "PRODUCT_EXISTS", "product_code already exists for this organisation")
    product = Product(
        id=uid("prd"), org_id=org.id, product_code=body.product_code.strip(),
        name=body.name.strip(), category=body.category.strip() or "pharma",
    )
    db.add(product)
    await db.commit()
    await db.refresh(product)
    return ProductOut.model_validate(product)


@router.get("/products", response_model=list[ProductOut])
async def list_products(user: User = Depends(get_current_user),
                        db: AsyncSession = Depends(get_session)):
    org = await require_active_org(user, db)
    rows = (
        await db.execute(
            select(Product).where(Product.org_id == org.id).order_by(Product.created_at.desc())
        )
    ).scalars().all()
    return [ProductOut.model_validate(r) for r in rows]


@router.get("/batches/lookup", response_model=BatchLookupOut)
async def batch_lookup(product_code: str | None = None, batch_number: str | None = None,
                       user: User = Depends(get_current_user),
                       db: AsyncSession = Depends(get_session)):
    org = await require_active_org(user, db)
    if not product_code and not batch_number:
        raise err(400, "LOOKUP_NEEDS_PARAM", "Pass product_code and/or batch_number")
    q = select(Batch, Product).join(Product, Batch.product_id == Product.id)
    if user.role != UserRole.platform_admin.value:
        q = q.where(Batch.org_id == org.id)
    if product_code:
        q = q.where(Product.product_code == product_code)
    if batch_number:
        q = q.where(Batch.batch_number == batch_number)
    row = (await db.execute(q)).first()
    if not row:
        raise err(404, "BATCH_NOT_FOUND", "No matching batch")
    batch, product = row
    out = BatchOut.model_validate(batch)
    out.units_generated = await _units_count(db, batch.id)
    return BatchLookupOut(batch=out, product=ProductOut.model_validate(product),
                          units_generated=out.units_generated)


@router.post("/batches", response_model=BatchOut)
async def create_batch(body: BatchCreate, user: User = Depends(get_current_user),
                       db: AsyncSession = Depends(get_session)):
    org = await require_active_org(user, db)
    _require_manufacturer(org)
    product = await db.get(Product, body.product_id)
    if not product or product.org_id != org.id:
        raise err(404, "PRODUCT_NOT_FOUND", "Product not found in your organisation")
    existing = (
        await db.execute(
            select(Batch).where(Batch.product_id == product.id,
                                Batch.batch_number == body.batch_number)
        )
    ).scalars().first()
    if existing:
        raise err(409, "BATCH_EXISTS", "batch_number already exists for this product")
    batch = Batch(
        id=uid("bat"), product_id=product.id, org_id=org.id,
        batch_number=body.batch_number.strip(), quantity=body.quantity,
        mfg_date=body.mfg_date, expiry_date=body.expiry_date,
    )
    db.add(batch)
    await db.commit()
    await db.refresh(batch)
    out = BatchOut.model_validate(batch)
    out.units_generated = 0
    return out


@router.get("/batches/{batch_id}", response_model=BatchOut)
async def get_batch(batch_id: str, user: User = Depends(get_current_user),
                    db: AsyncSession = Depends(get_session)):
    org = await require_active_org(user, db)
    batch = await db.get(Batch, batch_id)
    if not batch:
        raise err(404, "BATCH_NOT_FOUND", "Batch not found")
    if user.role != UserRole.platform_admin.value and batch.org_id != org.id:
        raise err(403, "FORBIDDEN", "Batch belongs to another organisation")
    out = BatchOut.model_validate(batch)
    out.units_generated = await _units_count(db, batch.id)
    return out


@router.get("/batches/{batch_id}/units", response_model=list[UnitOut])
async def list_batch_units(batch_id: str, user: User = Depends(get_current_user),
                           db: AsyncSession = Depends(get_session)):
    org = await require_active_org(user, db)
    batch = await db.get(Batch, batch_id)
    if not batch:
        raise err(404, "BATCH_NOT_FOUND", "Batch not found")
    if user.role != UserRole.platform_admin.value and batch.org_id != org.id:
        raise err(403, "FORBIDDEN", "Batch belongs to another organisation")
    rows = (
        await db.execute(select(Unit).where(Unit.batch_id == batch_id).order_by(Unit.created_at))
    ).scalars().all()
    return [UnitOut.model_validate(r) for r in rows]


@router.post("/batches/{batch_id}/units", response_model=UnitsGeneratedOut)
async def generate_units(batch_id: str, body: UnitsGenerateIn,
                         user: User = Depends(get_current_user),
                         db: AsyncSession = Depends(get_session)):
    org = await require_active_org(user, db)
    _require_manufacturer(org)
    batch = await db.get(Batch, batch_id)
    if not batch or batch.org_id != org.id:
        raise err(404, "BATCH_NOT_FOUND", "Batch not found in your organisation")
    count = body.count or batch.quantity
    ids: list[str] = []
    for _ in range(count):
        new_id = unit_id()
        db.add(Unit(id=new_id, batch_id=batch.id, product_id=batch.product_id,
                    current_state="ISSUED", holder_org_id=org.id))
        ids.append(new_id)
    await db.commit()
    return UnitsGeneratedOut(unit_ids=ids)


@router.post("/batches/{batch_id}/recall", response_model=RecallOut)
async def recall_batch(batch_id: str, body: RecallIn,
                       user: User = Depends(get_current_user),
                       db: AsyncSession = Depends(get_session)):
    org = await require_active_org(user, db)
    _require_manufacturer(org)
    if user.role != UserRole.org_admin.value:
        raise err(403, "FORBIDDEN", "Only org_admin can initiate a recall")
    batch = await db.get(Batch, batch_id)
    if not batch or batch.org_id != org.id:
        raise err(404, "BATCH_NOT_FOUND", "Batch not found in your organisation")
    batch.recalled = True
    batch.recall_reason = body.reason.strip()
    affected_units = await _units_count(db, batch.id)
    holders = (
        await db.execute(
            select(Unit.holder_org_id).where(Unit.batch_id == batch.id).distinct()
        )
    ).all()
    notified = len({h[0] for h in holders if h[0] and h[0] != org.id})
    await db.commit()
    return RecallOut(affected_units=affected_units, affected_orgs_notified=notified)


@router.post("/batches/{batch_id}/export-labels")
async def export_labels(batch_id: str, body: ExportLabelsIn,
                        user: User = Depends(get_current_user),
                        db: AsyncSession = Depends(get_session)):
    org = await require_active_org(user, db)
    _require_manufacturer(org)
    if body.format not in EXPORT_FORMATS:
        raise err(400, "BAD_FORMAT", f"format must be one of {EXPORT_FORMATS}")
    batch = await db.get(Batch, batch_id)
    if not batch or batch.org_id != org.id:
        raise err(404, "BATCH_NOT_FOUND", "Batch not found in your organisation")
    rows = (
        await db.execute(select(Unit.id).where(Unit.batch_id == batch.id).order_by(Unit.created_at))
    ).all()
    ids = [r[0] for r in rows]
    if not ids:
        raise err(409, "NO_UNITS", "Generate units before exporting labels")
    base = batch.batch_number.replace(" ", "_")
    if body.format == "csv":
        return Response(
            export_csv(ids, settings.PUBLIC_WEB_URL), media_type="text/csv",
            headers={"Content-Disposition": f"attachment; filename={base}_labels.csv"},
        )
    if body.format == "pdf_sheet":
        return Response(
            export_pdf_sheet(ids, settings.PUBLIC_WEB_URL, size_mm=body.size_mm),
            media_type="application/pdf",
            headers={"Content-Disposition": f"attachment; filename={base}_labels.pdf"},
        )
    return Response(
        export_zpl(ids, settings.PUBLIC_WEB_URL, size_mm=body.size_mm),
        media_type="text/plain",
        headers={"Content-Disposition": f"attachment; filename={base}_labels.zpl"},
    )
