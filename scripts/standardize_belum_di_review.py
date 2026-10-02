#!/usr/bin/env python3
"""
Targeted Standardization Script for 'Belum di review' and 'Butuh Revisi' Checksheets
=====================================================================================
Fixes:
1. Strips prepended balloon numbers (e.g. '16 Trim Line' -> 'TRIM LINE', '13 GAP' -> 'GAP', '1 Datum Hole' -> 'Datum Hole')
2. Standardizes all Trim Line variants to uppercase 'TRIM LINE'
3. Replaces pure numbers in item names with 'Position' or 'Hole Position' when checking position
4. Standardizes GAP and SHIM to uppercase 'GAP' and 'SHIM'
5. Cleans OCR artifacts (e.g. 'Appearance Ꚛꚛs' -> 'Appearance')
6. Expands appearance defect rows and groups them under the same item_no
"""
import asyncio
import os
import sys
import re
from datetime import datetime

# Add project root to sys.path
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

from sqlalchemy import select, delete, text
from database.connection import AsyncSessionLocal, engine
from database.models import Checksheet, InspectionPoint, ActivityLog
from parsers.smart_parser import TextNormalizer, FuzzyToolNormalizer


def clean_raw_point(pt: dict) -> dict:
    it = (pt.get("inspection_item") or "").strip()
    std = (pt.get("standard") or "-").strip()
    mth = (pt.get("method") or "Visual").strip()
    item_no = (pt.get("item_no") or "").strip()
    master = (pt.get("master_data") or "").strip()

    # Rule 1: Handle pure numeric items (e.g. "2", "3", "5")
    if re.match(r"^\d+$", it):
        if any(k in std.upper() for k in ["PIN GO", "MARK CTR", "NO GO", "GO/NO GO", "GO / NO GO"]):
            it = "Position"
            if not std.upper().startswith("OK / NG") and not std.upper().startswith("OK/NG"):
                std = f"OK / NG {std}"
        elif mth.upper() in ["VISUAL", "CALIPER", "INSERT PIN DATUM"]:
            it = "Position"

    # Rule 2: Strip prepended balloon numbers (e.g. "16 Trim Line", "14a Distance", "1 Datum Hole")
    lead_m = re.match(r"^\d+[a-zA-Z]?[\.\-\)]?\s+(.+)$", it)
    if lead_m:
        it = lead_m.group(1).strip()

    # Rule 3: TRIM LINE uppercase standardization
    if re.match(r"^(trim\s*[\-\s]*line|trimline)(\s*\[.+\])?$", it, re.I):
        br = re.search(r"\[.+\]", it)
        it = f"TRIM LINE {br.group(0).upper()}" if br else "TRIM LINE"
    elif it.lower() == "stopper trimline":
        it = "STOPPER TRIMLINE"
    elif it.lower() == "gap":
        it = "GAP"
    elif it.lower() == "shim":
        it = "SHIM"

    # Rule 4: Clean OCR artifacts in Appearance
    if "appearance" in it.lower():
        it = "Appearance"

    # Rule 5: Standard engineering terms
    if it.lower() in ["datum hole", "hole datum"]:
        it = "Datum Hole"
    elif it.lower() in ["hole position", "position"]:
        it = "Hole Position" if "hole" in it.lower() else "Position"
    elif it.lower() in ["pitch hole"]:
        it = "Pitch Hole"
    elif it.lower() in ["quantity spot", "qty spot"]:
        it = "Qty Spot Weld"
    elif it.lower() in ["identification marking"]:
        it = "Identification Marking"

    return {
        "item_no": item_no,
        "inspection_item": it,
        "standard": std,
        "method": mth,
        "master_data": master,
    }


async def run_standardization(apply_mode: bool = False):
    print("=" * 75)
    print(f"[*] SUMMIT TARGETED STANDARDIZATION ENGINE ('Belum di review')")
    print(f"[*] Mode: {'>>> APPLY (OVERWRITE DATABASE) <<<' if apply_mode else 'DRY-RUN (PREVIEW ONLY)'}")
    print("=" * 75)

    async with AsyncSessionLocal() as session:
        # Fetch checksheets with status 'Belum di review'
        res_cs = await session.execute(
            select(Checksheet)
            .filter(Checksheet.status.in_(["Belum di review"]))
            .order_by(Checksheet.id.asc())
        )
        checksheets = res_cs.scalars().all()
        total_cs = len(checksheets)
        print(f"[*] Ditemukan {total_cs} checksheet dengan status 'Belum di review'...")

        cs_changed = 0
        points_changed_total = 0

        for cs in checksheets:
            res_pts = await session.execute(
                select(InspectionPoint)
                .filter(InspectionPoint.checksheet_id == cs.id)
                .order_by(InspectionPoint.order_index.asc())
            )
            old_pts = res_pts.scalars().all()
            if not old_pts:
                continue

            old_dicts = [
                {
                    "item_no": p.item_no or "",
                    "inspection_item": p.inspection_item or "",
                    "standard": p.standard or "-",
                    "method": p.method or "Visual",
                    "master_data": p.master_data or "",
                }
                for p in old_pts
            ]

            # Step 1: Clean raw errors (leading numbers, pure numbers, TRIM LINE)
            cleaned_step1 = [clean_raw_point(p) for p in old_dicts]

            # Step 2: Expand appearance defect rows and group sequential defect numbers
            new_pts = TextNormalizer.expand_points(cleaned_step1)

            # Check if any change occurred
            has_changes = len(new_pts) != len(old_dicts)
            if not has_changes:
                for o, n in zip(old_dicts, new_pts):
                    if (
                        o["item_no"] != n["item_no"]
                        or o["inspection_item"] != n["inspection_item"]
                        or o["standard"] != n["standard"]
                        or o["method"] != n["method"]
                    ):
                        has_changes = True
                        break

            if has_changes:
                cs_changed += 1
                points_changed_total += len(new_pts)

                if cs_changed <= 6 or cs_changed % 10 == 0:
                    print(f"\n[CS #{cs.id}] {cs.part_number} ({cs.part_name}): {len(old_dicts)} -> {len(new_pts)} rows")
                    for p in new_pts[:8]:
                        print(f"    #{p['item_no']:2s} | {p['inspection_item']:22s} | {p['standard']:18s} | {p['method']}")
                    if len(new_pts) > 8:
                        print(f"    ... (+{len(new_pts) - 8} baris lainnya)")

                if apply_mode:
                    # Delete old points and insert new points
                    await session.execute(
                        delete(InspectionPoint).where(InspectionPoint.checksheet_id == cs.id)
                    )
                    for idx, pt in enumerate(new_pts):
                        ip = InspectionPoint(
                            checksheet_id=cs.id,
                            item_no=pt.get("item_no") or str(idx + 1),
                            inspection_item=pt.get("inspection_item") or f"Point {idx + 1}",
                            standard=pt.get("standard") or "-",
                            method=pt.get("method") or "Visual",
                            master_data=pt.get("master_data") or "",
                            order_index=idx,
                        )
                        session.add(ip)

        if apply_mode:
            log = ActivityLog(
                action="STANDARDIZATION_REVIEW",
                operator="System",
                status="SUCCESS",
                details=f"Standardized {cs_changed} checksheets in 'Belum di review' ({points_changed_total} points cleaned)",
                created_at=datetime.utcnow(),
            )
            session.add(log)
            await session.commit()
            print("\n" + "=" * 75)
            print(f"[✓] SUKSES! Database berhasil diperbarui untuk {cs_changed} checksheet.")
        else:
            print("\n" + "=" * 75)
            print(f"[*] DRY-RUN SELESAI: {cs_changed} dari {total_cs} checksheet akan diperbaiki.")
            print("[TIPS] Jalankan dengan '--apply' untuk menulis perubahan ke database:")
            print("       .venv/bin/python scripts/standardize_belum_di_review.py --apply")
        print("=" * 75)

    await engine.dispose()


if __name__ == "__main__":
    apply_flag = "--apply" in sys.argv
    asyncio.run(run_standardization(apply_mode=apply_flag))
