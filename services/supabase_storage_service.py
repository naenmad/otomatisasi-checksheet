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
    encoded_path = urllib.parse.quote(remote_path.lstrip("/"))
    return f"{SUPABASE_URL}/storage/v1/object/public/{BUCKET_NAME}/{encoded_path}"


def upload_file_to_supabase(local_path: str, remote_path: str) -> Optional[str]:
    """
    Upload a local file to Supabase Storage bucket synchronously.
    Returns public URL if successful, None otherwise.
    """
    if not os.path.isfile(local_path):
        return None

    encoded_path = urllib.parse.quote(remote_path.lstrip("/"))
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

        with urllib.request.urlopen(req, timeout=15) as resp:
            if resp.status in (200, 201):
                return get_public_url(remote_path)
    except Exception as e:
        logger.warning(f"Failed uploading {local_path} to Supabase: {e}")
        return None

    return None


async def sync_all_images_to_supabase_storage(session: AsyncSession) -> Dict[str, Any]:
    """
    Iterates over all PartImage records in the database, uploads missing files
    to the Supabase Storage bucket 'image', and updates image_url to the public CDN URL.
    """
    images = (await session.scalars(select(PartImage))).all()
    all_cs = (await session.scalars(select(Checksheet))).all()
    cs_map = {cs.id: cs for cs in all_cs}

    uploaded_count = 0
    already_synced = 0
    failed_count = 0

    print(f"[*] Memulai sinkronisasi {len(images)} gambar ke Supabase Storage bucket '{BUCKET_NAME}'...")

    for img in images:
        cs = cs_map.get(img.checksheet_id)
        if not cs:
            continue

        clean_p = cs.clean_part_number or clean_str(cs.part_number)
        filename = os.path.basename(img.image_path)
        remote_path = f"{clean_p}/{filename}"

        # If already pointing to public Supabase URL and exists, skip upload
        expected_url = get_public_url(remote_path)
        if img.image_url and img.image_url.startswith(f"{SUPABASE_URL}/storage/v1/object/public/{BUCKET_NAME}"):
            already_synced += 1
            continue

        # Upload file from disk
        if img.image_path and os.path.isfile(img.image_path):
            public_url = upload_file_to_supabase(img.image_path, remote_path)
            if public_url:
                img.image_url = public_url
                uploaded_count += 1
                if uploaded_count % 25 == 0:
                    print(f"[{uploaded_count}/{len(images)}] Diupload ke Supabase: {remote_path}")
            else:
                failed_count += 1
        else:
            failed_count += 1

    if uploaded_count > 0:
        await session.commit()

    print(f"[✓] Sinkronisasi Storage Selesai:")
    print(f"    - Berhasil Diupload : {uploaded_count}")
    print(f"    - Sudah Ada di Cloud: {already_synced}")
    print(f"    - Gagal / File Hilang: {failed_count}")

    return {
        "status": "success",
        "total_images": len(images),
        "uploaded_count": uploaded_count,
        "already_synced": already_synced,
        "failed_count": failed_count,
        "bucket": BUCKET_NAME
    }


if __name__ == "__main__":
    import asyncio
    async def main():
        async with AsyncSessionLocal() as session:
            await sync_all_images_to_supabase_storage(session)
    asyncio.run(main())
