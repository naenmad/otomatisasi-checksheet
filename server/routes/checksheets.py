"""
Checksheets API Router.
"""
from typing import List, Optional
from pydantic import BaseModel
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, delete, update

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
    limit: int = 1000,
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
        "images": _build_checksheet_images(cs)
    }


def _build_checksheet_images(cs: Checksheet) -> list:
    import os
    import re
    res = []
    for img in cs.images:
        path = img.image_path or ""
        url = img.image_url or ""
        if "storage/images" in path:
            sub = path.split("storage/images", 1)[1].lstrip("/\\")
            url = f"/media/images/{sub}"
        elif "extracted_images" in path:
            sub = path.split("extracted_images", 1)[1].lstrip("/\\")
            url = f"/media/extracted/{sub}"
        elif url and "storage/images" in url:
            sub = url.split("storage/images", 1)[1].lstrip("/\\")
            url = f"/media/images/{sub}"
        # Verify file exists on disk if path is provided
        if path and not os.path.exists(path):
            continue

        res.append({
            "id": img.id,
            "image_url": url,
            "image_path": path,
            "filename": os.path.basename(path)
        })

    # Fallback: scan disk folders if not linked in DB
    if not res:
        from database.crud import clean_str
        clean_p = clean_str(cs.part_number)
        norm_p = re.sub(r"[^0-9A-Za-z_-]", "_", cs.part_number)
        file_stem = os.path.splitext(os.path.basename(cs.raw_file_path or ""))[0]
        clean_file_stem = re.sub(r"^(CS\s*IQC\s*)", "", file_stem, flags=re.I).strip()
        norm_stem = re.sub(r"[^0-9A-Za-z_-]", "_", clean_file_stem)

        candidate_dirs = [cs.part_number, norm_p, clean_p, clean_file_stem, norm_stem]
        seen_cand = set()

        for folder in candidate_dirs:
            if not folder or len(folder) < 3 or folder in seen_cand:
                continue
            seen_cand.add(folder)

            for base_dir, url_prefix in [("storage/images", "/media/images"), ("extracted_images", "/media/extracted")]:
                dir_path = os.path.join(base_dir, folder)
                if os.path.isdir(dir_path):
                    for f in sorted(os.listdir(dir_path)):
                        if f.lower().endswith((".webp", ".png", ".jpg", ".jpeg")):
                            res.append({
                                "id": f,
                                "image_url": f"{url_prefix}/{folder}/{f}",
                                "image_path": os.path.join(dir_path, f),
                                "filename": f
                            })
                    if res:
                        break
            if res:
                break

    # Dynamic on-the-fly extraction if raw file exists and has images
    if not res and cs.raw_file_path and os.path.exists(cs.raw_file_path):
        if cs.raw_file_path.lower().endswith(".xlsx"):
            try:
                from parsers.image_extractor import extract_excel_images
                extracted = extract_excel_images(cs.raw_file_path, part_number=cs.part_number)
                for ep in extracted:
                    sub = ep.split("storage/images", 1)[1].lstrip("/\\") if "storage/images" in ep else os.path.basename(ep)
                    res.append({
                        "id": os.path.basename(ep),
                        "image_url": f"/media/images/{sub}",
                        "image_path": ep,
                        "filename": os.path.basename(ep)
                    })
            except Exception as e:
                print(f"[Warning] On-the-fly image extraction failed for {cs.part_number}: {e}")

    return res


@router.put("/{checksheet_id}")
async def update_checksheet(checksheet_id: int, payload: ChecksheetUpdateSchema, db: AsyncSession = Depends(get_db)):
    cs = await get_checksheet_by_id(db, checksheet_id)
    if not cs:
        raise HTTPException(status_code=404, detail="Checksheet not found")

    status_changed = False
    if payload.part_name is not None: cs.part_name = payload.part_name
    if payload.model is not None: cs.model = payload.model
    if payload.customer is not None: cs.customer = payload.customer
    if payload.doc_number is not None: cs.doc_number = payload.doc_number
    if payload.status is not None and payload.status != cs.status:
        cs.status = payload.status
        status_changed = True
    if payload.assigned_to is not None: cs.assigned_to = payload.assigned_to
    if payload.keterangan is not None: cs.keterangan = payload.keterangan

    await db.commit()
    await db.refresh(cs)

    if status_changed:
        from services.google_sheets_service import trigger_background_sheet_sync
        trigger_background_sheet_sync()

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
