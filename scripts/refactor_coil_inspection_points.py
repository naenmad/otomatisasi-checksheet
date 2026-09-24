"""
Database Migration Script: Refactor Coil & Material Inspection Points across Supabase.

1. Identifies checksheets with Appearance & Conformity/Non-Conformity points.
2. Removes footer disposition rows:
   - Conformity (Good for use)
   - Conformity (Good for use with condition)
   - Non Conformity (Reject to vendor)
3. Splits multi-criteria Appearance row:
   - "No Rust, No Scratch, No Wave, Packing 'OK'" ->
     1) Item: "No Rust", Standard: "OK / NG", Method: "Visual"
     2) Item: "No Scratch", Standard: "OK / NG", Method: "Visual"
     3) Item: "No Wave", Standard: "OK / NG", Method: "Visual"
     4) Item: "Packing", Standard: "OK / NG", Method: "Visual"
4. Re-sequences item_no (1, 2, 3, ...) and order_index.
5. Logs activity to ActivityLog and triggers Google Sheets background sync.
"""
import asyncio
import re
from typing import List, Dict, Any
from sqlalchemy import select, delete

from database.connection import AsyncSessionLocal
from database.models import Checksheet, InspectionPoint
from database.crud import log_activity
from services.google_sheets_service import trigger_background_sheet_sync


async def refactor_all_coil_points():
    async with AsyncSessionLocal() as session:
        all_cs = (await session.scalars(select(Checksheet))).all()
        cs_map = {cs.id: cs for cs in all_cs}

        all_points = (await session.scalars(
            select(InspectionPoint).order_by(InspectionPoint.checksheet_id, InspectionPoint.order_index)
        )).all()

        points_by_cs: Dict[int, List[InspectionPoint]] = {}
        for pt in all_points:
            points_by_cs.setdefault(pt.checksheet_id, []).append(pt)

        modified_cs_count = 0
        total_split_points_added = 0
        total_deleted_rows = 0

        for cs_id, pts in points_by_cs.items():
            cs = cs_map.get(cs_id)
            if not cs:
                continue

            has_appearance = False
            has_conformity = False

            for p in pts:
                item_lower = (p.inspection_item or "").lower()
                std_lower = (p.standard or "").lower()
                if "appearance" in item_lower or "rust" in std_lower:
                    has_appearance = True
                if "conformity" in item_lower or "good for use" in std_lower or "reject to vendor" in std_lower:
                    has_conformity = True

            if not (has_appearance or has_conformity):
                continue

            new_point_defs: List[Dict[str, Any]] = []

            for p in pts:
                item_lower = (p.inspection_item or "").lower()
                std_lower = (p.standard or "").lower()

                # 1. Skip footer disposition items (Conformity / Non Conformity)
                if "conformity" in item_lower or "good for use" in std_lower or "reject to vendor" in std_lower:
                    total_deleted_rows += 1
                    continue

                # 2. Split Appearance row if contains composite visual criteria
                if ("appearance" in item_lower or "rust" in std_lower) and ("rust" in std_lower or "scratch" in std_lower or "wave" in std_lower or "packing" in std_lower):
                    split_items = [
                        {"inspection_item": "No Rust", "standard": "OK / NG", "method": "Visual"},
                        {"inspection_item": "No Scratch", "standard": "OK / NG", "method": "Visual"},
                        {"inspection_item": "No Wave", "standard": "OK / NG", "method": "Visual"},
                        {"inspection_item": "Packing", "standard": "OK / NG", "method": "Visual"}
                    ]
                    new_point_defs.extend(split_items)
                    total_split_points_added += 4
                else:
                    # Keep regular dimension point (Material, Thickness, Length, Width, etc.)
                    new_point_defs.append({
                        "inspection_item": p.inspection_item,
                        "standard": p.standard,
                        "method": p.method or "Visual",
                        "master_data": p.master_data or ""
                    })

            # Delete existing points for this checksheet
            await session.execute(
                delete(InspectionPoint).where(InspectionPoint.checksheet_id == cs_id)
            )

            # Insert points
            for idx, p_def in enumerate(new_point_defs, 1):
                item_name = p_def["inspection_item"]
                # Visual appearance split items retain number 5
                if item_name in ["No Rust", "No Scratch", "No Wave", "Packing"]:
                    current_no = "5"
                else:
                    current_no = str(idx)

                new_ip = InspectionPoint(
                    checksheet_id=cs_id,
                    item_no=current_no,
                    inspection_item=p_def["inspection_item"],
                    standard=p_def["standard"],
                    method=p_def["method"],
                    master_data=p_def.get("master_data", ""),
                    order_index=idx - 1
                )
                session.add(new_ip)

            modified_cs_count += 1

        await session.commit()

        # Record activity log
        summary_log = (
            f"Refactoring titik inspeksi selesai pada {modified_cs_count} checksheet material/coil. "
            f"Baris Conformity/Non-Conformity dibersihkan, Appearance dipecah menjadi 4 item (No Rust, No Scratch, No Wave, Packing) dengan standar OK/NG."
        )
        await log_activity(
            session=session,
            action="UPDATE DATABASE POINTS",
            part_number="SYSTEM",
            operator="Admin",
            status="SUCCESS",
            details=summary_log
        )

        # Trigger automatic Google Sheets sync in background
        trigger_background_sheet_sync()

        print("=" * 60)
        print(f"[✓] Refactoring Database Berhasil:")
        print(f"    - Total Checksheet Diperbarui : {modified_cs_count}")
        print(f"    - Baris Footer Dihapus       : {total_deleted_rows}")
        print(f"    - Poin Inspeksi Baru Dibuat  : {total_split_points_added}")
        print(f"    - Google Sheet Sync Dipicu   : Ya (Background)")
        print("=" * 60)


if __name__ == "__main__":
    asyncio.run(refactor_all_coil_points())
