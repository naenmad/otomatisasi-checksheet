"""
Batch update for all 'Incomming Material' checksheets:
1. Convert temp images to WebP templates.
2. Remove old drawings across all statuses.
3. Attach both WebP drawings (Coil & Sheet) with Cloud CDN URLs.
4. Set status of all 253 checksheets to 'Siap Kirim'.
5. Update server and local caches.
"""
import os
import shutil
from datetime import datetime
from PIL import Image
import asyncio
from sqlalchemy import select, delete

from database.connection import AsyncSessionLocal
from database.models import Checksheet, PartImage
from database.crud import clean_str
from services.supabase_storage_service import upload_file_to_supabase, SUPABASE_URL

async def main():
    print("[*] 1. Memeriksa file sumber gambar...")
    src_coil = "temp/image copy.png"
    src_sheet = "temp/image.png"

    if not os.path.isfile(src_coil) or not os.path.isfile(src_sheet):
        raise FileNotFoundError(f"File gambar sumber tidak ditemukan: {src_coil} atau {src_sheet}")

    os.makedirs("storage/templates", exist_ok=True)
    tpl_coil_path = "storage/templates/material_coil.webp"
    tpl_sheet_path = "storage/templates/material_sheet.webp"

    # Convert to WebP
    im_coil = Image.open(src_coil)
    im_coil.save(tpl_coil_path, "WEBP", quality=85, method=6)

    im_sheet = Image.open(src_sheet)
    im_sheet.save(tpl_sheet_path, "WEBP", quality=85, method=6)

    print(f"[✓] Gambar berhasil dikonversi ke WebP:")
    print(f"    - Coil: {tpl_coil_path} ({os.path.getsize(tpl_coil_path)} bytes)")
    print(f"    - Sheet: {tpl_sheet_path} ({os.path.getsize(tpl_sheet_path)} bytes)")

    # Upload templates to Supabase Cloud Storage
    print("[*] 2. Mengunggah template WebP ke Supabase Storage...")
    url_coil = upload_file_to_supabase(tpl_coil_path, "templates/material_coil.webp")
    url_sheet = upload_file_to_supabase(tpl_sheet_path, "templates/material_sheet.webp")

    if not url_coil or not url_sheet:
        raise RuntimeError("Gagal mengunggah template ke Supabase Storage!")

    print(f"[✓] Template Cloud CDN aktif:")
    print(f"    - Coil CDN: {url_coil}")
    print(f"    - Sheet CDN: {url_sheet}")

    print("[*] 3. Memproses seluruh part 'Incomming Material'...")
    async with AsyncSessionLocal() as db:
        res = await db.execute(
            select(Checksheet).where(Checksheet.category == "Incomming Material")
        )
        checksheets = res.scalars().all()
        print(f"[*] Ditemukan {len(checksheets)} checksheet Incomming Material.")

        total_old_deleted = 0
        now = datetime.utcnow()

        for cs in checksheets:
            clean_p = cs.clean_part_number or clean_str(cs.part_number)
            part_dir = os.path.join("storage", "images", clean_p)
            os.makedirs(part_dir, exist_ok=True)

            # Copy local webp drawings to each part folder
            local_coil = os.path.join(part_dir, "material_coil.webp")
            local_sheet = os.path.join(part_dir, "material_sheet.webp")
            shutil.copyfile(tpl_coil_path, local_coil)
            shutil.copyfile(tpl_sheet_path, local_sheet)

            # Delete old PartImage records
            old_imgs = await db.execute(
                select(PartImage).where(PartImage.checksheet_id == cs.id)
            )
            for old_img in old_imgs.scalars().all():
                await db.delete(old_img)
                total_old_deleted += 1

            # Insert Image 1 (Coil) and Image 2 (Sheet)
            img1 = PartImage(
                checksheet_id=cs.id,
                image_path=local_coil.replace("\\", "/"),
                image_url=url_coil
            )
            img2 = PartImage(
                checksheet_id=cs.id,
                image_path=local_sheet.replace("\\", "/"),
                image_url=url_sheet
            )
            db.add(img1)
            db.add(img2)

            # Update checksheet status and timestamp
            cs.status = "Siap Kirim"
            cs.updated_at = now

        await db.commit()
        print(f"[✓] Berhasil menghapus {total_old_deleted} gambar lama.")
        print(f"[✓] Berhasil menambahkan 2 gambar WebP baru untuk seluruh {len(checksheets)} part.")
        print(f"[✓] Berhasil mengubah status seluruh {len(checksheets)} part menjadi 'Siap Kirim'.")

if __name__ == "__main__":
    asyncio.run(main())
