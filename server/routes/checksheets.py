"""
Checksheets API Router.
"""
import os
import re
import time
import base64
from typing import List, Optional, Union
from pydantic import BaseModel
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, delete, update

from database.connection import get_db
from database.models import Checksheet, InspectionPoint, PartImage
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
    from extractor import get_cached_image_info

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

        # Strictly exclude company logos or header banners
        if path:
            img_info = get_cached_image_info(path)
            if img_info.get("is_logo", False):
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
                            f_path = os.path.join(dir_path, f)
                            img_info = get_cached_image_info(f_path)
                            if img_info.get("is_logo", False):
                                continue
                            res.append({
                                "id": f,
                                "image_url": f"{url_prefix}/{folder}/{f}",
                                "image_path": f_path,
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
                    img_info = get_cached_image_info(ep)
                    if img_info.get("is_logo", False):
                        continue
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
@router.patch("/{checksheet_id}")
async def update_checksheet(checksheet_id: int, payload: ChecksheetUpdateSchema, db: AsyncSession = Depends(get_db)):
    cs = await get_checksheet_by_id(db, checksheet_id)
    if not cs:
        raise HTTPException(status_code=404, detail="Checksheet not found")

    status_changed = False
    assign_changed = False
    old_assigned = cs.assigned_to

    if payload.part_name is not None: cs.part_name = payload.part_name
    if payload.model is not None: cs.model = payload.model
    if payload.customer is not None: cs.customer = payload.customer
    if payload.doc_number is not None: cs.doc_number = payload.doc_number
    if payload.status is not None and payload.status != cs.status:
        cs.status = payload.status
        status_changed = True
    if payload.assigned_to is not None and payload.assigned_to != cs.assigned_to:
        cs.assigned_to = payload.assigned_to
        assign_changed = True
    if payload.keterangan is not None: cs.keterangan = payload.keterangan

    await db.commit()
    await db.refresh(cs)

    from database.crud import log_activity
    from services.google_sheets_service import trigger_background_sheet_sync

    if status_changed:
        await log_activity(
            session=db,
            action="UPDATE STATUS",
            part_number=cs.part_number,
            operator=cs.assigned_to or "Operator",
            status=cs.status,
            details=f"Status diubah menjadi {cs.status}" + (f" ({cs.keterangan})" if cs.keterangan else "")
        )
        trigger_background_sheet_sync()

    if assign_changed:
        is_claim = old_assigned in ("Unassigned", "Belum Ditugaskan", None, "")
        await log_activity(
            session=db,
            action="AMBIL TASK" if is_claim else "UPDATE PENUGASAN",
            part_number=cs.part_number,
            operator=cs.assigned_to or "Operator",
            status="SUCCESS",
            details=f"Operator {cs.assigned_to} mengambil task {cs.part_number}" if is_claim else f"Penugasan diubah ke {cs.assigned_to} (dari {old_assigned or 'Belum Ditugaskan'})"
        )
        trigger_background_sheet_sync()

    return {"status": "success", "id": cs.id, "assigned_to": cs.assigned_to}


class ClaimTaskSchema(BaseModel):
    operator_name: str


@router.post("/{checksheet_id}/claim")
async def claim_checksheet_task(checksheet_id: int, payload: ClaimTaskSchema, db: AsyncSession = Depends(get_db)):
    """Allow an operator to claim an unassigned checksheet task for themselves."""
    cs = await get_checksheet_by_id(db, checksheet_id)
    if not cs:
        raise HTTPException(status_code=404, detail="Checksheet not found")

    old_assigned = cs.assigned_to
    cs.assigned_to = payload.operator_name
    await db.commit()
    await db.refresh(cs)

    from database.crud import log_activity
    from services.google_sheets_service import trigger_background_sheet_sync

    await log_activity(
        session=db,
        action="AMBIL TASK",
        part_number=cs.part_number,
        operator=payload.operator_name,
        status="SUCCESS",
        details=f"Operator {payload.operator_name} mengambil task {cs.part_number} (sebelumnya: {old_assigned or 'Belum Ditugaskan'})"
    )
    trigger_background_sheet_sync()

    return {
        "status": "success",
        "checksheet_id": cs.id,
        "part_number": cs.part_number,
        "assigned_to": cs.assigned_to
    }


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

    from database.crud import log_activity
    await log_activity(
        session=db,
        action="SIMPAN POIN",
        part_number=cs.part_number,
        operator=cs.assigned_to or "Operator",
        status="SUCCESS",
        details=f"Menyimpan {len(payload.points)} poin inspeksi via Studio"
    )

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

    from database.crud import log_activity
    from services.google_sheets_service import trigger_background_sheet_sync

    await log_activity(
        session=db,
        action="AMBIL TASK BATCH" if payload.assigned_to else "PENUGASAN BATCH",
        part_number=f"{len(payload.checksheet_ids)} part",
        operator=payload.assigned_to,
        status="SUCCESS",
        details=f"Penugasan {len(payload.checksheet_ids)} part ke {payload.assigned_to}"
    )
    trigger_background_sheet_sync()

    return {"status": "success", "assigned_count": len(payload.checksheet_ids), "assigned_to": payload.assigned_to}


class ImageUploadSchema(BaseModel):
    image_base64: str
    filename: Optional[str] = None


@router.post("/{checksheet_id}/images/upload")
async def upload_checksheet_image(
    checksheet_id: int,
    payload: ImageUploadSchema,
    db: AsyncSession = Depends(get_db)
):
    """Upload or paste a sketch/drawing image for a checksheet."""
    cs = await get_checksheet_by_id(db, checksheet_id)
    if not cs:
        raise HTTPException(status_code=404, detail="Checksheet not found")

    from database.crud import clean_str
    clean_p = clean_str(cs.part_number) or "default"
    save_dir = os.path.join("storage", "images", clean_p)
    os.makedirs(save_dir, exist_ok=True)

    b64_str = payload.image_base64
    ext = "png"
    if "," in b64_str:
        header, b64_str = b64_str.split(",", 1)
        if "jpeg" in header or "jpg" in header:
            ext = "jpg"
        elif "webp" in header:
            ext = "webp"

    raw_name = payload.filename or f"sketch_{int(time.time() * 1000)}.{ext}"
    base_name = os.path.basename(raw_name)
    safe_name = re.sub(r"[^0-9A-Za-z_.-]", "_", base_name)
    if not safe_name.lower().endswith((".png", ".jpg", ".jpeg", ".webp")):
        safe_name = f"{safe_name}.{ext}"

    target_path = os.path.join(save_dir, safe_name)
    try:
        data = base64.b64decode(b64_str)
        with open(target_path, "wb") as f:
            f.write(data)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Gagal memproses file gambar: {str(e)}")

    url_sub = f"/media/images/{clean_p}/{safe_name}"

    existing_img = None
    for img in cs.images:
        if img.image_path == target_path:
            existing_img = img
            break

    new_part_img_id = None
    if not existing_img:
        new_part_img = PartImage(
            checksheet_id=cs.id,
            image_path=target_path,
            image_url=url_sub
        )
        db.add(new_part_img)
        await db.commit()
        await db.refresh(cs)
        new_part_img_id = new_part_img.id
    else:
        new_part_img_id = existing_img.id

    new_img_dict = {
        "id": new_part_img_id,
        "image_url": url_sub,
        "image_path": target_path,
        "filename": safe_name
    }

    updated_images = _build_checksheet_images(cs)
    return {"status": "success", "images": updated_images, "image": new_img_dict}


class DeleteImageSchema(BaseModel):
    image_id: Optional[Union[int, str]] = None
    filename: Optional[str] = None
    image_path: Optional[str] = None


@router.delete("/{checksheet_id}/images")
async def delete_checksheet_image(
    checksheet_id: int,
    filename: Optional[str] = Query(None),
    image_path: Optional[str] = Query(None),
    payload: Optional[DeleteImageSchema] = None,
    db: AsyncSession = Depends(get_db)
):
    """Delete a drawing image from DB and disk (e.g. erroneous logo extraction)."""
    cs = await get_checksheet_by_id(db, checksheet_id)
    if not cs:
        raise HTTPException(status_code=404, detail="Checksheet not found")

    raw_fn = payload.filename if (payload and payload.filename) else (filename if isinstance(filename, str) else None)
    raw_ip = payload.image_path if (payload and payload.image_path) else (image_path if isinstance(image_path, str) else None)
    target_id = str(payload.image_id) if (payload and payload.image_id is not None) else None

    target_file = raw_fn
    target_path = raw_ip
    if not target_file and target_path:
        target_file = os.path.basename(target_path)

    if not target_file and not target_path and not target_id:
        raise HTTPException(status_code=400, detail="Filename, image_path, or image_id is required")

    deleted_count = 0

    # 1. Delete from PartImage table
    for img in list(cs.images):
        matches = False
        if target_id and str(img.id) == target_id:
            matches = True
        elif target_file and os.path.basename(img.image_path or "") == target_file:
            matches = True
        elif target_path and img.image_path == target_path:
            matches = True

        if matches:
            if img.image_path and os.path.isfile(img.image_path):
                try:
                    os.remove(img.image_path)
                except Exception:
                    pass
            await db.delete(img)
            deleted_count += 1

    # 2. Check disk locations (storage/images, extracted_images)
    from database.crud import clean_str
    clean_p = clean_str(cs.part_number)
    norm_p = re.sub(r"[^0-9A-Za-z_-]", "_", cs.part_number)
    file_stem = os.path.splitext(os.path.basename(cs.raw_file_path or ""))[0]
    clean_file_stem = re.sub(r"^(CS\s*IQC\s*)", "", file_stem, flags=re.I).strip()
    norm_stem = re.sub(r"[^0-9A-Za-z_-]", "_", clean_file_stem)

    candidate_folders = [cs.part_number, norm_p, clean_p, clean_file_stem, norm_stem]

    for c_dir in candidate_folders:
        if not c_dir or len(c_dir) < 3:
            continue
        for base_dir in ["storage/images", "extracted_images"]:
            p = os.path.join(base_dir, c_dir, target_file) if target_file else None
            if p and os.path.isfile(p):
                try:
                    os.remove(p)
                    deleted_count += 1
                except Exception:
                    pass

    if target_path and os.path.isfile(target_path):
        try:
            os.remove(target_path)
            deleted_count += 1
        except Exception:
            pass

    await db.commit()
    await db.refresh(cs)

    updated_images = _build_checksheet_images(cs)
    return {"status": "success", "deleted_count": deleted_count, "images": updated_images}
