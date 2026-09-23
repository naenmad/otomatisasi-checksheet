"""
Checksheets API Router.
"""
from typing import List, Optional
from pydantic import BaseModel
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, delete

from database.connection import get_db
from database.models import Checksheet, InspectionPoint
from database.crud import list_checksheets, get_checksheet_by_id

router = APIRouter(prefix="/api/checksheets", tags=["Checksheets"])


class InspectionPointSchema(BaseModel):
    item_no: str
    inspection_item: str
    standard: str = "-"
    method: str = "Visual"
    master_data: Optional[str] = ""


class ChecksheetUpdateSchema(BaseModel):
    part_name: Optional[str] = None
    model: Optional[str] = None
    customer: Optional[str] = None
    doc_number: Optional[str] = None
    status: Optional[str] = None
    assigned_to: Optional[str] = None
    keterangan: Optional[str] = None


class ChecksheetPointsUpdateSchema(BaseModel):
    points: List[InspectionPointSchema]


@router.get("")
async def get_checksheets(
    assigned_to: Optional[str] = Query(None, description="Filter by assignee: Zul, Iqbal, Rama, Yogi"),
    status: Optional[str] = Query(None, description="Filter by status: Checksheet Done, Belum Di Input, Tidak Ada Part"),
    search: Optional[str] = Query(None, description="Search part number or name"),
    limit: int = 150,
    offset: int = 0,
    db: AsyncSession = Depends(get_db)
):
    items = await list_checksheets(
        session=db,
        assigned_to=assigned_to,
        status=status,
        search=search,
        limit=limit,
        offset=offset
    )
    return [
        {
            "id": cs.id,
            "part_number": cs.part_number,
            "part_name": cs.part_name,
            "model": cs.model,
            "customer": cs.customer,
            "doc_number": cs.doc_number,
            "status": cs.status,
            "assigned_to": cs.assigned_to,
            "keterangan": cs.keterangan,
            "points_count": len(cs.inspection_points),
            "images_count": len(cs.images),
            "factoryhub_url": cs.factoryhub_url,
            "updated_at": cs.updated_at.isoformat() if cs.updated_at else None
        }
        for cs in items
    ]


@router.get("/{checksheet_id}")
async def get_checksheet_detail(checksheet_id: int, db: AsyncSession = Depends(get_db)):
    cs = await get_checksheet_by_id(db, checksheet_id)
    if not cs:
        raise HTTPException(status_code=404, detail="Checksheet not found")

    return {
        "id": cs.id,
        "part_number": cs.part_number,
        "part_name": cs.part_name,
        "model": cs.model,
        "customer": cs.customer,
        "doc_number": cs.doc_number,
        "status": cs.status,
        "assigned_to": cs.assigned_to,
        "keterangan": cs.keterangan,
        "factoryhub_url": cs.factoryhub_url,
        "points": [
            {
                "id": p.id,
                "item_no": p.item_no,
                "inspection_item": p.inspection_item,
                "standard": p.standard,
                "method": p.method,
                "master_data": p.master_data or ""
            }
            for p in cs.inspection_points
        ],
        "images": [
            {
                "id": img.id,
                "image_url": img.image_url,
                "image_path": img.image_path
            }
            for img in cs.images
        ]
    }


@router.put("/{checksheet_id}")
async def update_checksheet(checksheet_id: int, payload: ChecksheetUpdateSchema, db: AsyncSession = Depends(get_db)):
    cs = await get_checksheet_by_id(db, checksheet_id)
    if not cs:
        raise HTTPException(status_code=404, detail="Checksheet not found")

    if payload.part_name is not None: cs.part_name = payload.part_name
    if payload.model is not None: cs.model = payload.model
    if payload.customer is not None: cs.customer = payload.customer
    if payload.doc_number is not None: cs.doc_number = payload.doc_number
    if payload.status is not None: cs.status = payload.status
    if payload.assigned_to is not None: cs.assigned_to = payload.assigned_to
    if payload.keterangan is not None: cs.keterangan = payload.keterangan

    await db.commit()
    await db.refresh(cs)
    return {"status": "success", "id": cs.id}


@router.put("/{checksheet_id}/points")
async def update_checksheet_points(checksheet_id: int, payload: ChecksheetPointsUpdateSchema, db: AsyncSession = Depends(get_db)):
    cs = await get_checksheet_by_id(db, checksheet_id)
    if not cs:
        raise HTTPException(status_code=404, detail="Checksheet not found")

    # Replace existing inspection points
    await db.execute(delete(InspectionPoint).where(InspectionPoint.checksheet_id == checksheet_id))

    for idx, p in enumerate(payload.points):
        ip = InspectionPoint(
            checksheet_id=checksheet_id,
            item_no=p.item_no,
            inspection_item=p.inspection_item,
            standard=p.standard,
            method=p.method,
            master_data=p.master_data or "",
            order_index=idx
        )
        db.add(ip)

    await db.commit()
    return {"status": "success", "updated_points": len(payload.points)}


class BatchAssignSchema(BaseModel):
    checksheet_ids: List[int]
    assigned_to: str


@router.post("/batch-assign")
async def batch_assign_checksheets(payload: BatchAssignSchema, db: AsyncSession = Depends(get_db)):
    """Assign multiple checksheets to a team member simultaneously."""
    stmt = (
        update(Checksheet)
        .where(Checksheet.id.in_(payload.checksheet_ids))
        .values(assigned_to=payload.assigned_to)
    )
    await db.execute(stmt)
    await db.commit()
    return {
        "status": "success",
        "updated_count": len(payload.checksheet_ids),
        "assigned_to": payload.assigned_to
    }
