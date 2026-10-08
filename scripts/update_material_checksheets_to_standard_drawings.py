"""
Update the 63 Material checksheets that originated from the subcont folder:
1. Replace drawings with BOTH standard webp templates:
   - material_coil.webp: https://nthmzrfyaxycheugjpzo.supabase.co/storage/v1/object/public/image/templates/material_coil.webp
   - material_sheet.webp: https://nthmzrfyaxycheugjpzo.supabase.co/storage/v1/object/public/image/templates/material_sheet.webp
2. Set status to 'Siap Kirim' (keeping already submitted ones as Checksheet Done).
3. Regenerate disk summary cache and refresh server cache.
"""
import asyncio
import os
import json
import re
from database.connection import AsyncSessionLocal
from database.models import Checksheet, PartImage, ActivityLog
from sqlalchemy import select, delete

COIL_IMG_URL = "https://nthmzrfyaxycheugjpzo.supabase.co/storage/v1/object/public/image/templates/material_coil.webp"
SHEET_IMG_URL = "https://nthmzrfyaxycheugjpzo.supabase.co/storage/v1/object/public/image/templates/material_sheet.webp"

def clean_part_no(pn: str) -> str:
    return re.sub(r"[^A-Za-z0-9]", "", pn)

async def main():
    async with AsyncSessionLocal() as session:
        # Fetch all Material checksheets coming from SUBCONT folder
        res = await session.execute(
            select(Checksheet)
            .where(
                Checksheet.category == "Incomming Material",
                Checksheet.raw_file_path.like("%SUBCONT%")
            )
            .order_by(Checksheet.id)
        )
        items = res.scalars().all()
        print(f"[1] Found {len(items)} checksheets to update.")

        updated_count = 0
        images_updated = 0

        for cs in items:
            clean_pn = clean_part_no(cs.part_number) or f"cs_{cs.id}"
            
            # Delete existing images for this checksheet
            await session.execute(
                delete(PartImage).where(PartImage.checksheet_id == cs.id)
            )

            # Insert Image 1: Coil
            coil_img = PartImage(
                checksheet_id=cs.id,
                image_path=f"storage/images/{clean_pn}/material_coil.webp",
                image_url=COIL_IMG_URL
            )
            session.add(coil_img)

            # Insert Image 2: Sheet
            sheet_img = PartImage(
                checksheet_id=cs.id,
                image_path=f"storage/images/{clean_pn}/material_sheet.webp",
                image_url=SHEET_IMG_URL
            )
            session.add(sheet_img)
            images_updated += 2

            # Update status to Siap Kirim (preserve Checksheet Done if already submitted)
            if cs.status != "Checksheet Done":
                cs.status = "Siap Kirim"
                cs.keterangan = "Siap kirim ke FactoryHub"
            
            # Activity Log
            log = ActivityLog(
                action="UPDATE_IMAGES_AND_STATUS",
                part_number=cs.part_number,
                operator="System",
                status="SUCCESS",
                details=f"Update drawing webp (coil & sheet) dan status Siap Kirim (CS IQC Material)"
            )
            session.add(log)
            updated_count += 1

        await session.commit()
        print(f"[2] Successfully updated {updated_count} checksheets with {images_updated} standard drawings.")

    # Regenerate local disk summary cache
    print("[3] Regenerating disk summary cache...")
    from database.crud import get_checksheets_summary_list
    async with AsyncSessionLocal() as session:
        raw_list = await get_checksheets_summary_list(
            session=session,
            assigned_to=None,
            status=None,
            search=None,
            limit=5000,
            offset=0
        )
        cache_file = "data/checksheets_summary_cache.json"
        tmp_file = cache_file + ".tmp"
        with open(tmp_file, "w", encoding="utf-8") as f:
            json.dump(raw_list, f, ensure_ascii=False)
        os.replace(tmp_file, cache_file)
        print(f"[4] Persisted {len(raw_list)} checksheets to {cache_file}.")

if __name__ == "__main__":
    asyncio.run(main())
