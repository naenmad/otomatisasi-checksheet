#!/usr/bin/env python3
"""
Migration script: Apply TextNormalizer to all existing inspection points in the database.
Standardizes inspection_item labels, method names, and appearance standards.

Usage:
    python scripts/normalize_existing_data.py          # Dry-run (preview only)
    python scripts/normalize_existing_data.py --apply  # Apply changes to DB
"""
import asyncio
import os
import sys

# Ensure project root is in path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from database.connection import AsyncSessionLocal
from parsers.smart_parser import TextNormalizer, FuzzyToolNormalizer
from sqlalchemy import text


async def main():
    apply_mode = "--apply" in sys.argv

    async with AsyncSessionLocal() as session:
        # Fetch all inspection points
        result = await session.execute(text(
            "SELECT id, inspection_item, standard, method FROM inspection_points ORDER BY id"
        ))
        rows = result.fetchall()
        total = len(rows)
        print(f"Total inspection points: {total}")
        print(f"Mode: {'APPLY (writing to DB)' if apply_mode else 'DRY-RUN (preview only)'}")
        print("=" * 80)

        changes_item = 0
        changes_std = 0
        changes_method = 0
        skipped = 0

        for row_id, old_item, old_std, old_method in rows:
            new_item = TextNormalizer.normalize_item(old_item)
            new_method = FuzzyToolNormalizer.normalize(old_method)
            new_std = TextNormalizer.normalize_standard(old_std, new_item)

            item_changed = new_item != old_item
            std_changed = new_std != old_std
            method_changed = new_method != old_method

            if item_changed or std_changed or method_changed:
                if item_changed:
                    changes_item += 1
                if std_changed:
                    changes_std += 1
                if method_changed:
                    changes_method += 1

                print(f"\n[ID={row_id}]")
                if item_changed:
                    print(f"  ITEM:   {repr(old_item)}")
                    print(f"       -> {repr(new_item)}")
                if std_changed:
                    print(f"  STD:    {repr(old_std)[:80]}")
                    print(f"       -> {repr(new_std)[:80]}")
                if method_changed:
                    print(f"  METHOD: {repr(old_method)}")
                    print(f"       -> {repr(new_method)}")

                if apply_mode:
                    await session.execute(text(
                        "UPDATE inspection_points SET inspection_item = :item, standard = :std, method = :method WHERE id = :id"
                    ), {"item": new_item, "std": new_std, "method": new_method, "id": row_id})
            else:
                skipped += 1

        if apply_mode:
            await session.commit()
            print("\n" + "=" * 80)
            print("CHANGES COMMITTED TO DATABASE")
        else:
            print("\n" + "=" * 80)
            print("DRY-RUN COMPLETE (no changes written)")
            print("Run with --apply to write changes.")

        print(f"\nSummary:")
        print(f"  Total points:        {total}")
        print(f"  Item label changes:  {changes_item}")
        print(f"  Standard changes:    {changes_std}")
        print(f"  Method changes:      {changes_method}")
        print(f"  Already correct:     {skipped}")


if __name__ == "__main__":
    asyncio.run(main())
