"""
Checksheets API Router.
"""
import os
import re
import time
import asyncio
import base64
from typing import List, Optional, Union, Dict, Any
from pydantic import BaseModel
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, delete, update

from database.connection import get_db
from database.models import Checksheet, InspectionPoint, PartImage, SubmissionQueue, ActivityLog
from database.crud import (
    list_checksheets,
    get_checksheet_by_id,
    get_checksheet_base_by_id,
    get_checksheets_summary_list,
)
from parsers.smart_parser import TextNormalizer

router = APIRouter(prefix="/api/checksheets", tags=["Checksheets"])

# Ultra-fast in-memory cache kept in-sync via in-place mutations (zero full-dataset reloads)
_checksheets_cache: Dict[str, Any] = {
    "data": None,
    "timestamp": 0.0,
    "lock": None
}
CACHE_TTL = 300.0  # 5 minutes default TTL, kept synchronized via in-place mutation


def get_cache_lock():
    if _checksheets_cache["lock"] is None:
        _checksheets_cache["lock"] = asyncio.Lock()
    return _checksheets_cache["lock"]


def invalidate_checksheets_cache():
    """Wipe in-memory cache so subsequent reads fetch latest database state."""
    _checksheets_cache["data"] = None
    _checksheets_cache["timestamp"] = 0.0


def update_checksheet_in_cache(checksheet_id: int, updates: Dict[str, Any]):
    """Update a single checksheet in memory cache instantly (< 0.01ms)."""
    data = _checksheets_cache.get("data")
    if data:
        for item in data:
            if item.get("id") == checksheet_id:
                item.update(updates)
                break


def remove_checksheets_from_cache(checksheet_ids: Union[List[int], set]):
    """Remove checksheet(s) from memory cache instantly (< 0.01ms)."""
    data = _checksheets_cache.get("data")
    if data:
        id_set = set(checksheet_ids)
        _checksheets_cache["data"] = [item for item in data if item.get("id") not in id_set]


def prepend_checksheet_to_cache(item: Dict[str, Any]):
    """Prepend a newly created checksheet into memory cache instantly (< 0.01ms)."""
    data = _checksheets_cache.get("data")
    if data is not None:
        data.insert(0, item)


class InspectionPointSchema(BaseModel):
    item_no: str
    inspection_item: str
    standard: str = ""
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
    now = time.time()
    cached = _checksheets_cache["data"]
    if cached is not None and (now - _checksheets_cache["timestamp"] < CACHE_TTL):
        raw_list = cached
    else:
        async with get_cache_lock():
            if _checksheets_cache["data"] is not None and (time.time() - _checksheets_cache["timestamp"] < CACHE_TTL):
                raw_list = _checksheets_cache["data"]
            else:
                # Fast SQL aggregate query instead of 80,000+ child ORM object loads
                raw_list = await get_checksheets_summary_list(
                    session=db,
                    assigned_to=None,
                    status=None,
                    search=None,
                    limit=5000,
                    offset=0
                )
                _checksheets_cache["data"] = raw_list
                _checksheets_cache["timestamp"] = time.time()

    filtered = raw_list
    if assigned_to and assigned_to.upper() != "ALL":
        if assigned_to.upper() in ("UNASSIGNED", "BELUM DITUGASKAN"):
            filtered = [
                c for c in filtered 
                if not c.get("assigned_to") or c.get("assigned_to") in ("Unassigned", "Belum Ditugaskan")
            ]
        else:
            filtered = [c for c in filtered if c.get("assigned_to") == assigned_to]

    if status and status.upper() != "ALL":
        st_clean = status.strip().lower()
        if st_clean in ("belum di review", "belum di input", "belum_di_review", "belum_di_input"):
            filtered = [c for c in filtered if (c.get("status") or "") in ("Belum Di Input", "Belum di review")]
        elif st_clean in ("checksheet done", "checksheet_done"):
            filtered = [c for c in filtered if (c.get("status") or "").lower() == "checksheet done"]
        else:
            filtered = [c for c in filtered if (c.get("status") or "").lower() == status.lower()]

    if search:
        s_lower = search.lower().strip()
        filtered = [
            c for c in filtered
            if s_lower in (c.get("part_number") or "").lower()
            or s_lower in (c.get("part_name") or "").lower()
            or s_lower in (c.get("model") or "").lower()
        ]

    return filtered[offset:offset + limit]


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
    from core.extractor import get_cached_image_info

    res = []
    for img in cs.images:
        path = (img.image_path or "").replace("\\", "/")
        url = (img.image_url or "").replace("\\", "/")
        is_remote_url = url.startswith("http://") or url.startswith("https://")

        # Normalize absolute paths to relative (cross-platform fix)
        for prefix_marker in ["/storage/images/", "/extracted_images/"]:
            if prefix_marker in path:
                path = path[path.index(prefix_marker) + 1:]  # strip everything before "storage/..." or "extracted_..."
                break
        if path.startswith("storage/images/") or path.startswith("extracted_images/"):
            pass  # already relative, good
        elif "storage/images/" in path:
            path = "storage/images/" + path.split("storage/images/", 1)[1]
        elif "extracted_images/" in path:
            path = "extracted_images/" + path.split("extracted_images/", 1)[1]

        if not is_remote_url:
            if "storage/images" in path:
                sub = path.split("storage/images", 1)[1].lstrip("/")
                url = f"/media/images/{sub}"
            elif "extracted_images" in path:
                sub = path.split("extracted_images", 1)[1].lstrip("/")
                url = f"/media/extracted/{sub}"
            elif url and "storage/images" in url:
                sub = url.split("storage/images", 1)[1].lstrip("/")
                url = f"/media/images/{sub}"

        # Verify file exists on disk if local path is provided and not remote
        if not is_remote_url and path and not os.path.exists(path):
            continue

        # Strictly exclude company logos or header banners if local inspection is available
        if path and os.path.exists(path):
            img_info = get_cached_image_info(path)
            if img_info.get("is_logo", False):
                continue

        filename = os.path.basename(path) if path else (os.path.basename(url.split("?")[0]) if url else "image.webp")

        res.append({
            "id": img.id,
            "image_url": url,
            "image_path": path,
            "filename": filename
        })

    # Fallback: scan existing server storage folders if not yet linked in DB
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

    return res


@router.put("/{checksheet_id}")
@router.patch("/{checksheet_id}")
async def update_checksheet(checksheet_id: int, payload: ChecksheetUpdateSchema, db: AsyncSession = Depends(get_db)):
    cs = await get_checksheet_base_by_id(db, checksheet_id)
    if not cs:
        raise HTTPException(status_code=404, detail="Checksheet not found")

    status_changed = False
    assign_changed = False
    cache_updates: Dict[str, Any] = {}

    if payload.part_name is not None:
        cs.part_name = payload.part_name
        cache_updates["part_name"] = payload.part_name
    if payload.model is not None:
        cs.model = payload.model
        cache_updates["model"] = payload.model
    if payload.customer is not None:
        cs.customer = payload.customer
        cache_updates["customer"] = payload.customer
    if payload.doc_number is not None:
        cs.doc_number = payload.doc_number
        cache_updates["doc_number"] = payload.doc_number
    if payload.status is not None and payload.status != cs.status:
        cs.status = payload.status
        cache_updates["status"] = payload.status
        status_changed = True
    if payload.assigned_to is not None and payload.assigned_to != cs.assigned_to:
        cs.assigned_to = payload.assigned_to
        cache_updates["assigned_to"] = payload.assigned_to
        assign_changed = True
    if payload.keterangan is not None:
        cs.keterangan = payload.keterangan
        cache_updates["keterangan"] = payload.keterangan

    await db.commit()
    
    if cache_updates:
        update_checksheet_in_cache(cs.id, cache_updates)

    from services.google_sheets_service import trigger_background_sheet_sync
    if status_changed or assign_changed:
        trigger_background_sheet_sync()

    return {"status": "success", "id": cs.id, "assigned_to": cs.assigned_to}


class ClaimTaskSchema(BaseModel):
    operator_name: str


@router.post("/{checksheet_id}/claim")
async def claim_checksheet_task(checksheet_id: int, payload: ClaimTaskSchema, db: AsyncSession = Depends(get_db)):
    """Allow an operator to claim an unassigned checksheet task for themselves."""
    cs = await get_checksheet_base_by_id(db, checksheet_id)
    if not cs:
        raise HTTPException(status_code=404, detail="Checksheet not found")

    cs.assigned_to = payload.operator_name
    await db.commit()
    update_checksheet_in_cache(cs.id, {"assigned_to": payload.operator_name})

    from services.google_sheets_service import trigger_background_sheet_sync
    trigger_background_sheet_sync()

    return {
        "status": "success",
        "checksheet_id": cs.id,
        "part_number": cs.part_number,
        "assigned_to": cs.assigned_to
    }


@router.put("/{checksheet_id}/points")
async def update_checksheet_points(checksheet_id: int, payload: ChecksheetPointsUpdateSchema, db: AsyncSession = Depends(get_db)):
    cs = await get_checksheet_base_by_id(db, checksheet_id)
    if not cs:
        raise HTTPException(status_code=404, detail="Checksheet not found")

    # Replace existing inspection points
    await db.execute(delete(InspectionPoint).where(InspectionPoint.checksheet_id == checksheet_id))

    for idx, p in enumerate(payload.points):
        norm = TextNormalizer.normalize_point({
            "item_no": p.item_no,
            "inspection_item": p.inspection_item,
            "standard": p.standard,
            "method": p.method,
            "master_data": p.master_data or "",
        })
        ip = InspectionPoint(
            checksheet_id=checksheet_id,
            item_no=norm.get("item_no") or p.item_no,
            inspection_item=norm.get("inspection_item") or p.inspection_item,
            standard=norm.get("standard") or p.standard,
            method=norm.get("method") or p.method,
            master_data=norm.get("master_data") or "",
            order_index=idx
        )
        db.add(ip)

    await db.commit()
    update_checksheet_in_cache(checksheet_id, {"points_count": len(payload.points)})
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
    for cid in payload.checksheet_ids:
        update_checksheet_in_cache(cid, {"assigned_to": payload.assigned_to})

    from services.google_sheets_service import trigger_background_sheet_sync
    trigger_background_sheet_sync()

    return {"status": "success", "assigned_count": len(payload.checksheet_ids), "assigned_to": payload.assigned_to}


class BatchStatusSchema(BaseModel):
    checksheet_ids: List[int]
    status: str
    keterangan: Optional[str] = None


@router.post("/batch-status")
async def batch_update_status(payload: BatchStatusSchema, db: AsyncSession = Depends(get_db)):
    """Update status (kategori) for multiple checksheets simultaneously."""
    if not payload.checksheet_ids:
        return {"status": "success", "updated_count": 0}

    values: Dict[str, Any] = {"status": payload.status}
    if payload.keterangan is not None:
        values["keterangan"] = payload.keterangan
    elif payload.status.lower() == "canceled":
        values["keterangan"] = "Dibatalkan manual oleh reviewer"

    stmt = (
        update(Checksheet)
        .where(Checksheet.id.in_(payload.checksheet_ids))
        .values(**values)
    )
    await db.execute(stmt)
    await db.commit()

    for cid in payload.checksheet_ids:
        update_checksheet_in_cache(cid, values)

    from services.google_sheets_service import trigger_background_sheet_sync
    trigger_background_sheet_sync()

    return {
        "status": "success",
        "updated_count": len(payload.checksheet_ids),
        "new_status": payload.status
    }


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

    # Always store as forward-slash relative path for cross-platform compatibility
    db_path = target_path.replace("\\", "/")
    url_sub = f"/media/images/{clean_p}/{safe_name}"
    try:
        from services.supabase_storage_service import upload_image_to_supabase
        remote_url = upload_image_to_supabase(target_path, clean_p, safe_name)
        if remote_url:
            url_sub = remote_url
    except Exception as e:
        pass

    existing_img = None
    for img in cs.images:
        norm_existing = (img.image_path or "").replace("\\", "/")
        if norm_existing == db_path:
            existing_img = img
            break

    new_part_img_id = None
    if not existing_img:
        new_part_img = PartImage(
            checksheet_id=cs.id,
            image_path=db_path,
            image_url=url_sub
        )
        db.add(new_part_img)
        await db.commit()
        await db.refresh(cs)
        update_checksheet_in_cache(cs.id, {"images_count": len(cs.images), "thumbnail_url": url_sub})
        new_part_img_id = new_part_img.id
    else:
        existing_img.image_url = url_sub
        await db.commit()
        await db.refresh(cs)
        update_checksheet_in_cache(cs.id, {"images_count": len(cs.images), "thumbnail_url": url_sub})
        new_part_img_id = existing_img.id

    new_img_dict = {
        "id": new_part_img_id,
        "image_url": url_sub,
        "image_path": db_path,
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
    thumb_url = updated_images[0]["image_url"] if updated_images else None
    update_checksheet_in_cache(cs.id, {"images_count": len(cs.images), "thumbnail_url": thumb_url})

    return {"status": "success", "deleted_count": deleted_count, "images": updated_images}


@router.delete("/{checksheet_id}/images/all")
async def delete_all_checksheet_images(
    checksheet_id: int,
    db: AsyncSession = Depends(get_db)
):
    """Delete ALL drawing images for this checksheet from DB and disk."""
    cs = await get_checksheet_by_id(db, checksheet_id)
    if not cs:
        raise HTTPException(status_code=404, detail="Checksheet not found")

    deleted_count = 0
    for img in list(cs.images):
        if img.image_path and os.path.isfile(img.image_path):
            try:
                os.remove(img.image_path)
            except Exception:
                pass
        await db.delete(img)
        deleted_count += 1

    await db.commit()
    update_checksheet_in_cache(cs.id, {"images_count": 0, "thumbnail_url": None})

    return {
        "status": "success",
        "message": f"Semua gambar ({deleted_count} gambar) berhasil dihapus.",
        "deleted_count": deleted_count,
        "images": []
    }


@router.post("/sync-images")
async def sync_images_endpoint(db: AsyncSession = Depends(get_db)):
    """
    Ingests and synchronizes all part sketch images to the Supabase database (part_images table)
    and uploads missing images directly to Supabase Cloud Storage.
    """
    from services.image_ingestion_service import sync_all_part_images_to_db
    from services.supabase_storage_service import sync_all_images_to_supabase_storage
    try:
        res = await sync_all_part_images_to_db(db)
        try:
            cloud_res = await sync_all_images_to_supabase_storage(db)
            res["cloud_storage"] = cloud_res
        except Exception as sc_err:
            res["cloud_storage_warning"] = str(sc_err)
        invalidate_checksheets_cache()
        return res
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Image ingestion failed: {str(e)}")


@router.post("/cache/clear")
async def clear_checksheets_cache_endpoint():
    """Immediately invalidates the in-memory checksheet summary cache."""
    invalidate_checksheets_cache()
    return {"status": "success", "message": "Checksheets cache cleared"}


@router.post("/reconcile")
async def reconcile_status_endpoint(
    channel: str = Query("chrome", description="Browser channel (chrome, msedge)"),
    db: AsyncSession = Depends(get_db)
):
    """
    Performs full two-way audit between FactoryHub checksheet master and Supabase database.
    Updates completed checksheets, marks missing ones as 'Butuh Revisi',
    logs clean audit history, and auto-syncs Google Sheets.
    """
    from services.reconciliation_service import run_factoryhub_reconciliation
    try:
        res = await run_factoryhub_reconciliation(session=db, headless=True, browser_channel=channel)
        invalidate_checksheets_cache()
        return res
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Reconciliation audit failed: {str(e)}")


class PointItemManualSchema(BaseModel):
    item_no: Optional[str] = "1"
    inspection_item: str
    standard: Optional[str] = ""
    method: Optional[str] = "Visual"
    master_data: Optional[str] = ""


class CreateChecksheetManualSchema(BaseModel):
    part_number: str
    part_name: Optional[str] = ""
    model: Optional[str] = "-"
    customer: Optional[str] = "PT. HPM"
    doc_number: Optional[str] = "FO-45-01"
    assigned_to: Optional[str] = "Unassigned"
    status: Optional[str] = "Belum di review"
    keterangan: Optional[str] = "Ditambahkan manual oleh admin"
    points: Optional[List[PointItemManualSchema]] = []


@router.post("/manual")
async def create_checksheet_manual(
    payload: CreateChecksheetManualSchema,
    db: AsyncSession = Depends(get_db)
):
    """Create a new checksheet manually with optional inspection points."""
    pn = payload.part_number.strip()
    if not pn:
        raise HTTPException(status_code=400, detail="Part number tidak boleh kosong.")

    from database.crud import clean_str, log_activity
    c_clean = clean_str(pn)

    new_cs = Checksheet(
        part_number=pn,
        clean_part_number=c_clean,
        part_name=payload.part_name or "",
        model=payload.model or "-",
        customer=payload.customer or "PT. HPM",
        doc_number=payload.doc_number or "FO-45-01",
        status=payload.status or "Belum di review",
        assigned_to=payload.assigned_to or "Unassigned",
        keterangan=payload.keterangan or "Ditambahkan manual oleh admin",
    )
    db.add(new_cs)
    await db.flush()

    if payload.points:
        for idx, pt in enumerate(payload.points):
            ip = InspectionPoint(
                checksheet_id=new_cs.id,
                item_no=pt.item_no or str(idx + 1),
                inspection_item=pt.inspection_item,
                standard=pt.standard or "",
                method=pt.method or "Visual",
                master_data=pt.master_data or "",
                order_index=idx
            )
            db.add(ip)

    await db.commit()
    prepend_checksheet_to_cache({
        "id": new_cs.id,
        "part_number": new_cs.part_number,
        "part_name": new_cs.part_name,
        "model": new_cs.model,
        "customer": new_cs.customer,
        "doc_number": new_cs.doc_number,
        "status": new_cs.status,
        "assigned_to": new_cs.assigned_to,
        "keterangan": new_cs.keterangan,
        "points_count": len(payload.points or []),
        "images_count": 0,
        "factoryhub_url": None,
        "updated_at": None
    })

    await log_activity(
        session=db,
        action="CREATE CHECKSHEET",
        part_number=new_cs.part_number,
        operator=payload.assigned_to or "Admin",
        status="SUCCESS",
        details=f"Part baru berhasil ditambahkan manual dengan {len(payload.points or [])} poin"
    )

    from services.google_sheets_service import trigger_background_sheet_sync
    trigger_background_sheet_sync()

    return {"status": "success", "id": new_cs.id, "part_number": new_cs.part_number}


@router.delete("/{checksheet_id}")
async def delete_checksheet_endpoint(
    checksheet_id: int,
    db: AsyncSession = Depends(get_db)
):
    """Delete a checksheet and its associated inspection points, images, and queue entries."""
    cs = await get_checksheet_base_by_id(db, checksheet_id)
    if not cs:
        raise HTTPException(status_code=404, detail="Checksheet not found")

    pn = cs.part_number
    # Cascade foreign keys in Postgres delete child records automatically in 1 query
    await db.execute(delete(Checksheet).where(Checksheet.id == checksheet_id))
    entry = ActivityLog(
        action="DELETE CHECKSHEET",
        part_number=pn,
        operator="Admin",
        status="SUCCESS",
        details=f"Checksheet #{checksheet_id} ({pn}) berhasil dihapus dari database"
    )
    db.add(entry)
    await db.commit()
    remove_checksheets_from_cache([checksheet_id])

    from services.google_sheets_service import trigger_background_sheet_sync
    trigger_background_sheet_sync()

    return {"status": "success", "deleted_id": checksheet_id, "part_number": pn}


class BulkDeleteSchema(BaseModel):
    checksheet_ids: List[int]


@router.post("/bulk-delete")
async def bulk_delete_checksheets(
    payload: BulkDeleteSchema,
    db: AsyncSession = Depends(get_db)
):
    """Delete multiple checksheets at once."""
    if not payload.checksheet_ids:
        return {"status": "success", "deleted_count": 0}

    target_ids = payload.checksheet_ids
    # Cascade foreign keys in Postgres delete child records automatically in 1 query
    res = await db.execute(delete(Checksheet).where(Checksheet.id.in_(target_ids)))
    deleted_count = res.rowcount if hasattr(res, "rowcount") else len(target_ids)
    
    entry = ActivityLog(
        action="BULK DELETE",
        part_number=f"{deleted_count} Part",
        operator="Admin",
        status="SUCCESS",
        details=f"Bulk delete berhasil menghapus {deleted_count} checksheet"
    )
    db.add(entry)
    await db.commit()
    remove_checksheets_from_cache(target_ids)

    from services.google_sheets_service import trigger_background_sheet_sync
    trigger_background_sheet_sync()

    return {"status": "success", "deleted_count": deleted_count}

