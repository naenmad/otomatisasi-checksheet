"""
Script to fix misclassified checksheets in database:
1. 62 checksheets from CS IQC SUBCONT that are actually Material (Sheet/Coil/Blank) -> Incomming Material
2. 26 checksheets from CS IQC SUBCONT that are actually Standard Parts (Nut/Bolt/Fastener) -> Incomming Std Part
3. 2 checksheets in TCF HPM that were erroneously set to Incomming Material -> Incomming Subcont Part
4. Synchronize status with FactoryHub catalog and attach standard material sketches if missing.
5. Refresh local summary cache.
"""
import asyncio
import os
import json
from datetime import datetime
from database.connection import AsyncSessionLocal
from database.models import Checksheet, PartImage, ActivityLog
from sqlalchemy import select

# Standard templates URLs for Material
SHEET_IMG_URL = "https://nthmzrfyaxycheugjpzo.supabase.co/storage/v1/object/public/image/templates/material_sheet.webp"
COIL_IMG_URL = "https://nthmzrfyaxycheugjpzo.supabase.co/storage/v1/object/public/image/templates/material_coil.webp"

async def run_fix():
    catalog_path = "data/factoryhub_catalog.json"
    if not os.path.exists(catalog_path):
        print("Error: factoryhub_catalog.json not found")
        return

    with open(catalog_path, "r", encoding="utf-8") as f:
        catalog_data = json.load(f)
    catalog_parts = set(p["part_number"].strip() for p in catalog_data.get("parts", []))
    print(f"[1] Loaded {len(catalog_parts)} catalog parts from FactoryHub.")

    async with AsyncSessionLocal() as session:
        res = await session.execute(select(Checksheet))
        all_checksheets = res.scalars().all()
        print(f"[2] Total checksheets in DB: {len(all_checksheets)}")

        to_material_count = 0
        to_std_count = 0
        to_subcont_count = 0
        images_added = 0

        for cs in all_checksheets:
            rf = (cs.raw_file_path or "").replace("\\", "/").upper()
            pn_clean = cs.part_number.strip()
            in_catalog = pn_clean in catalog_parts

            # 1. Misclassified Material
            if any(k in rf for k in ["IQC SHEET.XLSX", "IQC COIL.XLSX", "BLANK"]) and cs.category != "Incomming Material":
                cs.category = "Incomming Material"
                to_material_count += 1
                
                # Align status
                if in_catalog:
                    if cs.status in ["Tidak Ada Part", "Perlu Revisi Gambar", "DRAFT", "TIDAK_ADA_PART"]:
                        cs.status = "Siap Kirim"
                        cs.keterangan = "Siap kirim ke FactoryHub (Material)"
                else:
                    cs.status = "Tidak Ada Part"
                    cs.keterangan = "Part belum terdaftar di Master Part FactoryHub"

                # Check if image exists
                img_res = await session.execute(select(PartImage).where(PartImage.checksheet_id == cs.id))
                existing_imgs = img_res.scalars().all()
                if not existing_imgs:
                    is_coil = "COIL" in rf
                    img_url = COIL_IMG_URL if is_coil else SHEET_IMG_URL
                    img_path = f"storage/images/global/{'material_coil.webp' if is_coil else 'material_sheet.webp'}"
                    new_img = PartImage(
                        checksheet_id=cs.id,
                        image_path=img_path,
                        image_url=img_url
                    )
                    session.add(new_img)
                    images_added += 1

                # Log activity
                log = ActivityLog(
                    action="UPDATE_CATEGORY",
                    part_number=cs.part_number,
                    operator="System",
                    status="SUCCESS",
                    details=f"Koreksi kategori ke Incomming Material ({os.path.basename(cs.raw_file_path)})"
                )
                session.add(log)

            # 2. Misclassified Std Part (Nut & Fasteners)
            elif any(k in rf for k in ["C.SHEET NUT.XLSX", "STD PART"]) and cs.category != "Incomming Std Part":
                cs.category = "Incomming Std Part"
                to_std_count += 1

                # Align status
                if in_catalog:
                    if cs.status in ["Tidak Ada Part", "Perlu Revisi Gambar", "DRAFT", "TIDAK_ADA_PART"]:
                        cs.status = "Siap Kirim"
                        cs.keterangan = "Siap kirim ke FactoryHub (Std Part)"
                else:
                    cs.status = "Tidak Ada Part"
                    cs.keterangan = "Part belum terdaftar di Master Part FactoryHub"

                log = ActivityLog(
                    action="UPDATE_CATEGORY",
                    part_number=cs.part_number,
                    operator="System",
                    status="SUCCESS",
                    details=f"Koreksi kategori ke Incomming Std Part ({os.path.basename(cs.raw_file_path)})"
                )
                session.add(log)

            # 3. Misclassified Subcont (TCF HPM parts ID 445, 447)
            elif "TCF HPM" in rf and cs.category == "Incomming Material":
                cs.category = "Incomming Subcont Part"
                to_subcont_count += 1
                if in_catalog:
                    if cs.status in ["Tidak Ada Part", "DRAFT", "TIDAK_ADA_PART"]:
                        cs.status = "Siap Kirim"
                        cs.keterangan = "Siap kirim ke FactoryHub (Subcont Part)"
                else:
                    cs.status = "Tidak Ada Part"
                    cs.keterangan = "Part belum terdaftar di Master Part FactoryHub"

                log = ActivityLog(
                    action="UPDATE_CATEGORY",
                    part_number=cs.part_number,
                    operator="System",
                    status="SUCCESS",
                    details=f"Koreksi kategori ke Incomming Subcont Part ({os.path.basename(cs.raw_file_path)})"
                )
                session.add(log)

        await session.commit()
        print(f"[3] Successfully committed changes to database:")
        print(f"    - Converted to Incomming Material: {to_material_count}")
        print(f"    - Converted to Incomming Std Part: {to_std_count}")
        print(f"    - Converted to Incomming Subcont: {to_subcont_count}")
        print(f"    - Standard Material Drawings Added: {images_added}")

    # Regenerate local summary cache
    print("[4] Regenerating cache...")
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
        print(f"[5] Saved {len(raw_list)} checksheets to {cache_file}.")

if __name__ == "__main__":
    asyncio.run(run_fix())
