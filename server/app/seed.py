"""Seed script: disclosure templates, KYC requirements, demo orgs + catalogue.

Run:  python -m app.seed
"""
from __future__ import annotations
import asyncio
import os
from datetime import date

from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.config import get_settings
from app.core.ids import uid, unit_id
from app.db import Base
import app.models  # noqa: F401
from app.models import (
    Batch, DisclosureFieldDefinition, KycRequirement, NetworkEdge, Org, Product,
    ProductDisclosure, Unit, User, UserRole,
)

settings = get_settings()

# Pharma Schedule H2, Rule 96(6)-(7) — 9 elements (Fix Plan 1.3)
PHARMA_FIELDS = [
    ("unique_product_id", "Unique Product ID (serial)", "text", True, 1),
    ("generic_name", "Generic name", "text", True, 2),
    ("brand_name", "Brand name", "text", True, 3),
    ("manufacturer_name_address", "Manufacturer name & address", "multiline", True, 4),
    ("batch_number", "Batch number", "text", True, 5),      # -> Batch.batch_number
    ("mfg_date", "Manufacturing date", "date", True, 6),     # -> Batch.mfg_date
    ("expiry_date", "Expiry date", "date", True, 7),         # -> Batch.expiry_date
    ("manufacturing_licence_number", "Manufacturing licence no.", "text", True, 8),
    ("excipients_qualitative", "Excipients (where applicable)", "text", False, 9),
]

KYC_SEEDS = [
    ("pharma", "gst_certificate", "GST Certificate", True),
    ("pharma", "drug_licence", "Drug Licence", True),
    ("pharma", "industry_license", "Industry Licence", False),
    ("auto_parts", "gst_certificate", "GST Certificate", True),
    ("auto_parts", "dealer_certificate", "Dealer Certificate", True),
    ("default", "shop_license", "Shop / Trade Licence", True),
    ("default", "other", "Other supporting document", False),
]


async def main() -> None:
    url = os.getenv("DATABASE_URL", settings.DATABASE_URL)
    engine = create_async_engine(url, future=True)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, expire_on_commit=False)

    async with factory() as db:
        # 1. disclosure templates
        for category, key, label, ftype, req, order in [("pharma", *f) for f in PHARMA_FIELDS]:
            exists = (
                await db.execute(
                    select(DisclosureFieldDefinition).where(
                        DisclosureFieldDefinition.category == category,
                        DisclosureFieldDefinition.field_key == key,
                    )
                )
            ).scalars().first()
            if not exists:
                db.add(DisclosureFieldDefinition(
                    id=uid("fld"), category=category, field_key=key, label=label,
                    field_type=ftype, required=req, display_order=order))
        # 2. KYC requirements
        for category, doctype, label, req in KYC_SEEDS:
            exists = (
                await db.execute(
                    select(KycRequirement).where(
                        KycRequirement.category == category,
                        KycRequirement.document_type == doctype,
                    )
                )
            ).scalars().first()
            if not exists:
                db.add(KycRequirement(
                    id=uid("kyc"), category=category, document_type=doctype,
                    label=label, required=req))
        await db.commit()

        # 3. demo orgs + users
        async def ensure_org(name, org_type, phone, role=UserRole.org_admin.value):
            org = (await db.execute(select(Org).where(Org.name == name))).scalars().first()
            if not org:
                org = Org(id=uid("org"), name=name, org_type=org_type,
                          approval_status="approved", categories=["pharma"])
                db.add(org)
                await db.flush()
            user = (await db.execute(select(User).where(User.phone == phone))).scalars().first()
            if not user:
                user = User(id=uid("usr"), phone=phone,
                            org_id=None if role == "platform_admin" else org.id, role=role)
                db.add(user)
            else:
                user.org_id = None if role == "platform_admin" else org.id
                user.role = role
            await db.flush()
            return org, user

        admin_org, _admin = await ensure_org(
            "TrustUs Platform", "manufacturer", settings.SEED_ADMIN_PHONE, "platform_admin")
        mfg, _mfg = await ensure_org("Acme Pharma", "manufacturer", settings.SEED_MFG_PHONE)
        dist, _dist = await ensure_org(
            "City Distributors", "distributor_authorized", settings.SEED_DIST_PHONE)
        retail, _ret = await ensure_org(
            "HealthPlus Retail", "retailer", settings.SEED_RETAIL_PHONE)
        trans, _tra = await ensure_org(
            "Swift Logistics", "transporter", settings.SEED_TRANSPORT_PHONE)
        social, _soc = await ensure_org(
            "Meds Reseller", "social_seller", settings.SEED_SOCIAL_PHONE)
        await db.commit()

        # 4. network edges (manufacturer -> partners)
        for partner in (dist, retail, trans, social):
            exists = (
                await db.execute(
                    select(NetworkEdge).where(
                        NetworkEdge.manufacturer_org_id == mfg.id,
                        NetworkEdge.partner_org_id == partner.id,
                    )
                )
            ).scalars().first()
            if not exists:
                db.add(NetworkEdge(
                    id=uid("edg"), manufacturer_org_id=mfg.id,
                    partner_org_id=partner.id, product_code=None, authorized=True))
        await db.commit()

        # 5. product + disclosures + batch + units
        product = (
            await db.execute(
                select(Product).where(Product.org_id == mfg.id, Product.product_code == "PCM500"))
        ).scalars().first()
        if not product:
            product = Product(id=uid("prd"), org_id=mfg.id, product_code="PCM500",
                              name="Paracetamol 500mg (100 tabs)", category="pharma")
            db.add(product)
            await db.flush()
        fields = (
            await db.execute(
                select(DisclosureFieldDefinition)
                .where(DisclosureFieldDefinition.category == "pharma"))
        ).scalars().all()
        demo_values = {
            "unique_product_id": "see unit QR", "generic_name": "Paracetamol",
            "brand_name": "AcmePara", "manufacturer_name_address": "Acme Pharma, Ind. Area, IN",
            "manufacturing_licence_number": "MFG/2024/001",
            "excipients_qualitative": "Starch, Povidone",
        }
        for f in fields:
            if f.field_key in ("batch_number", "mfg_date", "expiry_date"):
                continue
            exists = (
                await db.execute(
                    select(ProductDisclosure).where(
                        ProductDisclosure.product_id == product.id,
                        ProductDisclosure.field_id == f.id))
            ).scalars().first()
            if not exists:
                db.add(ProductDisclosure(id=uid("dis"), product_id=product.id,
                                         field_id=f.id,
                                         value=demo_values.get(f.field_key, "")))
        batch = (
            await db.execute(
                select(Batch).where(Batch.product_id == product.id,
                                    Batch.batch_number == "B-001"))
        ).scalars().first()
        if not batch:
            batch = Batch(id=uid("bat"), product_id=product.id, org_id=mfg.id,
                          batch_number="B-001", quantity=20,
                          mfg_date=date(2026, 1, 10), expiry_date=date(2027, 12, 31))
            db.add(batch)
            await db.flush()
            for _ in range(20):
                db.add(Unit(id=unit_id(), batch_id=batch.id, product_id=product.id,
                            current_state="ISSUED", holder_org_id=mfg.id))
        await db.commit()

        print("Seed complete.")
        print(f"  platform_admin : {settings.SEED_ADMIN_PHONE}")
        print(f"  manufacturer   : {settings.SEED_MFG_PHONE}")
        print(f"  distributor    : {settings.SEED_DIST_PHONE}")
        print(f"  retailer       : {settings.SEED_RETAIL_PHONE}")
        print(f"  transporter    : {settings.SEED_TRANSPORT_PHONE}")
        print(f"  social_seller  : {settings.SEED_SOCIAL_PHONE}")
        print("  OTPs: use debug_otp from POST /auth/otp/request (non-prod, dummy SMS).")

    await engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())
