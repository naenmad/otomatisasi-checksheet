"""
FastAPI Routes for Maintenance Tools (Image Optimization & WebP Compression).
"""
import os
import re
import asyncio
from typing import Dict, Any, List, Optional
from pydantic import BaseModel
from fastapi import APIRouter, HTTPException, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from database.connection import get_db
from database.models import Checksheet, PartImage
from services.supabase_storage_service import (
    upload_file_to_supabase,
    delete_file_from_supabase,
    get_public_url,
    BUCKET_NAME
)

router = APIRouter(prefix="/api/tools", tags=["tools"])

SUPPORTED_NON_WEBP = (".png", ".jpg", ".jpeg", ".bmp", ".tiff")


class CompressRequest(BaseModel):
    target: str = "all"  # "all", "storage", "extracted"
    quality: int = 82
    max_dimension: int = 1920
    delete_original: bool = True


@router.get("/image-stats")
async def get_image_stats() -> Dict[str, Any]:
    """Scan disk and return statistics of WebP vs Non-WebP images."""
    base_dirs = ["storage/images", "extracted_images"]
    non_webp_count = 0
    non_webp_bytes = 0
    webp_count = 0
    webp_bytes = 0

    for b_dir in base_dirs:
        if not os.path.isdir(b_dir):
            continue
        for root, _, files in os.walk(b_dir):
            for fn in files:
                ext = os.path.splitext(fn)[1].lower()
                fp = os.path.join(root, fn)
                try:
                    sz = os.path.getsize(fp)
                except OSError:
                    continue

                if ext == ".webp":
                    webp_count += 1
                    webp_bytes += sz
                elif ext in SUPPORTED_NON_WEBP:
                    non_webp_count += 1
                    non_webp_bytes += sz

    non_webp_mb = round(non_webp_bytes / (1024 * 1024), 2)
    webp_mb = round(webp_bytes / (1024 * 1024), 2)
    # Average webp conversion saves ~80%
    est_savings_mb = round(non_webp_mb * 0.80, 2)

    return {
        "non_webp_count": non_webp_count,
        "non_webp_mb": non_webp_mb,
        "webp_count": webp_count,
        "webp_mb": webp_mb,
        "estimated_savings_mb": est_savings_mb
    }


@router.post("/compress-webp")
async def compress_images_to_webp(
    payload: CompressRequest,
    session: AsyncSession = Depends(get_db)
) -> Dict[str, Any]:
    """
    Compresses non-webp images to WebP, uploads to Supabase, updates DB,
    and removes old bloated files.
    """
    try:
        from PIL import Image
    except ImportError:
        raise HTTPException(status_code=500, detail="PIL / Pillow library tidak terpasang")

    # Select target folders
    if payload.target == "storage":
        base_dirs = ["storage/images"]
    elif payload.target == "extracted":
        base_dirs = ["extracted_images"]
    else:
        base_dirs = ["storage/images", "extracted_images"]

    candidates = []
    for b_dir in base_dirs:
        if not os.path.isdir(b_dir):
            continue
        for root, _, files in os.walk(b_dir):
            for fn in files:
                ext = os.path.splitext(fn)[1].lower()
                if ext in SUPPORTED_NON_WEBP:
                    src_p = os.path.join(root, fn)
                    candidates.append((b_dir, root, fn, src_p))

    converted_files = []
    total_old_bytes = 0
    total_new_bytes = 0

    all_images = (await session.scalars(select(PartImage))).all()
    all_cs = (await session.scalars(select(Checksheet))).all()
    cs_map = {cs.id: cs for cs in all_cs}

    for b_dir, root, fn, src_path in candidates:
        stem, _ = os.path.splitext(fn)
        dest_fn = f"{stem}.webp"
        dest_path = os.path.join(root, dest_fn)

        try:
            old_sz = os.path.getsize(src_path)
            with Image.open(src_path) as im:
                if im.mode in ("RGBA", "LA") or (im.mode == "P" and "transparency" in im.info):
                    im_c = im.convert("RGBA")
                else:
                    im_c = im.convert("RGB")

                if payload.max_dimension and payload.max_dimension > 0:
                    w, h = im_c.size
                    if w > payload.max_dimension or h > payload.max_dimension:
                        im_c.thumbnail((payload.max_dimension, payload.max_dimension), Image.Resampling.LANCZOS)

                im_c.save(dest_path, "WEBP", quality=max(10, min(100, payload.quality)), method=6)

            new_sz = os.path.getsize(dest_path)
            total_old_bytes += old_sz
            total_new_bytes += new_sz

            saved_file_bytes = max(0, old_sz - new_sz)
            saved_file_pct = round((saved_file_bytes / old_sz * 100), 1) if old_sz > 0 else 0

            # Folder name relative to base_dir (part_number)
            rel_folder = os.path.relpath(root, b_dir).replace("\\", "/")
            remote_webp = f"{rel_folder}/{dest_fn}" if rel_folder != "." else dest_fn
            remote_old = f"{rel_folder}/{fn}" if rel_folder != "." else fn

            # Upload to Supabase Storage
            public_url = upload_file_to_supabase(dest_path, remote_webp)
            if payload.delete_original:
                delete_file_from_supabase(remote_old)
                try:
                    os.remove(src_path)
                except Exception:
                    pass

            converted_files.append({
                "original_path": src_path.replace("\\", "/"),
                "new_path": dest_path.replace("\\", "/"),
                "old_size_kb": round(old_sz / 1024, 1),
                "new_size_kb": round(new_sz / 1024, 1),
                "saved_percent": saved_file_pct
            })
        except Exception as e:
            continue

    # Update database records
    if converted_files:
        for img in all_images:
            p = (img.image_path or "").replace("\\", "/")
            ext = os.path.splitext(p)[1].lower()
            if ext in SUPPORTED_NON_WEBP:
                base_p, _ = os.path.splitext(p)
                webp_p = f"{base_p}.webp"
                if os.path.isfile(webp_p):
                    img.image_path = webp_p
                    cs = cs_map.get(img.checksheet_id)
                    clean_p = (cs.clean_part_number if cs else "") or "default"
                    img.image_url = get_public_url(f"{clean_p}/{os.path.basename(webp_p)}")
        await session.commit()

        # Invalidate cache
        try:
            from server.routes.checksheets import warmup_checksheets_cache
            asyncio.create_task(warmup_checksheets_cache())
        except Exception:
            pass

    saved_bytes = max(0, total_old_bytes - total_new_bytes)
    saved_mb = round(saved_bytes / (1024 * 1024), 2)
    saved_pct = round((saved_bytes / total_old_bytes * 100), 1) if total_old_bytes > 0 else 0

    return {
        "total_converted": len(converted_files),
        "original_size_mb": round(total_old_bytes / (1024 * 1024), 2),
        "compressed_size_mb": round(total_new_bytes / (1024 * 1024), 2),
        "saved_size_mb": saved_mb,
        "saved_percent": saved_pct,
        "converted_files": converted_files
    }
