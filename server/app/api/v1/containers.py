from __future__ import annotations
from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import err
from app.core.ids import uid
from app.core.permissions import get_current_user, require_active_org
from app.db import get_session
from app.models import Container, ContainerItem, Org, Unit, User
from app.schemas import AddChildrenIn, ContainerChildOut, ContainerCreate, ContainerOut

router = APIRouter(tags=["containers"])


async def _out(db: AsyncSession, container: Container) -> ContainerOut:
    items = (
        await db.execute(
            select(ContainerItem).where(ContainerItem.container_id == container.id)
        )
    ).scalars().all()
    children: list[ContainerChildOut] = []
    for item in items:
        state: str | None = None
        if item.child_type == "unit":
            row = await db.get(Unit, item.child_id)
            state = row.current_state if row else None
        else:
            row = await db.get(Container, item.child_id)
            state = row.state if row else None
        children.append(ContainerChildOut(child_type=item.child_type, child_id=item.child_id, state=state))
    out = ContainerOut.model_validate(container)
    out.children = children
    return out


@router.post("/containers", response_model=ContainerOut)
async def create_container(body: ContainerCreate, user: User = Depends(get_current_user),
                           db: AsyncSession = Depends(get_session)):
    org: Org = await require_active_org(user, db)
    if org.org_type not in ("manufacturer", "regional_agent", "distributor_authorized"):
        raise err(403, "FORBIDDEN", "Only stocking tiers can create containers")
    container = Container(
        id=uid("ctr"), container_type=body.container_type,
        created_by_org_id=org.id, holder_org_id=org.id, state="ISSUED",
    )
    db.add(container)
    await db.flush()
    for unit_id in body.child_unit_ids:
        if not await db.get(Unit, unit_id):
            raise err(404, "UNIT_NOT_FOUND", f"Unit {unit_id} not found")
        db.add(ContainerItem(id=uid("cit"), container_id=container.id,
                             child_type="unit", child_id=unit_id))
    for ctr_id in body.child_container_ids:
        child = await db.get(Container, ctr_id)
        if not child:
            raise err(404, "CONTAINER_NOT_FOUND", f"Container {ctr_id} not found")
        child.parent_container_id = container.id
        db.add(ContainerItem(id=uid("cit"), container_id=container.id,
                             child_type="container", child_id=ctr_id))
    await db.commit()
    return await _out(db, container)


@router.get("/containers/{container_id}", response_model=ContainerOut)
async def get_container(container_id: str, user: User = Depends(get_current_user),
                        db: AsyncSession = Depends(get_session)):
    await require_active_org(user, db)
    container = await db.get(Container, container_id)
    if not container:
        raise err(404, "CONTAINER_NOT_FOUND", "Container not found")
    return await _out(db, container)


@router.post("/containers/{container_id}/units", response_model=ContainerOut)
async def add_children(container_id: str, body: AddChildrenIn,
                       user: User = Depends(get_current_user),
                       db: AsyncSession = Depends(get_session)):
    org: Org = await require_active_org(user, db)
    container = await db.get(Container, container_id)
    if not container:
        raise err(404, "CONTAINER_NOT_FOUND", "Container not found")
    if container.disaggregated:
        raise err(409, "CONTAINER_DISAGGREGATED", "Container was disaggregated")
    if container.holder_org_id != org.id and container.created_by_org_id != org.id:
        raise err(403, "FORBIDDEN", "Only the holding organisation can add children")
    for unit_id in body.unit_ids:
        if not await db.get(Unit, unit_id):
            raise err(404, "UNIT_NOT_FOUND", f"Unit {unit_id} not found")
        db.add(ContainerItem(id=uid("cit"), container_id=container.id,
                             child_type="unit", child_id=unit_id))
    for ctr_id in body.container_ids:
        child = await db.get(Container, ctr_id)
        if not child:
            raise err(404, "CONTAINER_NOT_FOUND", f"Container {ctr_id} not found")
        child.parent_container_id = container.id
        db.add(ContainerItem(id=uid("cit"), container_id=container.id,
                             child_type="container", child_id=ctr_id))
    await db.commit()
    return await _out(db, container)


@router.post("/containers/{container_id}/disaggregate", response_model=ContainerOut)
async def disaggregate(container_id: str, user: User = Depends(get_current_user),
                       db: AsyncSession = Depends(get_session)):
    org: Org = await require_active_org(user, db)
    container = await db.get(Container, container_id)
    if not container:
        raise err(404, "CONTAINER_NOT_FOUND", "Container not found")
    if container.holder_org_id != org.id and container.created_by_org_id != org.id:
        raise err(403, "FORBIDDEN", "Only the holding organisation can disaggregate")
    items = (
        await db.execute(
            select(ContainerItem).where(ContainerItem.container_id == container.id)
        )
    ).scalars().all()
    for item in items:
        if item.child_type == "container":
            child = await db.get(Container, item.child_id)
            if child and child.parent_container_id == container.id:
                child.parent_container_id = None
        await db.delete(item)
    container.disaggregated = True  # irreversible
    await db.commit()
    return await _out(db, container)
