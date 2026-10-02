"""
Storage Images Backup Utility for Summit FactoryHub Checksheet System.

Ensures 100% of all part drawing images (sketches) from Supabase Storage CDN
and local storage are verified and archived into storage/backups/images_backup/

Usage:
    python scripts/backup_storage_images.py
"""
import os
import sys
import time
import shutil
import urllib.request
import urllib.parse
from concurrent.futures import ThreadPoolExecutor, as_completed
import asyncio

ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)

from database.connection import AsyncSessionLocal
from database.models import PartImage
from sqlalchemy import select

BACKUP_IMAGES_DIR = os.path.join(ROOT_DIR, "storage", "backups", "images_backup")


def download_single_image(url: str, dest_path: str) -> bool:
    """Download an image from Supabase CDN to destination path if not exists."""
    try:
        if os.path.isfile(dest_path) and os.path.getsize(dest_path) > 500:
            return True
        os.makedirs(os.path.dirname(dest_path), exist_ok=True)
        urllib.request.urlretrieve(url, dest_path)
        return os.path.isfile(dest_path) and os.path.getsize(dest_path) > 0
    except Exception as e:
        return False


async def backup_all_images():
    t0 = time.time()
    os.makedirs(BACKUP_IMAGES_DIR, exist_ok=True)
    print("[*] Mengambil daftar seluruh gambar part dari database...")

    async with AsyncSessionLocal() as session:
        imgs = (await session.execute(select(PartImage))).scalars().all()

    total = len(imgs)
    print(f"[*] Ditemukan total {total} record gambar di database.")

    to_download = []
    already_local = 0

    for img in imgs:
        p = (img.image_path or "").replace("\\", "/")
        url = (img.image_url or "").strip()

        # Target relative path inside images_backup
        # e.g. 71246-BZ010/sketch_1.webp
        rel_sub = ""
        for marker in ["storage/images/", "extracted_images/"]:
            if marker in p:
                rel_sub = p[p.index(marker) + len(marker):]
                break
        if not rel_sub:
            if "storage/v1/object/public/image/" in url:
                rel_sub = url.split("storage/v1/object/public/image/", 1)[1]
            else:
                rel_sub = os.path.basename(p or url)

        dest_file = os.path.join(BACKUP_IMAGES_DIR, rel_sub.lstrip("/"))

        # 1. Check if already exists in storage/images
        local_src = os.path.join(ROOT_DIR, p) if not os.path.isabs(p) else p
        if os.path.isfile(local_src) and os.path.getsize(local_src) > 500:
            os.makedirs(os.path.dirname(dest_file), exist_ok=True)
            if not os.path.isfile(dest_file):
                shutil.copy2(local_src, dest_file)
            already_local += 1
            continue

        # 2. Check if already downloaded in backup directory
        if os.path.isfile(dest_file) and os.path.getsize(dest_file) > 500:
            already_local += 1
            continue

        # 3. Otherwise queue for download from CDN
        if url.startswith("http"):
            to_download.append((url, dest_file))

    print(f"[*] Gambar sudah tersimpan di lokal : {already_local}")
    print(f"[*] Gambar perlu diunduh dari Cloud  : {len(to_download)}")

    downloaded = 0
    failed = 0
    if to_download:
        print("[*] Memulai download paralel (10 worker)...")
        with ThreadPoolExecutor(max_workers=10) as executor:
            future_map = {
                executor.submit(download_single_image, u, d): (u, d)
                for u, d in to_download
            }
            for fut in as_completed(future_map):
                ok = fut.result()
                if ok:
                    downloaded += 1
                else:
                    failed += 1
                done_count = downloaded + failed
                if done_count % 50 == 0 or done_count == len(to_download):
                    print(f"    - Terunduh: {downloaded}/{len(to_download)}...")

    # Calculate backup total files & size
    total_backed_up = 0
    total_size = 0
    for root, _, files in os.walk(BACKUP_IMAGES_DIR):
        for f in files:
            total_backed_up += 1
            total_size += os.path.getsize(os.path.join(root, f))

    elapsed = round(time.time() - t0, 2)
    mb_size = round(total_size / (1024 * 1024), 2)
    print("\n" + "=" * 55)
    print(" [✓] BACKUP GAMBAR SELESAI!")
    print(f" Direktori Backup : {BACKUP_IMAGES_DIR}")
    print(f" Total File Gambar: {total_backed_up} file ({mb_size} MB)")
    print(f" Berhasil Diunduh : {downloaded}")
    print(f" Gagal            : {failed}")
    print(f" Waktu Proses     : {elapsed} detik")
    print("=" * 55)


if __name__ == "__main__":
    asyncio.run(backup_all_images())
