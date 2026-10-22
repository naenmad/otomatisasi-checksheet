"""
Rollback Tool: Restore a Checksheet Template on FactoryHub and FaketoryHub local DB
from a previously saved rollback snapshot JSON file.

Usage:
    .venv/bin/python scripts/rollback_template.py <path_to_snapshot_json>
"""
import os
import sys
import json
import asyncio
from playwright.async_api import async_playwright
from sqlalchemy import select, delete

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from core.automator import login_factoryhub
from database.connection import AsyncSessionLocal
from database.models import Checksheet, InspectionPoint
from database.crud import get_checksheets_summary_list
from scripts.update_all_ir_templates import update_factoryhub_template

async def rollback_from_file(snapshot_path: str):
    if not os.path.exists(snapshot_path):
        print(f"Error: Snapshot file not found: {snapshot_path}")
        return False

    with open(snapshot_path, "r") as f:
        data = json.load(f)

    tid = data["tid"]
    pn = data["part_number"]
    points = data.get("factoryhub_live_rows") or data.get("local_db_points", [])

    print("=" * 60)
    print(f"  ROLLBACK TEMPLATE: TID {tid} ({pn})")
    print(f"  Source file: {snapshot_path}")
    print(f"  Total items to restore: {len(points)}")
    print("=" * 60)

    # 1. Restore local PostgreSQL DB
    print("[1/3] Restoring local PostgreSQL DB...")
    async with AsyncSessionLocal() as session:
        cs = (await session.execute(select(Checksheet).where(Checksheet.part_number == pn))).scalars().first()
        if cs:
            await session.execute(delete(InspectionPoint).where(InspectionPoint.checksheet_id == cs.id))
            for idx, pt in enumerate(points):
                ip = InspectionPoint(
                    checksheet_id=cs.id,
                    item_no=str(pt.get("item_no") or (idx + 1)),
                    inspection_item=pt.get("inspection_item") or "",
                    measuring_position=pt.get("measuring_position") or "",
                    standard=pt.get("standard") or "",
                    method=pt.get("method") or "Caliper",
                    master_data=pt.get("master_data") or "",
                    order_index=idx
                )
                session.add(ip)
            await session.commit()
            print(f"      Local DB checksheet {cs.id} restored with {len(points)} points!")
        else:
            print("      [!] Warning: Checksheet not found in local DB.")

    # 2. Restore Live FactoryHub Template
    print(f"[2/3] Restoring live FactoryHub template TID {tid}...")
    target = {
        "tid": tid,
        "part_number": pn
    }
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()
        page.set_default_timeout(60000)
        await login_factoryhub(page)
        res = await update_factoryhub_template(page, target, points)
        print("      FactoryHub update response:", res)
        await browser.close()

    # 3. Refresh Cache
    print("[3/3] Refreshing cache...")
    async with AsyncSessionLocal() as session:
        cache_data = await get_checksheets_summary_list(session)
        with open("data/checksheets_summary_cache.json", "w") as f:
            json.dump(cache_data, f)
    print("      Cache refreshed!")

    print("\n[+] ROLLBACK COMPLETED SUCCESSFULLY!")
    return True

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: .venv/bin/python scripts/rollback_template.py <path_to_snapshot_json>")
        sys.exit(1)
    asyncio.run(rollback_from_file(sys.argv[1]))
