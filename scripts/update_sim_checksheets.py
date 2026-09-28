"""
Update SIM Subcontractor Checksheets with extracted inspection points and drawings.
"""
import os
import sys
import zipfile
import asyncio
import openpyxl
from sqlalchemy import select, delete, func

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

from database.connection import AsyncSessionLocal
from database.models import Checksheet, InspectionPoint, PartImage
from database.crud import log_activity
from parsers.smart_parser import FuzzyToolNormalizer
from parsers.image_extractor import get_workbook_sheet_drawing_map, extract_sheet_images
from scripts.import_cs_subcont import (
    get_cell_value,
    parse_subcont_sheet_meta,
    parse_subcont_sheet_points,
    clean_str,
    DUMMY_SHEETS
)
from services.google_sheets_service import sync_all_checksheets_to_sheet


async def update_sim_checksheets():
    sim_dir = "documents/CS INCOMING/CS IQC SUBCONT/C. sheet SIM"
    blank_sim_dir = "documents/CS INCOMING/CS IQC SUBCONT/c. sheet blank SIM & MMKI"
    target_files = [
        os.path.join(sim_dir, "CS subcont SIM (Autosaved).xlsx"),
        os.path.join(sim_dir, "04. IQC Subcont Part ytb..xlsx"),
        os.path.join(sim_dir, "b.baterai.xlsx"),
        os.path.join(sim_dir, "c.sheet subcont amc.xlsx"),
        os.path.join(blank_sim_dir, "Copy of C.SHEET  BLANK SIM MMKI..xlsx")
    ]

    print("=== STARTING SIM CHECKSHEETS UPDATE ===")
    
    async with AsyncSessionLocal() as session:
        # Pre-fetch all checksheets
        res = await session.execute(select(Checksheet))
        db_checksheets = {cs.clean_part_number: cs for cs in res.scalars().all()}
        print(f"Total checksheets loaded from DB: {len(db_checksheets)}")

        total_pts_added = 0
        total_imgs_added = 0
        updated_parts = []

        for fp in target_files:
            if not os.path.exists(fp):
                continue
            fname = os.path.basename(fp)
            print(f"\n[*] Processing file: {fname}")

            z_archive = zipfile.ZipFile(fp, "r") if zipfile.is_zipfile(fp) else None
            drawing_map = get_workbook_sheet_drawing_map(z_archive) if z_archive else {}

            wb = openpyxl.load_workbook(fp, data_only=True, read_only=True)
            for sname in wb.sheetnames:
                sname_clean = sname.strip().lower()
                if sname_clean in DUMMY_SHEETS:
                    continue

                ws = wb[sname]
                matrix = list(ws.iter_rows(values_only=True, max_row=50, max_col=35))
                meta = parse_subcont_sheet_meta(matrix, fp, sname)
                part_no = meta["part_number"]
                cpn = clean_str(part_no)

                if not cpn or len(cpn) < 3 or cpn.lower() in DUMMY_SHEETS:
                    continue

                pts = parse_subcont_sheet_points(matrix)
                if not pts:
                    print(f"    [-] Sheet {sname:15} | PN {part_no:20} -> 0 points parsed")
                    continue

                # Extract images
                imgs = []
                try:
                    d_target = drawing_map.get(sname_clean)
                    imgs = extract_sheet_images(fp, sheet_name=sname, part_number=part_no, z=z_archive, drawing_target=d_target)
                except Exception as e:
                    print(f"    [!] Error extracting image for {sname}: {e}")

                # Locate checksheet in DB
                cs = db_checksheets.get(cpn)
                if not cs:
                    # Try matching by part_number substring or sheetname
                    for k, v in db_checksheets.items():
                        if cpn in k or k in cpn:
                            cs = v
                            break

                if not cs:
                    # Create new checksheet if missing
                    cs = Checksheet(
                        part_number=part_no,
                        clean_part_number=cpn,
                        part_name=meta["part_name"],
                        model=meta["model"],
                        customer=meta["customer"],
                        doc_number=meta["doc_number"],
                        template_type="IQCSubcontParser",
                        status="Belum di review",
                        assigned_to="Unassigned",
                        keterangan="Diimpor dari CS subcont SIM",
                        raw_file_path=fp
                    )
                    session.add(cs)
                    await session.flush()
                    db_checksheets[cpn] = cs
                    print(f"    [+] Created NEW Checksheet: #{cs.id} ({part_no})")

                # Check existing points count
                pt_cnt_res = await session.execute(
                    select(func.count(InspectionPoint.id)).where(InspectionPoint.checksheet_id == cs.id)
                )
                curr_pt_count = pt_cnt_res.scalar() or 0

                # If current points is 0, or user wants updated points
                if curr_pt_count == 0 or len(pts) > curr_pt_count:
                    # Clear old points
                    await session.execute(delete(InspectionPoint).where(InspectionPoint.checksheet_id == cs.id))
                    for idx, pt in enumerate(pts):
                        ip = InspectionPoint(
                            checksheet_id=cs.id,
                            item_no=pt.get("item_no") or str(idx + 1),
                            inspection_item=pt.get("inspection_item") or f"Point {idx + 1}",
                            standard=pt.get("standard") or "-",
                            method=pt.get("method") or "Visual",
                            master_data="",
                            order_index=idx
                        )
                        session.add(ip)
                    total_pts_added += len(pts)

                # Add images if not already present
                if imgs:
                    img_cnt_res = await session.execute(
                        select(func.count(PartImage.id)).where(PartImage.checksheet_id == cs.id)
                    )
                    curr_img_count = img_cnt_res.scalar() or 0
                    if curr_img_count == 0:
                        for img_path in imgs:
                            pimg = PartImage(
                                checksheet_id=cs.id,
                                image_path=img_path,
                                image_url=img_path
                            )
                            session.add(pimg)
                        total_imgs_added += len(imgs)

                updated_parts.append((cs.id, cs.part_number, len(pts), len(imgs)))
                print(f"    [OK] #{cs.id:4} | {cs.part_number:22} | +{len(pts)} pts | +{len(imgs)} imgs")

            wb.close()
            if z_archive:
                z_archive.close()

            await session.commit()

        # Audit activity
        await log_activity(
            session=session,
            action="UPDATE SIM POINTS",
            part_number=f"{len(updated_parts)} Part SIM",
            operator="Admin",
            status="SUCCESS",
            details=f"Berhasil memperbarui titik ukur untuk {len(updated_parts)} part CS subcont SIM ({total_pts_added} titik ukur, {total_imgs_added} gambar)"
        )
        await session.commit()

    print("\n" + "=" * 60)
    print("=== SUMMARY OF SIM UPDATE ===")
    print(f"Total parts updated/verified: {len(updated_parts)}")
    print(f"Total inspection points populated: {total_pts_added}")
    print(f"Total images populated: {total_imgs_added}")
    print("=" * 60)

    print("\n[*] Synchronizing master data to Google Sheets...")
    try:
        await sync_all_checksheets_to_sheet()
        print("[✓] Google Sheets synchronization finished successfully!")
    except Exception as e:
        print(f"[!] Warning: Google Sheets sync error: {e}")


if __name__ == "__main__":
    asyncio.run(update_sim_checksheets())
