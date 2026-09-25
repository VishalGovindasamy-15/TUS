from __future__ import annotations
from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import err
from app.core.ids import uid
from app.core.permissions import get_current_user, require_active_org
from app.db import get_session
from app.models import Org, SocialListing, Unit, User, UserRole
from app.schemas import SocialCreate, SocialOut

router = APIRouter(tags=["social"])


@router.post("/social-listings", response_model=SocialOut)
async def create_listing(body: SocialCreate, user: User = Depends(get_current_user),
                         db: AsyncSession = Depends(get_session)):
    org: Org = await require_active_org(user, db)
    for unit_id in body.unit_ids:
        if not await db.get(Unit, unit_id):
            raise err(404, "UNIT_NOT_FOUND", f"Unit {unit_id} not found")
    listing = SocialListing(
        id=uid("soc"), org_id=org.id, platform=body.platform,
        post_url=body.post_url.strip(), unit_ids=body.unit_ids,
    )
    db.add(listing)
    await db.commit()
    await db.refresh(listing)
    return SocialOut.model_validate(listing)


@router.get("/social-listings", response_model=list[SocialOut])
async def list_listings(user: User = Depends(get_current_user),
                        db: AsyncSession = Depends(get_session)):
    org = await require_active_org(user, db)
    rows = (
        await db.execute(
            select(SocialListing).where(SocialListing.org_id == org.id)
            .order_by(SocialListing.created_at.desc())
        )
    ).scalars().all()
    return [SocialOut.model_validate(r) for r in rows]


@router.get("/social-listings/{listing_id}", response_model=SocialOut)
async def get_listing(listing_id: str, user: User = Depends(get_current_user),
                      db: AsyncSession = Depends(get_session)):
    org = await require_active_org(user, db)
    listing = await db.get(SocialListing, listing_id)
    if not listing or (listing.org_id != org.id and user.role != UserRole.platform_admin.value):
        raise err(404, "LISTING_NOT_FOUND", "Listing not found")
    return SocialOut.model_validate(listing)


@router.delete("/social-listings/{listing_id}")
async def delete_listing(listing_id: str, user: User = Depends(get_current_user),
                         db: AsyncSession = Depends(get_session)):
    org = await require_active_org(user, db)
    listing = await db.get(SocialListing, listing_id)
    if not listing or listing.org_id != org.id:
        raise err(404, "LISTING_NOT_FOUND", "Listing not found")
    await db.delete(listing)
    await db.commit()
    return {"deleted": True}
