#!/usr/bin/env python3
"""
Comprehensive Standardization Script for Summit Checksheets Database
======================================================================
1. Standardizes all Burry variants to:
   - inspection_item: "Burry"
   - standard: "≤ 0.3 mm"
   - method: "Caliper"
2. Standardizes all Appearance / Defect checks:
   - No Rust, No Scratch, No Dent, No Crack, No Wave, No Wrinkle, No Neck,
     No Over Cutting, No Spatter, No Bubble, No Meler, No Kotor, No Bintik Putih,
     No Menggumpal, No Orange Peel, No Cacat, Profile OK, Packing
   - standard: "OK / NG" (except Profile OK: "Sesuai Sample")
   - method: "Visual"
   - Group Numbering: Consecutive defect rows share the exact same item_no
3. Standardizes general measurement names & tools (Thickness, Length, Width, Diameter Hole, etc.)
4. Optional image purge (--delete-images) to wipe incorrect sketches

Usage:
    python scripts/standardize_all_checksheets.py                # Dry-run preview
    python scripts/standardize_all_checksheets.py --apply        # Overwrite & standardize tables in DB
    python scripts/standardize_all_checksheets.py --apply --delete-images  # Also delete incorrect images
"""
import asyncio
import os
import sys
from datetime import datetime

# Add project root to sys.path
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

from sqlalchemy import select, delete, func, text
from database.connection import AsyncSessionLocal
from database.models import Checksheet, InspectionPoint, PartImage, ActivityLog
from parsers.smart_parser import TextNormalizer, FuzzyToolNormalizer


async def standardize_checksheets(apply_mode: bool = False, delete_images: bool = False):
    print("=" * 75)
    print(f"[*] SUMMIT CHECKSHEET STANDARDIZATION ENGINE")
    print(f"[*] Mode: {'>>> APPLY (OVERWRITE DATABASE) <<<' if apply_mode else 'DRY-RUN (PREVIEW ONLY)'}")
    print(f"[*] Delete Images: {'YES (Purge all part images)' if delete_images else 'NO (Keep images untouched)'}")
    print("=" * 75)

    async with AsyncSessionLocal() as session:
        # Optional image deletion
        if delete_images:
            img_count = (await session.execute(select(func.count(PartImage.id)))).scalar() or 0
            if apply_mode:
                await session.execute(delete(PartImage))
                print(f"[✓] Berhasil menghapus {img_count} gambar dari tabel part_images.")
            else:
                print(f"[PREVIEW] Akan menghapus {img_count} gambar dari tabel part_images.")

        # Fetch all checksheets with their points
        res_cs = await session.execute(select(Checksheet).order_by(Checksheet.id.asc()))
        checksheets = res_cs.scalars().all()
        total_cs = len(checksheets)
        print(f"[*] Memeriksa {total_cs} checksheet di database...")

        cs_updated_count = 0
        points_updated_count = 0
        burry_updated_count = 0
        appearance_grouped_count = 0

        for cs_idx, cs in enumerate(checksheets):
            res_pts = await session.execute(
                select(InspectionPoint)
                .filter(InspectionPoint.checksheet_id == cs.id)
                .order_by(InspectionPoint.order_index.asc())
            )
            old_pts = res_pts.scalars().all()
            if not old_pts:
                continue

            old_pts_dicts = [
                {
                    "item_no": p.item_no or "",
                    "inspection_item": p.inspection_item or "",
                    "standard": p.standard or "-",
                    "method": p.method or "Visual",
                    "master_data": p.master_data or "",
                }
                for p in old_pts
            ]

            # Run normalization and expansion with group numbering
            new_pts = TextNormalizer.expand_points(old_pts_dicts)

            # Check if there are changes
            is_changed = False
            if len(new_pts) != len(old_pts_dicts):
                is_changed = True
            else:
                for o, n in zip(old_pts_dicts, new_pts):
                    if (
                        o["item_no"] != n["item_no"]
                        or o["inspection_item"] != n["inspection_item"]
                        or o["standard"] != n["standard"]
                        or o["method"] != n["method"]
                    ):
                        is_changed = True
                        break

            if is_changed:
                cs_updated_count += 1
                points_updated_count += len(new_pts)

                for p in new_pts:
                    if p["inspection_item"] == "Burry":
                        burry_updated_count += 1
                    elif p["inspection_item"] in TextNormalizer.DEFECT_ITEMS:
                        appearance_grouped_count += 1

                # Show sample previews for the first 5 checksheets changed
                if cs_updated_count <= 5 or cs_updated_count % 100 == 0:
                    print(f"\n[CS #{cs.id}] {cs.part_number} ({cs.part_name}): {len(old_pts)} rows -> {len(new_pts)} rows")
                    for p in new_pts[:6]:
                        print(f"    #{p['item_no']:2s} | {p['inspection_item']:20s} | {p['standard']:18s} | {p['method']}")
                    if len(new_pts) > 6:
                        print(f"    ... (+{len(new_pts) - 6} baris lainnya)")

                if apply_mode:
                    # Delete old points
                    await session.execute(
                        delete(InspectionPoint).where(InspectionPoint.checksheet_id == cs.id)
                    )
                    # Insert standardized points
                    for idx, pt in enumerate(new_pts):
                        ip = InspectionPoint(
                            checksheet_id=cs.id,
                            item_no=pt.get("item_no") or str(idx + 1),
                            inspection_item=pt.get("inspection_item") or f"Point {idx + 1}",
                            standard=pt.get("standard") or "-",
                            method=pt.get("method") or "Visual",
                            master_data=pt.get("master_data") or "",
                            order_index=idx
                        )
                        session.add(ip)

        if apply_mode:
            # Add activity log entry
            log = ActivityLog(
                action="STANDARDIZATION",
                operator="System Standardization",
                status="SUCCESS",
                details=f"Standardized {cs_updated_count} checksheets ({points_updated_count} points, {burry_updated_count} burry, {appearance_grouped_count} defect rows grouped)",
                created_at=datetime.utcnow()
            )
            session.add(log)
            await session.commit()
            print("\n" + "=" * 75)
            print("[✓] DATABASE UPDATE SELESAI!")
        else:
            print("\n" + "=" * 75)
            print("[*] DRY-RUN SELESAI (Database belum diubah).")

        print(f"    - Total Checksheet di Database : {total_cs}")
        print(f"    - Checksheet yang Distandarkan : {cs_updated_count}")
        print(f"    - Total Poin Inspeksi Akhir    : {points_updated_count}")
        print(f"    - Poin Burry ≤ 0.3 mm          : {burry_updated_count}")
        print(f"    - Poin Defect Visual Bernomor Sama : {appearance_grouped_count}")
        if not apply_mode:
            print("\n[TIPS] Jalankan dengan flag '--apply' untuk menerapkan perubahan ke database:")
            print("       python scripts/standardize_all_checksheets.py --apply")
            print("       (Tambahkan '--delete-images' jika ingin menghapus semua gambar lama)")
        print("=" * 75)


if __name__ == "__main__":
    apply_flag = "--apply" in sys.argv
    delete_images_flag = "--delete-images" in sys.argv
    asyncio.run(standardize_checksheets(apply_mode=apply_flag, delete_images=delete_images_flag))
