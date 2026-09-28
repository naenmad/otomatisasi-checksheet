#!/usr/bin/env python3
"""
Migration: Split combined LH/RH part numbers into separate checksheet records.

Handles patterns like:
  - 5253AN87/5253AN88       -> 5253AN87 (LH) + 5253AN88 (RH)
  - 5253AN87/ 5253AN88      -> same (with spaces)
  - 5220K988/989             -> 5220K988 (LH) + 5220K989 (RH)  [abbreviated]
  - 61771-BZ150 / 61771-BZ160 -> each gets its own record

Lower number = LH (first), Higher number = RH (second).
Both get identical inspection points and images.

Usage:
    python scripts/split_combined_parts.py          # Dry-run
    python scripts/split_combined_parts.py --apply  # Apply to DB
"""
import asyncio
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from database.connection import AsyncSessionLocal
from sqlalchemy import text


def parse_combined_part_number(combined_pn: str):
    """
    Parse a combined part number string into two individual part numbers.
    Returns (pn_left, pn_right) or None if not a combined format.
    """
    combined_pn = combined_pn.strip()
    if "/" not in combined_pn:
        return None

    parts = [p.strip() for p in combined_pn.split("/", 1)]
    if len(parts) != 2 or not parts[0] or not parts[1]:
        return None

    pn_left = parts[0]
    pn_right = parts[1]

    # Handle abbreviated right side: "5220K988/989" -> "5220K988" + "5220K989"
    if len(pn_right) < len(pn_left) and pn_right.isdigit():
        prefix = pn_left[:-len(pn_right)]
        pn_right = prefix + pn_right

    # Handle abbreviated with suffix: "75572/73B010P-BL" -> reconstruct
    # For these complex cases, we need to figure out the common prefix
    if len(pn_right) < len(pn_left) and not pn_right.isdigit():
        # Try to find common prefix by checking digit boundaries
        # e.g. "85312/812-74P00-000" -> prefix "85" + "312-74P00-000" vs "812-74P00-000"
        # This is ambiguous, keep as-is
        pass

    return (pn_left, pn_right)


def parse_combined_name(name: str, pn_left: str, pn_right: str):
    """
    Parse combined part name into (name_for_left_pn, name_for_right_pn).
    """
    if not name:
        return (f"Part {pn_left}", f"Part {pn_right}")

    name = name.strip()

    # Pattern 1: "NAME_LH/RH" or "NAME_LH/ RH" or "NAME LH/RH"
    match = re.match(r"^(.+?)[_\s]+LH\s*/\s*RH\s*$", name, re.IGNORECASE)
    if match:
        base = match.group(1).strip().rstrip(",_")
        return (f"{base} LH", f"{base} RH")

    # Pattern 2: "NAME RH/LH" (reversed)
    match = re.match(r"^(.+?)[_\s]+RH\s*/\s*LH\s*$", name, re.IGNORECASE)
    if match:
        base = match.group(1).strip().rstrip(",_")
        return (f"{base} RH", f"{base} LH")

    # Pattern 3: Two full names separated by " / " (with spaces around slash)
    if " / " in name:
        name_parts = [p.strip() for p in name.split(" / ", 1)]
        if len(name_parts) == 2 and len(name_parts[0]) > 3 and len(name_parts[1]) > 3:
            return (name_parts[0], name_parts[1])

    # Pattern 4: Name ends with "LH" or "RH" -> create the other variant
    match = re.match(r"^(.+?)\s+(LH|RH)\s*$", name, re.IGNORECASE)
    if match:
        base = match.group(1).strip().rstrip(",")
        side = match.group(2).upper()
        return (f"{base} LH", f"{base} RH")

    # Pattern 5: Name ends with ", R" or ", L" 
    match = re.match(r"^(.+?),\s*(R|L)\s*$", name, re.IGNORECASE)
    if match:
        base = match.group(1).strip()
        return (f"{base}, L", f"{base}, R")

    # Pattern 6: Name contains "R," or "L," at a word boundary
    # e.g. "BRKT R, FR SEAT OUT" -> base is "BRKT, FR SEAT OUT"
    match = re.match(r"^(.+?)\s+(R|L),\s*(.+)$", name, re.IGNORECASE)
    if match:
        prefix = match.group(1).strip()
        rest = match.group(3).strip()
        return (f"{prefix} L, {rest}", f"{prefix} R, {rest}")

    # Fallback: use base name + LH/RH
    # Strip any existing LH/RH/L/R from name to get clean base
    base = name
    return (f"{base} LH", f"{base} RH")




def determine_lr_order(pn_left: str, pn_right: str, name_left: str, name_right: str):
    """
    Determine which part number is LH and which is RH.
    Rule: lower number = LH (first), higher = RH (second).
    
    Returns: (pn_lh, name_lh, pn_rh, name_rh)
    """
    # Extract trailing numbers for comparison
    num_left = re.search(r"(\d+)\s*$", re.sub(r"[-_]", "", pn_left))
    num_right = re.search(r"(\d+)\s*$", re.sub(r"[-_]", "", pn_right))

    if num_left and num_right:
        n_left = int(num_left.group(1))
        n_right = int(num_right.group(1))

        if n_left <= n_right:
            # Left is lower number = LH
            return (pn_left, name_left, pn_right, name_right)
        else:
            # Right is lower = LH, swap
            return (pn_right, name_right, pn_left, name_left)

    # Can't determine numerically, keep original order
    return (pn_left, name_left, pn_right, name_right)


async def main():
    apply_mode = "--apply" in sys.argv

    async with AsyncSessionLocal() as session:
        # Find all combined part numbers
        result = await session.execute(text("""
            SELECT id, part_number, clean_part_number, part_name, model, customer, 
                   doc_number, template_type, status, keterangan, assigned_to, raw_file_path,
                   factoryhub_id, factoryhub_url
            FROM checksheets 
            WHERE part_number LIKE '%/%'
            ORDER BY id
        """))
        combined = result.fetchall()

        print(f"Combined part numbers found: {len(combined)}")
        print(f"Mode: {'APPLY' if apply_mode else 'DRY-RUN'}")
        print("=" * 100)

        split_count = 0
        skip_count = 0

        for row in combined:
            cs_id = row[0]
            orig_pn = row[1]
            orig_name = row[3]
            model = row[4]
            customer = row[5]
            doc_number = row[6]
            template_type = row[7]
            status = row[8]
            keterangan = row[9]
            assigned_to = row[10]
            raw_file = row[11]
            fh_id = row[12]
            fh_url = row[13]

            parsed = parse_combined_part_number(orig_pn)
            if not parsed:
                print(f"\n[SKIP] CS#{cs_id} - Cannot parse: {orig_pn}")
                skip_count += 1
                continue

            pn_left, pn_right = parsed

            # Same part number on both sides (e.g. "58313-BZ060 / 58313-BZ060")
            if pn_left == pn_right:
                print(f"\n[SKIP] CS#{cs_id} - Same PN on both sides: {pn_left}")
                skip_count += 1
                continue

            # Parse name
            name_left, name_right = parse_combined_name(orig_name, pn_left, pn_right)

            # Determine LH/RH order
            pn_lh, name_lh, pn_rh, name_rh = determine_lr_order(
                pn_left, pn_right, name_left, name_right
            )

            # Ensure LH/RH is in the name
            if "LH" not in name_lh.upper() and "L " not in name_lh.upper() and ", L" not in name_lh.upper():
                name_lh = name_lh + " LH" if not name_lh.upper().endswith(" LH") else name_lh
            if "RH" not in name_rh.upper() and "R " not in name_rh.upper() and ", R" not in name_rh.upper():
                name_rh = name_rh + " RH" if not name_rh.upper().endswith(" RH") else name_rh

            print(f"\n[SPLIT] CS#{cs_id}: {orig_pn} -> {orig_name}")
            print(f"  LH: {pn_lh:30s} -> {name_lh}")
            print(f"  RH: {pn_rh:30s} -> {name_rh}")

            # Get inspection points
            ip_result = await session.execute(text(
                "SELECT item_no, inspection_item, standard, method, master_data, order_index "
                "FROM inspection_points WHERE checksheet_id = :cs_id ORDER BY order_index"
            ), {"cs_id": cs_id})
            points = ip_result.fetchall()
            print(f"  Inspection points: {len(points)}")

            # Get images
            img_result = await session.execute(text(
                "SELECT image_path, image_url, image_base64 FROM part_images WHERE checksheet_id = :cs_id"
            ), {"cs_id": cs_id})
            images = img_result.fetchall()

            if apply_mode:
                clean_lh = re.sub(r"[^a-zA-Z0-9]", "", pn_lh).upper()
                clean_rh = re.sub(r"[^a-zA-Z0-9]", "", pn_rh).upper()

                # Check if either already exists as separate
                existing_lh = await session.execute(text(
                    "SELECT id FROM checksheets WHERE clean_part_number = :cpn"
                ), {"cpn": clean_lh})
                existing_rh = await session.execute(text(
                    "SELECT id FROM checksheets WHERE clean_part_number = :cpn"
                ), {"cpn": clean_rh})

                has_lh = existing_lh.scalar_one_or_none()
                has_rh = existing_rh.scalar_one_or_none()

                # Update original record to be the LH part
                await session.execute(text("""
                    UPDATE checksheets SET 
                        part_number = :pn, clean_part_number = :cpn, part_name = :name
                    WHERE id = :id
                """), {"pn": pn_lh, "cpn": clean_lh, "name": name_lh, "id": cs_id})

                # Create new record for RH part (if not already exists)
                if not has_rh:
                    await session.execute(text("""
                        INSERT INTO checksheets (part_number, clean_part_number, part_name, model, customer,
                            doc_number, template_type, status, keterangan, assigned_to, raw_file_path)
                        VALUES (:pn, :cpn, :name, :model, :customer, :doc, :tmpl, :status, :ket, :assigned, :raw)
                    """), {
                        "pn": pn_rh, "cpn": clean_rh, "name": name_rh,
                        "model": model, "customer": customer, "doc": doc_number,
                        "tmpl": template_type, "status": status, "ket": keterangan,
                        "assigned": assigned_to, "raw": raw_file or "",
                    })

                    # Get the new ID
                    new_id_result = await session.execute(text(
                        "SELECT id FROM checksheets WHERE clean_part_number = :cpn"
                    ), {"cpn": clean_rh})
                    new_cs_id = new_id_result.scalar_one_or_none()

                    if new_cs_id:
                        # Copy inspection points
                        for pt in points:
                            await session.execute(text("""
                                INSERT INTO inspection_points 
                                    (checksheet_id, item_no, inspection_item, standard, method, master_data, order_index)
                                VALUES (:cs_id, :item_no, :item, :std, :method, :master, :idx)
                            """), {
                                "cs_id": new_cs_id,
                                "item_no": pt[0], "item": pt[1], "std": pt[2],
                                "method": pt[3], "master": pt[4] or "", "idx": pt[5],
                            })

                        # Copy images
                        for img in images:
                            await session.execute(text("""
                                INSERT INTO part_images (checksheet_id, image_path, image_url, image_base64)
                                VALUES (:cs_id, :path, :url, :b64)
                            """), {
                                "cs_id": new_cs_id,
                                "path": img[0], "url": img[1], "b64": img[2],
                            })

                        print(f"  -> Created RH as CS#{new_cs_id}")

            split_count += 1

        if apply_mode:
            await session.commit()
            print("\n" + "=" * 100)
            print("CHANGES COMMITTED")
        else:
            print("\n" + "=" * 100)
            print("DRY-RUN COMPLETE")
            print("Run with --apply to write changes.")

        print(f"\nSummary:")
        print(f"  Split: {split_count}")
        print(f"  Skipped: {skip_count}")


if __name__ == "__main__":
    asyncio.run(main())
