"""
Batch Importer for CS INCOMING checksheets into Supabase Database.
"""
import os
import sys
import glob
import asyncio
from typing import List

# Ensure project root is in sys.path
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

from database.connection import AsyncSessionLocal
from services.parser_service import parse_and_save_checksheet


async def import_all_cs_incoming():
    search_pattern = "documents/CS INCOMING/**/*.xlsx"
    files = glob.glob(search_pattern, recursive=True)
    files.extend(glob.glob("documents/CS INCOMING/**/*.xls", recursive=True))

    # Exclude temp files if any remain
    files = [f for f in sorted(files) if not os.path.basename(f).startswith("~$")]

    print(f"[*] Found {len(files)} CS INCOMING files to process.")

    success_count = 0
    duplicate_or_updated = 0
    error_count = 0
    errors: List[dict] = []

    async with AsyncSessionLocal() as session:
        for idx, file_path in enumerate(files, 1):
            fname = os.path.basename(file_path)
            try:
                result = await parse_and_save_checksheet(
                    session=session,
                    file_path=file_path,
                    assigned_to="Unassigned"
                )
                success_count += 1
                if idx % 10 == 0 or idx == len(files):
                    print(f"[{idx}/{len(files)}] Parsed & saved: {result.get('part_number')} ({result.get('points_count')} pts)")
            except Exception as e:
                error_count += 1
                errors.append({"file": fname, "path": file_path, "error": str(e)})
                print(f"[!] Error on {fname}: {e}")

    print("\n" + "=" * 50)
    print(f"[+] Import Complete!")
    print(f"    Total Processed : {len(files)}")
    print(f"    Successfully Saved: {success_count}")
    print(f"    Errors          : {error_count}")
    print("=" * 50)

    if errors:
        print("\nErrors detail:")
        for err in errors[:10]:
            print(f"  - {err['file']}: {err['error']}")

    return {
        "total": len(files),
        "success": success_count,
        "errors": error_count,
        "error_details": errors
    }


if __name__ == "__main__":
    asyncio.run(import_all_cs_incoming())
