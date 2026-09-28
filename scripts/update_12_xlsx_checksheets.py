#!/usr/bin/env python3
"""
Import / Update all checksheets from '12.xlsx' (MMKI Subcont).
Includes:
- 5251D430 and all other 53 sheets in 12.xlsx
- Extracts inspection points + expands via TextNormalizer
- Extracts sketch drawings
- Inserts missing checksheets and updates existing checksheets with points & drawings
"""
import os
import sys
import zipfile
import asyncio
import openpyxl

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

from database.connection import AsyncSessionLocal
from database.crud import create_checksheet
from database.models import Checksheet, InspectionPoint, PartImage
from sqlalchemy import select, delete, text
from parsers.smart_parser import TextNormalizer, FuzzyToolNormalizer
from parsers.image_extractor import get_workbook_sheet_drawing_map, extract_sheet_images
from scripts.import_cs_subcont import (
    parse_subcont_sheet_meta,
    parse_subcont_sheet_points,
    clean_str,
    DUMMY_SHEETS
)
from services.parser_service import match_catalog_status


async def main():
    apply_mode = "--apply" in sys.argv
    fp = "documents/CS INCOMING/CS IQC SUBCONT/C.sheet MMKI/12.xlsx"
    fname = os.path.basename(fp)

    print(f"File: {fp}")
    print(f"Mode: {'APPLY' if apply_mode else 'DRY-RUN'}")
    print("=" * 80)

    # 1. Open zip archive for drawing map
    z_archive = zipfile.ZipFile(fp, "r") if zipfile.is_zipfile(fp) else None
    drawing_map = get_workbook_sheet_drawing_map(z_archive) if z_archive else {}

    # 2. Open workbook
    wb = openpyxl.load_workbook(fp, data_only=True)

    async with AsyncSessionLocal() as session:
        # Load existing checksheets map by clean part number
        existing_res = await session.execute(select(Checksheet))
        existing_checksheets = existing_res.scalars().all()
        cs_by_pn = {}
        for cs in existing_checksheets:
            cpn = clean_str(cs.part_number)
            if cpn:
                cs_by_pn[cpn] = cs

        total_sheets = 0
        total_created = 0
        total_updated = 0
        total_points = 0
        total_images = 0

        for sname in wb.sheetnames:
            sname_clean = sname.strip().lower()
            if sname_clean in DUMMY_SHEETS or not sname_clean:
                continue

            ws = wb[sname]
            matrix = list(ws.iter_rows(values_only=True, max_row=60, max_col=35))
            meta = parse_subcont_sheet_meta(matrix, fp, sname)
            part_no = meta["part_number"]
            cpn = clean_str(part_no)

            if not cpn or len(cpn) < 3 or cpn in DUMMY_SHEETS:
                continue

            total_sheets += 1

            # Extract raw points
            raw_pts = parse_subcont_sheet_points(matrix)
            # Expand points (splits categories, formats OK / NG)
            pts = TextNormalizer.expand_points(raw_pts)

            # Extract drawings
            imgs = []
            try:
                d_target = drawing_map.get(sname_clean)
                imgs = extract_sheet_images(fp, sheet_name=sname, part_number=part_no, z=z_archive, drawing_target=d_target)
            except Exception as e:
                print(f"  [!] Image extraction error on {sname}: {e}")

            cat_match = match_catalog_status(part_no)
            existing_cs = cs_by_pn.get(cpn)
            action = "UPDATE" if existing_cs else "CREATE"

            print(f"[{action}] Sheet: {sname:15s} | PN: {part_no:20s} | Name: {meta['part_name']:25s} | Pts: {len(pts):2d} | Imgs: {len(imgs)}")

            total_points += len(pts)
            total_images += len(imgs)
            if existing_cs:
                total_updated += 1
            else:
                total_created += 1

            if apply_mode:
                if existing_cs:
                    # Update metadata if needed
                    existing_cs.part_name = meta["part_name"] or existing_cs.part_name
                    existing_cs.raw_file_path = fp
                    if meta.get("customer") and meta["customer"] != "PT. SUMMIT":
                        existing_cs.customer = meta["customer"]

                    # Replace points
                    await session.execute(delete(InspectionPoint).where(InspectionPoint.checksheet_id == existing_cs.id))
                    for idx, pt in enumerate(pts):
                        ip = InspectionPoint(
                            checksheet_id=existing_cs.id,
                            item_no=pt.get("item_no") or str(idx + 1),
                            inspection_item=pt.get("inspection_item") or f"Point {idx + 1}",
                            standard=pt.get("standard") or "-",
                            method=pt.get("method") or "Visual",
                            master_data=pt.get("master_data") or "",
                            order_index=idx
                        )
                        session.add(ip)

                    # Update images if we found images and none existed
                    if imgs:
                        await session.execute(delete(PartImage).where(PartImage.checksheet_id == existing_cs.id))
                        for img_p in imgs:
                            pimg = PartImage(
                                checksheet_id=existing_cs.id,
                                image_path=img_p,
                                image_url=img_p
                            )
                            session.add(pimg)
                else:
                    # Create new checksheet
                    new_cs = await create_checksheet(
                        session=session,
                        part_number=part_no,
                        part_name=meta["part_name"],
                        model=meta["model"],
                        customer=meta["customer"],
                        doc_number=meta["doc_number"],
                        template_type="IQCSubcontParser",
                        status=cat_match["status"],
                        assigned_to="Unassigned",
                        keterangan=cat_match["keterangan"] or "Diimpor dari MMKI 12.xlsx",
                        raw_file_path=fp,
                        points=pts,
                        images=imgs
                    )
                    cs_by_pn[cpn] = new_cs

        if apply_mode:
            await session.commit()
            print("\nCHANGES COMMITTED TO DATABASE!")
        else:
            print("\nDRY-RUN COMPLETE (no changes written). Run with --apply to write changes.")

        print(f"\nSummary:")
        print(f"  Valid sheets processed: {total_sheets}")
        print(f"  Checksheets to create:  {total_created}")
        print(f"  Checksheets to update:  {total_updated}")
        print(f"  Total points extracted: {total_points}")
        print(f"  Total images extracted: {total_images}")

    wb.close()
    if z_archive:
        z_archive.close()


if __name__ == "__main__":
    asyncio.run(main())
