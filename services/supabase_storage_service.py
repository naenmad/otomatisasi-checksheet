"""
Supabase Cloud Storage Service for Checksheet Drawing Images.

Uploads local sketch drawings to Supabase Storage bucket ('image')
and updates PartImage records in the database with public CDN URLs:
https://pkccxrqjnnhgjalcpnot.supabase.co/storage/v1/object/public/image/{clean_part}/{filename}
"""
import os
import re
import urllib.request
import urllib.parse
import mimetypes
import logging
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Dict, Any, List, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from database.connection import AsyncSessionLocal
from database.models import Checksheet, PartImage
from database.crud import clean_str

logger = logging.getLogger("supabase_storage")

SUPABASE_URL = os.getenv("SUPABASE_URL", "https://pkccxrqjnnhgjalcpnot.supabase.co").strip().rstrip("/")
SUPABASE_KEY = os.getenv("SUPABASE_KEY", "sb_publishable_ffPoXsFoLE3wFZjszPtSMQ_pfhPbdw6").strip()
BUCKET_NAME = "image"


def get_public_url(remote_path: str) -> str:
    """Generate public CDN URL for an object in the 'image' bucket."""
    encoded_path = urllib.parse.quote(remote_path.lstrip("/"), safe="/-_.~")
    return f"{SUPABASE_URL}/storage/v1/object/public/{BUCKET_NAME}/{encoded_path}"


def upload_file_to_supabase(local_path: str, remote_path: str) -> Optional[str]:
    """
    Upload a local file to Supabase Storage bucket synchronously.
    Returns public CDN URL if successful, None otherwise.
    """
    if not os.path.isfile(local_path):
        return None

    encoded_path = urllib.parse.quote(remote_path.lstrip("/"), safe="/-_.~")
    endpoint = f"{SUPABASE_URL}/storage/v1/object/{BUCKET_NAME}/{encoded_path}"

    mime_type, _ = mimetypes.guess_type(local_path)
    if not mime_type:
        mime_type = "image/webp" if local_path.lower().endswith(".webp") else "image/png"

    try:
        with open(local_path, "rb") as f:
            file_data = f.read()

        req = urllib.request.Request(
            endpoint,
            data=file_data,
            headers={
                "apikey": SUPABASE_KEY,
                "Authorization": f"Bearer {SUPABASE_KEY}",
                "Content-Type": mime_type,
                "x-upsert": "true"
            },
            method="POST"
        )

        with urllib.request.urlopen(req, timeout=30) as resp:
            if resp.status in (200, 201):
                return get_public_url(remote_path)
    except Exception as e:
        logger.warning(f"Failed uploading {local_path} to Supabase: {e}")
        return None

    return None


def upload_image_to_supabase(local_path: str, clean_part: str, filename: str) -> Optional[str]:
    """Helper used by upload route to upload directly to Supabase storage."""
    clean_p = clean_str(clean_part) or "default"
    remote_path = f"{clean_p}/{filename}"
    return upload_file_to_supabase(local_path, remote_path)


def delete_file_from_supabase(remote_path: str) -> bool:
    """Delete an object from Supabase Storage bucket."""
    encoded_path = urllib.parse.quote(remote_path.lstrip("/"), safe="/-_.~")
    endpoint = f"{SUPABASE_URL}/storage/v1/object/{BUCKET_NAME}/{encoded_path}"
    try:
        req = urllib.request.Request(
            endpoint,
            headers={
                "apikey": SUPABASE_KEY,
                "Authorization": f"Bearer {SUPABASE_KEY}"
            },
            method="DELETE"
        )
        with urllib.request.urlopen(req, timeout=15) as resp:
            return resp.status in (200, 204)
    except Exception as e:
        logger.warning(f"Failed deleting {remote_path} from Supabase: {e}")
        return False


def _resolve_local_image_path(img: PartImage, cs: Optional[Checksheet]) -> Optional[str]:
    """Helper to locate the actual image file on disk across different platforms."""
    raw_path = (img.image_path or "").replace("\\", "/")
    
    # 1. Direct path check
    if raw_path and os.path.isfile(raw_path):
        return raw_path

    # 2. Check normalized relative path
    for prefix in ["storage/images/", "extracted_images/"]:
        if prefix in raw_path:
            rel = raw_path[raw_path.index(prefix):]
            if os.path.isfile(rel):
                return rel

    # 3. Check candidate folders based on checksheet part number
    filename = os.path.basename(raw_path) if raw_path else ""
    if cs and filename:
        clean_p = cs.clean_part_number or clean_str(cs.part_number)
        norm_p = re.sub(r"[^0-9A-Za-z_-]", "_", cs.part_number)
        for base in ["storage/images", "extracted_images"]:
            for folder in [clean_p, cs.part_number, norm_p]:
                cand = os.path.join(base, folder, filename)
                if os.path.isfile(cand):
                    return cand

    return None


async def sync_all_images_to_supabase_storage(session: AsyncSession, max_workers: int = 12) -> Dict[str, Any]:
    """
    Iterates over all PartImage records in the database, uploads missing files
    to the Supabase Storage bucket 'image' concurrently, and updates image_url to the public CDN URL.
    """
    images = (await session.scalars(select(PartImage))).all()
    all_cs = (await session.scalars(select(Checksheet))).all()
    cs_map = {cs.id: cs for cs in all_cs}

    tasks_to_upload = []
    already_synced = 0
    missing_on_disk = 0

    print(f"[*] Menyiapkan sinkronisasi {len(images)} gambar ke Supabase Storage bucket '{BUCKET_NAME}'...")

    for img in images:
        cs = cs_map.get(img.checksheet_id)
        if not cs:
            continue

        clean_p = cs.clean_part_number or clean_str(cs.part_number)
        raw_path = (img.image_path or "").replace("\\", "/")
        filename = os.path.basename(raw_path) if raw_path else "sketch.png"
        remote_path = f"{clean_p}/{filename}"

        # If already pointing to public Supabase URL and exists, skip upload
        if img.image_url and img.image_url.startswith(f"{SUPABASE_URL}/storage/v1/object/public/{BUCKET_NAME}"):
            already_synced += 1
            continue

        local_file = _resolve_local_image_path(img, cs)
        if local_file:
            tasks_to_upload.append((img, local_file, remote_path))
        else:
            missing_on_disk += 1

    print(f"[*] {len(tasks_to_upload)} gambar siap diupload (Sudah cloud: {already_synced}, Tidak ada di disk: {missing_on_disk}).")
    print(f"[*] Mengupload dengan {max_workers} worker threads...")

    uploaded_count = 0
    failed_count = 0

    def _worker(item):
        img_obj, loc_path, rem_path = item
        res_url = upload_file_to_supabase(loc_path, rem_path)
        return (img_obj, res_url, rem_path)

    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = {executor.submit(_worker, item): item for item in tasks_to_upload}
        for future in as_completed(futures):
            try:
                img_obj, res_url, rem_path = future.result()
                if res_url:
                    img_obj.image_url = res_url
                    uploaded_count += 1
                    if uploaded_count % 50 == 0 or uploaded_count == len(tasks_to_upload):
                        print(f"[{uploaded_count}/{len(tasks_to_upload)}] Berhasil upload: {rem_path}")
                else:
                    failed_count += 1
            except Exception as e:
                failed_count += 1

    if uploaded_count > 0:
        await session.commit()

    print(f"\n[✓] Sinkronisasi Supabase Storage Selesai:")
    print(f"    - Berhasil Diupload : {uploaded_count}")
    print(f"    - Sudah Ada di Cloud: {already_synced}")
    print(f"    - Gagal Upload      : {failed_count}")
    print(f"    - Tidak Ada di Disk : {missing_on_disk}")
    print(f"    - Total Gambar      : {len(images)}")

    return {
        "status": "success",
        "total_images": len(images),
        "uploaded_count": uploaded_count,
        "already_synced": already_synced,
        "failed_count": failed_count,
        "missing_on_disk": missing_on_disk,
        "bucket": BUCKET_NAME
    }


if __name__ == "__main__":
    import asyncio
    async def main():
        async with AsyncSessionLocal() as session:
            await sync_all_images_to_supabase_storage(session)
    asyncio.run(main())
