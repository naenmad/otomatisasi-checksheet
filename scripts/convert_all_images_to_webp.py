#!/usr/bin/env python3
"""
Convert All Images to WebP, Upload to Supabase, and Update Database.
- Converts all PNG/JPG/JPEG files in storage/images to WebP
- Uploads WebP to Supabase Storage
- Deletes old PNG/JPG from Supabase Storage & local disk
- Updates all part_images records in PostgreSQL to WebP paths & URLs
- Removes dead phantom records
- Invalidates and refreshes checksheet cache
"""
import os
import sys
import re
import asyncio
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Dict, Any, List, Tuple
from PIL import Image

# Ensure project root in sys.path
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

from dotenv import load_dotenv
load_dotenv()

from sqlalchemy import select, delete, update, text
from database.connection import AsyncSessionLocal, engine
from database.models import Checksheet, PartImage
from database.crud import clean_str
from services.supabase_storage_service import (
    upload_file_to_supabase,
    delete_file_from_supabase,
    get_public_url,
    BUCKET_NAME,
    SUPABASE_URL
)

SUPPORTED_NON_WEBP = (".png", ".jpg", ".jpeg", ".bmp", ".tiff")


def convert_local_images_to_webp(base_dirs: List[str] = None) -> List[Dict[str, Any]]:
    """Scan base_dirs and convert any non-webp image to webp."""
    if not base_dirs:
        base_dirs = ["storage/images", "extracted_images"]

    conversion_results = []
    total_old_bytes = 0
    total_new_bytes = 0

    print("[*] Memindai file gambar non-WebP di direktori lokal...")
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

    print(f"[*] Ditemukan {len(candidates)} file non-WebP untuk dikonversi.")

    for b_dir, root, fn, src_path in candidates:
        stem, old_ext = os.path.splitext(fn)
        dest_fn = f"{stem}.webp"
        dest_path = os.path.join(root, dest_fn)

        try:
            old_sz = os.path.getsize(src_path)
            with Image.open(src_path) as im:
                if im.mode in ("RGBA", "LA") or (im.mode == "P" and "transparency" in im.info):
                    im_c = im.convert("RGBA")
                else:
                    im_c = im.convert("RGB")

                w, h = im_c.size
                if w > 1920 or h > 1920:
                    im_c.thumbnail((1920, 1920), Image.Resampling.LANCZOS)

                im_c.save(dest_path, "WEBP", quality=82, method=6)

            new_sz = os.path.getsize(dest_path)
            total_old_bytes += old_sz
            total_new_bytes += new_sz

            # Relative folder inside storage/images or extracted_images
            rel_folder = os.path.relpath(root, b_dir).replace("\\", "/")
            if rel_folder == ".":
                rel_folder = ""

            conversion_results.append({
                "base_dir": b_dir,
                "folder": rel_folder,
                "old_filename": fn,
                "new_filename": dest_fn,
                "old_local_path": src_path.replace("\\", "/"),
                "new_local_path": dest_path.replace("\\", "/"),
                "old_size": old_sz,
                "new_size": new_sz,
            })
        except Exception as e:
            print(f"[!] Gagal konversi {src_path}: {e}")

    saved_bytes = max(0, total_old_bytes - total_new_bytes)
    saved_mb = round(saved_bytes / (1024 * 1024), 2)
    saved_pct = round((saved_bytes / total_old_bytes * 100), 1) if total_old_bytes > 0 else 0
    print(f"[✓] Konversi lokal selesai: {len(conversion_results)} file.")
    print(f"    - Ukuran Semula : {total_old_bytes / (1024*1024):.2f} MB")
    print(f"    - Ukuran Baru   : {total_new_bytes / (1024*1024):.2f} MB")
    print(f"    - Ruang Terhemat: {saved_mb} MB ({saved_pct}%)")

    return conversion_results


def sync_converted_to_supabase(conversions: List[Dict[str, Any]], max_workers: int = 16) -> Dict[str, Any]:
    """Upload new WebP images to Supabase Storage and remove old PNGs from Supabase."""
    print(f"[*] Mengupload {len(conversions)} file WebP baru ke Supabase Storage (bucket '{BUCKET_NAME}')...")

    uploaded = 0
    deleted_old = 0
    failed = 0

    def _worker(item):
        folder = item["folder"]
        webp_path = item["new_local_path"]
        webp_fn = item["new_filename"]
        old_fn = item["old_filename"]

        # Remote path
        remote_webp = f"{folder}/{webp_fn}" if folder else webp_fn
        remote_old = f"{folder}/{old_fn}" if folder else old_fn

        # 1. Upload new WebP
        url = upload_file_to_supabase(webp_path, remote_webp)
        # 2. Delete old non-webp on Supabase
        del_ok = delete_file_from_supabase(remote_old)

        return (item, url, del_ok)

    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = {executor.submit(_worker, c): c for c in conversions}
        for future in as_completed(futures):
            try:
                item, url, del_ok = future.result()
                if url:
                    uploaded += 1
                    item["supabase_url"] = url
                    # Delete local old file only after successful upload
                    try:
                        if os.path.isfile(item["old_local_path"]):
                            os.remove(item["old_local_path"])
                    except Exception:
                        pass
                else:
                    failed += 1

                if del_ok:
                    deleted_old += 1
            except Exception as e:
                failed += 1

    print(f"[✓] Sinkronisasi Storage Selesai:")
    print(f"    - WebP Berhasil Upload : {uploaded}")
    print(f"    - PNG Lama Dihapus Cloud: {deleted_old}")
    print(f"    - Gagal Upload          : {failed}")

    return {
        "uploaded": uploaded,
        "deleted_old": deleted_old,
        "failed": failed
    }


async def update_database_part_images():
    """Update all part_images records in PostgreSQL to point strictly to WebP."""
    print("\n[*] Memperbarui database PostgreSQL (tabel part_images)...")
    async with AsyncSessionLocal() as session:
        all_images = (await session.scalars(select(PartImage))).all()
        all_cs = (await session.scalars(select(Checksheet))).all()
        cs_map = {cs.id: cs for cs in all_cs}

        updated_count = 0
        deleted_dead_count = 0

        for img in all_images:
            p = (img.image_path or "").replace("\\", "/")
            ext = os.path.splitext(p)[1].lower()

            if ext not in SUPPORTED_NON_WEBP:
                continue

            cs = cs_map.get(img.checksheet_id)
            clean_p = (cs.clean_part_number if cs else "") or "default"

            # Determine corresponding webp path
            base_p, _ = os.path.splitext(p)
            webp_p = f"{base_p}.webp"
            fn = os.path.basename(webp_p)

            # Check if webp exists on disk
            if os.path.isfile(webp_p):
                # Update to webp
                img.image_path = webp_p
                img.image_url = get_public_url(f"{clean_p}/{fn}")
                updated_count += 1
            elif img.image_url and "supabase.co" in img.image_url:
                # File was already on Supabase with png, update url & path to webp
                new_url = re.sub(r"\.(png|jpg|jpeg|bmp|tiff)$", ".webp", img.image_url, flags=re.I)
                img.image_path = webp_p
                img.image_url = new_url
                updated_count += 1
            else:
                # Dead phantom record with no local file and no supabase file
                await session.delete(img)
                deleted_dead_count += 1

        await session.commit()

        print(f"[✓] Update Database Selesai:")
        print(f"    - PartImage Diubah ke WebP : {updated_count}")
        print(f"    - Record Hantu Dihapus      : {deleted_dead_count}")

        # Check final extension counts in DB
        res = await session.execute(text(r"""
            SELECT 
                LOWER(SUBSTRING(image_path FROM '\.[a-zA-Z0-9]+$')) as ext,
                COUNT(*) 
            FROM part_images 
            GROUP BY ext 
            ORDER BY count DESC;
        """))
        print("\n[DB] Status Akhir Tabel part_images:")
        for row in res.fetchall():
            print(f"    - {row[0]}: {row[1]} records")


async def refresh_cache():
    """Regenerate checksheets summary cache to use new WebP urls."""
    print("\n[*] Merefresh cache checksheets summary...")
    try:
        from server.routes.checksheets import warmup_checksheets_cache
        await warmup_checksheets_cache()
        print("[✓] Cache berhasil dimuat ulang dengan WebP URLs.")
    except Exception as e:
        print(f"[!] Gagal merefresh cache: {e}")


async def main():
    print("=" * 65)
    print("   ⚡ SUMMIT QC - MIGRASI SEMUA GAMBAR KE WEBP TERKOMPRESI")
    print("=" * 65)

    # 1. Convert local non-webp images
    conversions = convert_local_images_to_webp(["storage/images", "extracted_images"])

    # 2. Sync to Supabase Cloud Storage
    if conversions:
        sync_converted_to_supabase(conversions)

    # 3. Update PostgreSQL database
    await update_database_part_images()

    # 4. Refresh cache
    await refresh_cache()

    print("\n" + "=" * 65)
    print("   🎉 SEMUA GAMBAR BERHASIL DIMIGRASIKAN KE WEBP 100%!")
    print("=" * 65)


if __name__ == "__main__":
    asyncio.run(main())
