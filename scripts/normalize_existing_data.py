#!/usr/bin/env python3
"""
Migration script: Split combined appearance rows into individual defect check rows.
Also re-applies TextNormalizer to all inspection points.

Usage:
    python scripts/normalize_existing_data.py          # Dry-run (preview only)
    python scripts/normalize_existing_data.py --apply  # Apply changes to DB
"""
import asyncio
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from database.connection import AsyncSessionLocal
from parsers.smart_parser import TextNormalizer, FuzzyToolNormalizer
from sqlalchemy import text


async def main():
    apply_mode = "--apply" in sys.argv

    async with AsyncSessionLocal() as session:
        # 1. Get all checksheet IDs that need row expansion:
        # - Has 'appearance', 'app', 'function', 'fungsi' in inspection_item
        # - Has combined standard in appearance
        result = await session.execute(text("""
            SELECT DISTINCT checksheet_id FROM inspection_points 
            WHERE LOWER(inspection_item) IN ('appearance', 'app', 'surface', 'function', 'fungsi')
               OR (standard LIKE '%,%' AND standard LIKE '%No %')
            ORDER BY checksheet_id
        """))
        affected_cs_ids = [r[0] for r in result.fetchall()]

        print(f"Checksheets to check for expansion/category swap: {len(affected_cs_ids)}")
        print(f"Mode: {'APPLY' if apply_mode else 'DRY-RUN'}")
        print("=" * 80)

        total_split = 0
        total_new_rows = 0

        for cs_id in affected_cs_ids:
            # Get all points for this checksheet
            result = await session.execute(text(
                "SELECT id, item_no, inspection_item, standard, method, master_data, order_index "
                "FROM inspection_points WHERE checksheet_id = :cs_id ORDER BY order_index"
            ), {"cs_id": cs_id})
            rows = result.fetchall()

            # Build points list
            old_points = []
            for row in rows:
                old_points.append({
                    "id": row[0],
                    "item_no": row[1],
                    "inspection_item": row[2],
                    "standard": row[3],
                    "method": row[4],
                    "master_data": row[5] or "",
                })

            # Run expand_points
            new_points = TextNormalizer.expand_points(old_points)

            # Check if points changed (either row count changed OR items/standards changed)
            changed = False
            if len(new_points) != len(old_points):
                changed = True
            else:
                for old_p, new_p in zip(old_points, new_points):
                    if (old_p["inspection_item"] != new_p["inspection_item"] or 
                        old_p["standard"] != new_p["standard"] or 
                        old_p["method"] != new_p["method"]):
                        changed = True
                        break

            if changed:
                print(f"\n[CS #{cs_id}] {len(old_points)} rows -> {len(new_points)} rows")
                for i, pt in enumerate(new_points):
                    old_desc = f"{old_points[i]['inspection_item']} | {old_points[i]['standard']}" if i < len(old_points) else "(new)"
                    new_desc = f"{pt['inspection_item']} | {pt['standard']} | {pt['method']}"
                    marker = "  " if i < len(old_points) and old_desc == f"{pt['inspection_item']} | {pt['standard']}" else "~"
                    print(f"  {marker} #{pt['item_no']:>2s} {new_desc}")

                total_split += 1
                total_new_rows += len(new_points) - len(old_points)

                if apply_mode:
                    # Delete old points
                    await session.execute(text(
                        "DELETE FROM inspection_points WHERE checksheet_id = :cs_id"
                    ), {"cs_id": cs_id})

                    # Insert new expanded points
                    for idx, pt in enumerate(new_points):
                        await session.execute(text(
                            "INSERT INTO inspection_points (checksheet_id, item_no, inspection_item, standard, method, master_data, order_index) "
                            "VALUES (:cs_id, :item_no, :item, :std, :method, :master, :idx)"
                        ), {
                            "cs_id": cs_id,
                            "item_no": pt.get("item_no", str(idx + 1)),
                            "item": pt.get("inspection_item", ""),
                            "std": pt.get("standard", "-"),
                            "method": pt.get("method", "Visual"),
                            "master": pt.get("master_data", ""),
                            "idx": idx,
                        })

        # Also normalize all remaining inspection points (labels, standards, methods)
        print("\n" + "=" * 80)
        print("Normalizing all inspection points (labels + standards + methods)...")

        result = await session.execute(text(
            "SELECT id, inspection_item, standard, method FROM inspection_points ORDER BY id"
        ))
        all_rows = result.fetchall()
        label_fixes = 0
        std_fixes = 0
        method_fixes = 0

        for row_id, old_item, old_std, old_method in all_rows:
            new_item = TextNormalizer.normalize_item(old_item)
            new_method = FuzzyToolNormalizer.normalize(old_method)
            new_std = TextNormalizer.normalize_standard(old_std, new_item)

            if new_item != old_item or new_method != old_method or new_std != old_std:
                if new_item != old_item:
                    label_fixes += 1
                if new_std != old_std:
                    std_fixes += 1
                if new_method != old_method:
                    method_fixes += 1

                if apply_mode:
                    await session.execute(text(
                        "UPDATE inspection_points SET inspection_item = :item, standard = :std, method = :method WHERE id = :id"
                    ), {"item": new_item, "std": new_std, "method": new_method, "id": row_id})

        if apply_mode:
            await session.commit()
            print("\nCHANGES COMMITTED TO DATABASE")
        else:
            print("\nDRY-RUN COMPLETE (no changes written)")
            print("Run with --apply to write changes.")

        print(f"\nSummary:")
        print(f"  Checksheets expanded/swapped: {total_split}")
        print(f"  New rows added:               {total_new_rows}")
        print(f"  Label fixes:                  {label_fixes}")
        print(f"  Standard fixes:               {std_fixes}")
        print(f"  Method fixes:                 {method_fixes}")


if __name__ == "__main__":
    asyncio.run(main())
