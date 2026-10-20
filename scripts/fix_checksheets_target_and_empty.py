"""
Fix empty checksheets and target checksheets requested by user:
- 5253AH80 (ID 793): Deduplicate and standardize 10 points
- 5305A772 (ID 741): Standardize 11 points (Burry <= 0.3 mm)
- 68721-73R00 (ID 671): Standardize 8 points (One Numbering Rule 1..8)
- 5220L701 (ID 580): Standardize 10 points (Reorder & Burry <= 0.3 mm)
- ID 1108 (61771-BZ150): Populate 8 points from IQC COIL sheet 61771-BZ150-60
- ID 1154 (65153): Populate 8 points from BLANK HPM sheet 65153
- ID 1155 (68126): Populate 8 points from BLANK HPM sheet 68126
- ID 963 (65743): Populate 8 points from BLANK HPM sheet 65743
- ID 973 (4-T86-K000): Populate 8 points from BLANK HPM sheet 4-T86-K000
- ID 1146 (MT143218): Populate 10 points from SIDE GATE TOP sheet 14321718
- ID 1153 (65793-TG1-T000-H1-R): Populate 8 points from 65793-TG1-T000-H1
- ID 458 (17522-TG4-T000): Deduplicate & fix coating thickness
- ID 910 (5256C055): Deduplicate & fix threading
"""
import asyncio
import json
import os
import sys

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

from sqlalchemy import select, delete
from database.connection import AsyncSessionLocal
from database.models import Checksheet, InspectionPoint, ActivityLog
from database.crud import get_checksheets_summary_list
from parsers.smart_parser import TextNormalizer, FuzzyToolNormalizer

# Points definitions for targeted updates
DEFINITIONS = {
    # 1. 5253AH80 (ID: 793)
    793: [
        {"item_no": "1", "inspection_item": "Thickness", "standard": "1.6 ± 0.1", "method": "Micrometer"},
        {"item_no": "2", "inspection_item": "Qty Hole", "standard": "4", "method": "Visual"},
        {"item_no": "3", "inspection_item": "Dimension", "standard": "Ø 12 + 0.2/-0.0", "method": "Caliper"},
        {"item_no": "4", "inspection_item": "Dimension", "standard": "12X18 + 0.2/-0.0", "method": "Caliper"},
        {"item_no": "5", "inspection_item": "Burry", "standard": "≤ 0.3 mm", "method": "Caliper"},
        {"item_no": "6", "inspection_item": "No Crack", "standard": "OK / NG", "method": "Visual"},
        {"item_no": "7", "inspection_item": "No Dent", "standard": "OK / NG", "method": "Visual"},
        {"item_no": "8", "inspection_item": "No Scratch", "standard": "OK / NG", "method": "Visual"},
        {"item_no": "9", "inspection_item": "No Over Cutting", "standard": "OK / NG", "method": "Visual"},
        {"item_no": "10", "inspection_item": "No Rust", "standard": "OK / NG", "method": "Visual"},
    ],
    # 2. 5305A772 (ID: 741)
    741: [
        {"item_no": "1", "inspection_item": "Thickness", "standard": "1.4 ± 0.1", "method": "Micrometer"},
        {"item_no": "2", "inspection_item": "Qty Hole", "standard": "3", "method": "Visual"},
        {"item_no": "3", "inspection_item": "Dimension", "standard": "Ø 25 +0.2/-0", "method": "Caliper"},
        {"item_no": "4", "inspection_item": "Dimension", "standard": "Ø 8 +0.2/-0", "method": "Caliper"},
        {"item_no": "5", "inspection_item": "Dimension", "standard": "Ø 8 +0.2/-0", "method": "Caliper"},
        {"item_no": "6", "inspection_item": "Burry", "standard": "≤ 0.3 mm", "method": "Caliper"},
        {"item_no": "7", "inspection_item": "No Crack", "standard": "OK / NG", "method": "Visual"},
        {"item_no": "8", "inspection_item": "No Dent", "standard": "OK / NG", "method": "Visual"},
        {"item_no": "9", "inspection_item": "No Scratch", "standard": "OK / NG", "method": "Visual"},
        {"item_no": "10", "inspection_item": "No Over Cutting", "standard": "OK / NG", "method": "Visual"},
        {"item_no": "11", "inspection_item": "No Rust", "standard": "OK / NG", "method": "Visual"},
    ],
    # 3. 68721-73R00 (ID: 671)
    671: [
        {"item_no": "1", "inspection_item": "Thickness", "standard": "0.7 ± 0.08", "method": "Caliper"},
        {"item_no": "2", "inspection_item": "Qty Hole", "standard": "12", "method": "Visual"},
        {"item_no": "3", "inspection_item": "Burry", "standard": "≤ 0.3 mm", "method": "Caliper"},
        {"item_no": "4", "inspection_item": "No Crack", "standard": "OK / NG", "method": "Visual"},
        {"item_no": "5", "inspection_item": "No Dent", "standard": "OK / NG", "method": "Visual"},
        {"item_no": "6", "inspection_item": "No Scratch", "standard": "OK / NG", "method": "Visual"},
        {"item_no": "7", "inspection_item": "No Over Cutting", "standard": "OK / NG", "method": "Visual"},
        {"item_no": "8", "inspection_item": "Profile OK", "standard": "Sesuai Sample", "method": "Visual"},
    ],
    # 4. 5220L701 (ID: 580)
    580: [
        {"item_no": "1", "inspection_item": "Thickness", "standard": "3.2 ± 0.1", "method": "Micrometer"},
        {"item_no": "2", "inspection_item": "Qty Hole", "standard": "3", "method": "Visual"},
        {"item_no": "3", "inspection_item": "Dimension", "standard": "Ø 10.5 +0.2/-0", "method": "Caliper"},
        {"item_no": "4", "inspection_item": "Dimension", "standard": "10.5X11 +0.2/-0", "method": "Caliper"},
        {"item_no": "5", "inspection_item": "Burry", "standard": "≤ 0.3 mm", "method": "Caliper"},
        {"item_no": "6", "inspection_item": "No Crack", "standard": "OK / NG", "method": "Visual"},
        {"item_no": "7", "inspection_item": "No Dent", "standard": "OK / NG", "method": "Visual"},
        {"item_no": "8", "inspection_item": "No Scratch", "standard": "OK / NG", "method": "Visual"},
        {"item_no": "9", "inspection_item": "No Over Cutting", "standard": "OK / NG", "method": "Visual"},
        {"item_no": "10", "inspection_item": "No Rust", "standard": "OK / NG", "method": "Visual"},
    ],
    # 5. ID 1108 (61771-BZ150)
    1108: [
        {"item_no": "1", "inspection_item": "Spec. Material", "standard": "SPC270-DX", "method": "Tag Label"},
        {"item_no": "2", "inspection_item": "Thickness", "standard": "1.2 ± 0.08", "method": "Caliper"},
        {"item_no": "3", "inspection_item": "Length", "standard": "Coil", "method": "Visual"},
        {"item_no": "4", "inspection_item": "Width", "standard": "860 ± 0.5", "method": "Roll Meter"},
        {"item_no": "5", "inspection_item": "No Rust", "standard": "OK / NG", "method": "Visual"},
        {"item_no": "6", "inspection_item": "No Scratch", "standard": "OK / NG", "method": "Visual"},
        {"item_no": "7", "inspection_item": "No Wave", "standard": "OK / NG", "method": "Visual"},
        {"item_no": "8", "inspection_item": "Packing", "standard": "OK / NG", "method": "Visual"},
    ],
    # 6. ID 1154 (65153)
    1154: [
        {"item_no": "1", "inspection_item": "Thickness", "standard": "2.3 ± 0.1", "method": "Caliper"},
        {"item_no": "2", "inspection_item": "Qty Hole", "standard": "2", "method": "Visual"},
        {"item_no": "3", "inspection_item": "Burry", "standard": "≤ 0.3 mm", "method": "Caliper"},
        {"item_no": "4", "inspection_item": "No Crack", "standard": "OK / NG", "method": "Visual"},
        {"item_no": "5", "inspection_item": "No Dent", "standard": "OK / NG", "method": "Visual"},
        {"item_no": "6", "inspection_item": "No Scratch", "standard": "OK / NG", "method": "Visual"},
        {"item_no": "7", "inspection_item": "No Over Cutting", "standard": "OK / NG", "method": "Visual"},
        {"item_no": "8", "inspection_item": "No Rust", "standard": "OK / NG", "method": "Visual"},
    ],
    # 7. ID 1155 (68126)
    1155: [
        {"item_no": "1", "inspection_item": "Thickness", "standard": "0.65 ± 0.08", "method": "Caliper"},
        {"item_no": "2", "inspection_item": "Qty Hole", "standard": "2", "method": "Visual"},
        {"item_no": "3", "inspection_item": "Burry", "standard": "≤ 0.3 mm", "method": "Caliper"},
        {"item_no": "4", "inspection_item": "No Crack", "standard": "OK / NG", "method": "Visual"},
        {"item_no": "5", "inspection_item": "No Dent", "standard": "OK / NG", "method": "Visual"},
        {"item_no": "6", "inspection_item": "No Scratch", "standard": "OK / NG", "method": "Visual"},
        {"item_no": "7", "inspection_item": "No Over Cutting", "standard": "OK / NG", "method": "Visual"},
        {"item_no": "8", "inspection_item": "No Rust", "standard": "OK / NG", "method": "Visual"},
    ],
    # 8. ID 963 (65743)
    963: [
        {"item_no": "1", "inspection_item": "Thickness", "standard": "1.6 ± 0.1", "method": "Caliper"},
        {"item_no": "2", "inspection_item": "Qty Hole", "standard": "3", "method": "Visual"},
        {"item_no": "3", "inspection_item": "Burry", "standard": "≤ 0.3 mm", "method": "Caliper"},
        {"item_no": "4", "inspection_item": "No Crack", "standard": "OK / NG", "method": "Visual"},
        {"item_no": "5", "inspection_item": "No Dent", "standard": "OK / NG", "method": "Visual"},
        {"item_no": "6", "inspection_item": "No Scratch", "standard": "OK / NG", "method": "Visual"},
        {"item_no": "7", "inspection_item": "No Over Cutting", "standard": "OK / NG", "method": "Visual"},
        {"item_no": "8", "inspection_item": "No Rust", "standard": "OK / NG", "method": "Visual"},
    ],
    # 9. ID 973 (4-T86-K000)
    973: [
        {"item_no": "1", "inspection_item": "Thickness", "standard": "1.6 ± 0.1", "method": "Caliper"},
        {"item_no": "2", "inspection_item": "Qty Hole", "standard": "2", "method": "Visual"},
        {"item_no": "3", "inspection_item": "Burry", "standard": "≤ 0.3 mm", "method": "Caliper"},
        {"item_no": "4", "inspection_item": "No Crack", "standard": "OK / NG", "method": "Visual"},
        {"item_no": "5", "inspection_item": "No Dent", "standard": "OK / NG", "method": "Visual"},
        {"item_no": "6", "inspection_item": "No Scratch", "standard": "OK / NG", "method": "Visual"},
        {"item_no": "7", "inspection_item": "No Over Cutting", "standard": "OK / NG", "method": "Visual"},
        {"item_no": "8", "inspection_item": "No Rust", "standard": "OK / NG", "method": "Visual"},
    ],
    # 10. ID 1146 (MT143218)
    1146: [
        {"item_no": "1", "inspection_item": "Thickness", "standard": "2.0 ± 0.1", "method": "Micrometer"},
        {"item_no": "2", "inspection_item": "Dimension", "standard": "19.4 ± 1.0", "method": "Caliper"},
        {"item_no": "3", "inspection_item": "Dimension", "standard": "22 ± 1.0", "method": "Caliper"},
        {"item_no": "4", "inspection_item": "Burry", "standard": "≤ 0.3 mm", "method": "Caliper"},
        {"item_no": "5", "inspection_item": "No Crack", "standard": "OK / NG", "method": "Visual"},
        {"item_no": "6", "inspection_item": "No Dent", "standard": "OK / NG", "method": "Visual"},
        {"item_no": "7", "inspection_item": "No Scratch", "standard": "OK / NG", "method": "Visual"},
        {"item_no": "8", "inspection_item": "No Rust", "standard": "OK / NG", "method": "Visual"},
        {"item_no": "9", "inspection_item": "No Over Cutting", "standard": "OK / NG", "method": "Visual"},
        {"item_no": "10", "inspection_item": "Profile OK", "standard": "Sesuai Sample", "method": "Visual"},
    ],
    # 11. ID 1153 (65793-TG1-T000-H1-R)
    1153: [
        {"item_no": "1", "inspection_item": "Thickness", "standard": "1.4 ± 0.1", "method": "Caliper"},
        {"item_no": "2", "inspection_item": "Qty Hole", "standard": "1", "method": "Visual"},
        {"item_no": "3", "inspection_item": "Burry", "standard": "≤ 0.3 mm", "method": "Caliper"},
        {"item_no": "4", "inspection_item": "No Crack", "standard": "OK / NG", "method": "Visual"},
        {"item_no": "5", "inspection_item": "No Dent", "standard": "OK / NG", "method": "Visual"},
        {"item_no": "6", "inspection_item": "No Scratch", "standard": "OK / NG", "method": "Visual"},
        {"item_no": "7", "inspection_item": "No Over Cutting", "standard": "OK / NG", "method": "Visual"},
        {"item_no": "8", "inspection_item": "No Rust", "standard": "OK / NG", "method": "Visual"},
    ],
    # 12. ID 458 (17522-TG4-T000)
    458: [
        {"item_no": "1", "inspection_item": "Color", "standard": "Hitam", "method": "Visual"},
        {"item_no": "2", "inspection_item": "Coating Thickness [A, B, C]", "standard": "Min 20µ", "method": "Thickness Meter"},
        {"item_no": "3", "inspection_item": "No Bubble", "standard": "OK / NG", "method": "Visual"},
        {"item_no": "4", "inspection_item": "No Scratch", "standard": "OK / NG", "method": "Visual"},
        {"item_no": "5", "inspection_item": "No Dent", "standard": "OK / NG", "method": "Visual"},
    ],
    # 13. ID 910 (5256C055)
    910: [
        {"item_no": "1", "inspection_item": "Length", "standard": "55 ± 0.5", "method": "Caliper"},
        {"item_no": "2", "inspection_item": "Diameter X", "standard": "Ø 34 ± 0.3", "method": "Caliper"},
        {"item_no": "3", "inspection_item": "Diameter Y", "standard": "Ø 34 ± 0.3", "method": "Caliper"},
        {"item_no": "4", "inspection_item": "Concentricity", "standard": "Ø 12 ± 0.5", "method": "Caliper"},
        {"item_no": "5", "inspection_item": "Chamfer", "standard": "0.5 - 1", "method": "CMM"},
        {"item_no": "6", "inspection_item": "Threading", "standard": "M24X3", "method": "Thread Gauge"},
        {"item_no": "7", "inspection_item": "Burry", "standard": "≤ 0.3 mm", "method": "Caliper"},
        {"item_no": "8", "inspection_item": "No Dent", "standard": "OK / NG", "method": "Visual"},
        {"item_no": "9", "inspection_item": "No Rust", "standard": "OK / NG", "method": "Visual"},
    ],
}


async def apply_fixes():
    async with AsyncSessionLocal() as session:
        print("=== APPLYING CHECKSHEET POINT FIXES ===")
        for cs_id, points_data in DEFINITIONS.items():
            # 1. Fetch checksheet
            stmt = select(Checksheet).where(Checksheet.id == cs_id)
            cs = (await session.execute(stmt)).scalar_one_or_none()
            if not cs:
                print(f"[SKIP] Checksheet #{cs_id} not found in DB")
                continue

            print(f"Updating Checksheet #{cs_id} ({cs.part_number} - {cs.part_name})...")

            # 2. Delete existing inspection points
            await session.execute(delete(InspectionPoint).where(InspectionPoint.checksheet_id == cs_id))

            # 3. Insert standardized points
            for idx, pt in enumerate(points_data):
                norm_pt = TextNormalizer.normalize_point(pt)
                new_pt = InspectionPoint(
                    checksheet_id=cs_id,
                    item_no=str(norm_pt.get("item_no", idx + 1)),
                    inspection_item=norm_pt.get("inspection_item", ""),
                    standard=norm_pt.get("standard", ""),
                    method=norm_pt.get("method", "Visual"),
                    master_data="",
                    order_index=idx
                )
                session.add(new_pt)

            print(f"  -> Added {len(points_data)} inspection points")

        await session.commit()
        print("\nAll target checksheets successfully committed to PostgreSQL!")

        # 4. Refresh cache
        print("\nRefreshing cache snapshot...")
        raw_list = await get_checksheets_summary_list(
            session=session,
            assigned_to=None,
            status=None,
            search=None,
            limit=5000,
            offset=0
        )
        if raw_list:
            cache_file = os.path.join(BASE_DIR, "data", "checksheets_summary_cache.json")
            with open(cache_file, "w", encoding="utf-8") as f:
                json.dump(raw_list, f, ensure_ascii=False)
            print(f"Cache successfully refreshed: {len(raw_list)} items written to {cache_file}")

if __name__ == "__main__":
    asyncio.run(apply_fixes())
