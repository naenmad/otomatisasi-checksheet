"""
Utility script to scan all local images on disk (storage/images/)
and upload any missing images to Supabase Cloud Storage,
then link them into the Supabase PostgreSQL database.

Usage (on any laptop, e.g. Iqbal's Windows laptop):
    python scripts/sync_local_images_to_cloud.py
"""
import os
import re
import sys
import glob
from datetime import datetime
from dotenv import load_dotenv

# Ensure root dir is in sys.path
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

load_dotenv()

from database.connection import AsyncSessionLocal
from database.models import Checksheet, PartImage
from database.crud import clean_str
from services.supabase_storage_service import upload_file_to_supabase, SUPABASE_URL, BUCKET_NAME
from sqlalchemy import select
from sqlalchemy.orm import selectinload
import asyncio


SUPPORTED_EXT = (".webp", ".png", ".jpg", ".jpeg")


async def sync_disk_to_cloud():
    print("=" * 60, flush=True)
    print("   SINKRONISASI GAMBAR LOKAL KE SUPABASE CLOUD   ", flush=True)
    print("=" * 60, flush=True)
    print(f"[*] Target Supabase: {SUPABASE_URL}", flush=True)
    print(f"[*] Target Bucket  : {BUCKET_NAME}", flush=True)

    storage_dir = os.path.join(BASE_DIR, "storage", "images")
    if not os.path.isdir(storage_dir):
        print(f"[!] Direktori {storage_dir} tidak ditemukan!", flush=True)
        return

    # 1. Fetch checksheets from Cloud DB
    print("[*] Mengambil data checksheet dari database Supabase Cloud...", flush=True)
    async with AsyncSessionLocal() as session:
        res = await session.execute(
            select(Checksheet).options(selectinload(Checksheet.images))
        )
        all_cs = res.scalars().all()

    print(f"[✓] Berhasil memuat {len(all_cs)} checksheet dari Cloud.", flush=True)

    # Build mapping
    cs_by_clean = {}
    cs_by_raw = {}
    for cs in all_cs:
        c_p = clean_str(cs.part_number)
        if c_p:
            cs_by_clean[c_p.lower()] = cs
        if cs.part_number:
            cs_by_raw[cs.part_number.lower()] = cs

    # 2. Scan folders in storage/images
    folders = [f for f in os.listdir(storage_dir) if os.path.isdir(os.path.join(storage_dir, f))]
    print(f"[*] Menemukan {len(folders)} folder part di {storage_dir}.", flush=True)

    total_uploaded = 0
    total_linked = 0
    total_skipped = 0

    batch_size = 10
    pending_commits = 0

    async with AsyncSessionLocal() as session:
        for idx, folder_name in enumerate(folders, 1):
            folder_path = os.path.join(storage_dir, folder_name)
            files = sorted([
                f for f in os.listdir(folder_path)
                if os.path.splitext(f)[1].lower() in SUPPORTED_EXT
            ])

            if not files:
                continue

            # Match checksheet
            clean_name = clean_str(folder_name) or folder_name
            target_cs = cs_by_clean.get(clean_name.lower()) or cs_by_raw.get(folder_name.lower())

            if not target_cs:
                continue

            # Re-fetch CS in current session to attach
            cs_res = await session.execute(
                select(Checksheet).options(selectinload(Checksheet.images)).where(Checksheet.id == target_cs.id)
            )
            cs_db = cs_res.scalar_one_or_none()
            if not cs_db:
                continue

            existing_img_filenames = set()
            for img in cs_db.images:
                fn = os.path.basename((img.image_path or img.image_url or "").replace("\\", "/"))
                if fn:
                    existing_img_filenames.add(fn.lower())

            clean_p = clean_str(cs_db.part_number) or folder_name
            cs_modified = False

            for f in files:
                local_file = os.path.join(folder_path, f)
                remote_path = f"{clean_p}/{f}"
                rel_path = f"storage/images/{folder_name}/{f}".replace("\\", "/")

                # Upload to Supabase Storage (upsert)
                remote_url = upload_file_to_supabase(local_file, remote_path)
                if not remote_url:
                    print(f"    [!] Gagal upload {local_file}", flush=True)
                    continue

                total_uploaded += 1

                # Check if already linked in PartImage
                if f.lower() not in existing_img_filenames:
                    pi = PartImage(
                        checksheet_id=cs_db.id,
                        image_path=rel_path,
                        image_url=remote_url
                    )
                    session.add(pi)
                    existing_img_filenames.add(f.lower())
                    total_linked += 1
                    cs_modified = True
                    print(f"    [+] Link baru: Part {cs_db.part_number} -> {f}", flush=True)
                else:
                    # Check if existing URL needs update to Cloud CDN
                    for img in cs_db.images:
                        fn = os.path.basename((img.image_path or img.image_url or "").replace("\\", "/"))
                        if fn.lower() == f.lower() and not (img.image_url or "").startswith("http"):
                            img.image_url = remote_url
                            cs_modified = True
                            print(f"    [*] Update URL: Part {cs_db.part_number} -> {f} ke Cloud CDN", flush=True)
                    total_skipped += 1

            if cs_modified:
                cs_db.updated_at = datetime.utcnow()
                pending_commits += 1

            if pending_commits >= batch_size:
                await session.commit()
                pending_commits = 0
                print(f"[PROGRESS {idx}/{len(folders)}] {total_uploaded} diupload, {total_linked} di-link ke DB...", flush=True)

        if pending_commits > 0:
            await session.commit()

    print("\n" + "=" * 60, flush=True)
    print("           SINKRONISASI SELESAI DENGAN SUKSES!           ", flush=True)
    print("=" * 60, flush=True)
    print(f"  - Total File Terupload ke Supabase Cloud : {total_uploaded}", flush=True)
    print(f"  - Total Gambar Baru Ter-link ke Database : {total_linked}", flush=True)
    print(f"  - Total Gambar Yang Sudah Ada            : {total_skipped}", flush=True)
    print("=" * 60, flush=True)
    print("Sekarang semua laptop dapat melihat seluruh gambar secara instan!\n", flush=True)


if __name__ == "__main__":
    asyncio.run(sync_disk_to_cloud())
