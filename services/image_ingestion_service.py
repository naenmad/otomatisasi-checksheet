"""
Image Ingestion Service for Supabase Checksheets.

This service ensures all checksheet sketch images are properly extracted once
and stored in the Supabase database (part_images table) and on the server filesystem
(storage/images/{clean_part}/).

At form submission / dry-run time, the automator NEVER touches or parses documents on disk;
it consumes pre-stored image paths and inspection points strictly from Supabase.
"""
import os
import re
import glob
import logging
from typing import Dict, Any, List
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, delete

from database.connection import AsyncSessionLocal
from database.models import Checksheet, PartImage
from database.crud import clean_str
from core.extractor import get_cached_image_info

logger = logging.getLogger("image_ingestion")


def _to_relative_path(path: str) -> str:
    """Convert any path to a relative forward-slash path from the project root."""
    p = (path or "").replace("\\", "/")
    for marker in ["storage/images/", "extracted_images/"]:
        if marker in p:
            return p[p.index(marker):]
    return os.path.basename(p)


def _is_valid_sketch(file_path: str) -> bool:
    """Check if image file exists and is definitely a technical sketch, not a company logo."""
    if not os.path.isfile(file_path):
        return False
    info = get_cached_image_info(file_path)
    if info.get("is_logo", False):
        return False
    # Check minimum file size (> 1KB)
    try:
        return os.path.getsize(file_path) > 1024
    except Exception:
        return False


async def sync_all_part_images_to_db(session: AsyncSession) -> Dict[str, Any]:
    """
    Scans storage/images and extracted_images for all checksheets in Supabase.
    If a checksheet is missing its PartImage record or has unlinked sketches,
    registers the sketch files to part_images in Supabase with:
    - Relative path (cross-platform safe, not machine-specific absolute paths)
    - Supabase CDN URL (immediately uploaded; fallback to /media URL if upload fails)
    """
    from services.supabase_storage_service import upload_file_to_supabase

    all_cs = (await session.scalars(select(Checksheet))).all()
    cs_by_clean = {cs.clean_part_number: cs for cs in all_cs}
    cs_by_norm = {re.sub(r"[^0-9A-Za-z_-]", "_", cs.part_number): cs for cs in all_cs}
    cs_by_raw = {cs.part_number.strip(): cs for cs in all_cs}

    # Build lookup using relative paths (cross-platform deduplication)
    existing_images = (await session.scalars(select(PartImage))).all()
    existing_by_cs: Dict[int, List[str]] = {}
    for img in existing_images:
        rel = _to_relative_path(img.image_path or "")
        existing_by_cs.setdefault(img.checksheet_id, []).append(rel)

    new_linked_count = 0
    updated_cs_count = set()

    # Base search directories on server
    base_dirs = ["storage/images", "extracted_images"]

    for b_dir in base_dirs:
        if not os.path.isdir(b_dir):
            continue
        for folder in os.listdir(b_dir):
            folder_path = os.path.join(b_dir, folder)
            if not os.path.isdir(folder_path):
                continue

            # Try matching folder name to a checksheet
            clean_folder = clean_str(folder)
            target_cs = cs_by_clean.get(clean_folder) or cs_by_norm.get(folder) or cs_by_raw.get(folder)

            if not target_cs:
                # Try finding by prefix matching or stem
                clean_no_rev = re.sub(r"^(CS\s*IQC\s*)", "", folder, flags=re.I).strip()
                target_cs = cs_by_clean.get(clean_str(clean_no_rev))

            if not target_cs:
                continue

            # Scan images in this folder
            for f in sorted(os.listdir(folder_path)):
                if not f.lower().endswith((".png", ".webp", ".jpg", ".jpeg")):
                    continue
                abs_img_path = os.path.abspath(os.path.join(folder_path, f))
                if not _is_valid_sketch(abs_img_path):
                    continue

                # Relative path for cross-platform DB storage
                rel_path = _to_relative_path(abs_img_path)

                already_linked = existing_by_cs.get(target_cs.id, [])
                if rel_path not in already_linked:
                    # Upload immediately to Supabase Storage CDN
                    clean_p = target_cs.clean_part_number or clean_str(target_cs.part_number)
                    remote_path = f"{clean_p}/{f}"
                    public_url = upload_file_to_supabase(abs_img_path, remote_path)

                    # Fallback URL if Supabase upload fails
                    if b_dir == "storage/images":
                        rel_sub = rel_path[len("storage/images/"):].lstrip("/")
                        fallback_url = f"/media/images/{rel_sub}"
                    else:
                        rel_sub = rel_path[len("extracted_images/"):].lstrip("/")
                        fallback_url = f"/media/extracted/{rel_sub}"

                    pimg = PartImage(
                        checksheet_id=target_cs.id,
                        image_path=rel_path,          # Relative path — always cross-platform safe
                        image_url=public_url or fallback_url  # Prefer Supabase CDN
                    )
                    session.add(pimg)
                    already_linked.append(rel_path)
                    existing_by_cs[target_cs.id] = already_linked
                    new_linked_count += 1
                    updated_cs_count.add(target_cs.id)

    if new_linked_count > 0:
        await session.commit()

    # Recalculate summary stats
    total_images_in_db = len((await session.scalars(select(PartImage))).all())
    cs_with_images = len(set(await session.scalars(select(PartImage.checksheet_id).distinct())))

    return {
        "status": "success",
        "newly_linked_images": new_linked_count,
        "affected_checksheets": len(updated_cs_count),
        "total_part_images_in_db": total_images_in_db,
        "checksheets_with_images": cs_with_images,
        "total_checksheets": len(all_cs)
    }


if __name__ == "__main__":
    import asyncio
    async def main():
        async with AsyncSessionLocal() as session:
            res = await sync_all_part_images_to_db(session)
            print("Image Ingestion Result:", res)
    asyncio.run(main())
