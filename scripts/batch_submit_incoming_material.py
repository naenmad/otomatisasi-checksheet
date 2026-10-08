"""
Batch submit all 'Siap Kirim' Incomming Material checksheets to FactoryHub.
- Reuses single authenticated Playwright browser session (1x login).
- Automatically removes stale/legacy images on FactoryHub.
- Uploads both WebP reference drawings (Coil & Sheet).
- Updates checksheet status to 'Checksheet Done'.
- Records activity log with operator assigned to each part (Iqbal, Rama, Zul).
"""
import os
import sys
import re
import asyncio
from datetime import datetime
from typing import List, Dict, Any

# Ensure project root is in sys.path
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from playwright.async_api import async_playwright
from database.connection import AsyncSessionLocal
from database.models import Checksheet, ActivityLog
from database.crud import update_checksheet_status, log_activity, clean_str
from core.automator import launch_playwright_browser, login_factoryhub, fill_checksheet_form

async def batch_submit(limit: int = None):
    print("=" * 60)
    print("[*] BATCH SUBMIT INCOMING MATERIAL TO FACTORYHUB")
    print("=" * 60)

    # 1. Fetch parts to process
    async with AsyncSessionLocal() as db:
        from sqlalchemy import select
        from sqlalchemy.orm import selectinload
        query = (
            select(Checksheet)
            .options(selectinload(Checksheet.inspection_points))
            .where(Checksheet.category == "Incomming Material")
            .where(Checksheet.status == "Siap Kirim")
            .order_by(Checksheet.id)
        )
        if limit:
            query = query.limit(limit)
        res = await db.execute(query)
        checksheets = res.scalars().all()

    total = len(checksheets)
    print(f"[*] Ditemukan {total} checksheet Incomming Material berstatus 'Siap Kirim'.")
    if total == 0:
        print("[!] Tidak ada checksheet untuk diproses.")
        return

    # Operator distribution
    op_counts = {}
    for cs in checksheets:
        op = cs.assigned_to or "Unassigned"
        op_counts[op] = op_counts.get(op, 0) + 1
    print(f"[*] Rincian Operator: {op_counts}")

    # 2. Launch browser with single session login
    async with async_playwright() as p:
        print("[*] Menjalankan browser Google Chrome...")
        browser_obj, context, page = await launch_playwright_browser(
            p=p,
            headless=True,
            browser_channel="chrome"
        )

        try:
            print("[*] Login ke FactoryHub (1x sesi untuk seluruh batch)...")
            await login_factoryhub(page)
            print("[✓] Login berhasil!\n")

            success_count = 0
            fail_count = 0

            for idx, cs in enumerate(checksheets, 1):
                part_no = cs.part_number
                operator_name = cs.assigned_to or "Operator"
                print("-" * 50)
                print(f"[{idx}/{total}] Memproses: {part_no} | Operator: {operator_name}")

                # Prepare inspection points payload
                points_payload = [
                    {
                        "item_no": pt.item_no,
                        "inspection_item": pt.inspection_item,
                        "standard": pt.standard,
                        "method": pt.method,
                        "master_data": pt.master_data or ""
                    }
                    for pt in cs.inspection_points
                ]

                # Prepare image paths (local files)
                clean_p = cs.clean_part_number or clean_str(part_no)
                part_dir = os.path.join(PROJECT_ROOT, "storage", "images", clean_p)
                coil_img = os.path.join(part_dir, "material_coil.webp")
                sheet_img = os.path.join(part_dir, "material_sheet.webp")

                image_paths = []
                for img_candidate in [coil_img, sheet_img]:
                    if os.path.isfile(img_candidate):
                        image_paths.append(img_candidate)

                if not image_paths:
                    # Fallback to templates directory
                    tpl_coil = os.path.join(PROJECT_ROOT, "storage", "templates", "material_coil.webp")
                    tpl_sheet = os.path.join(PROJECT_ROOT, "storage", "templates", "material_sheet.webp")
                    for tpl_candidate in [tpl_coil, tpl_sheet]:
                        if os.path.isfile(tpl_candidate):
                            image_paths.append(tpl_candidate)

                meta_payload = {
                    "part_number": part_no,
                    "part_name": cs.part_name or "",
                    "model": cs.model or "-",
                    "customer": cs.customer or "PT. HPM",
                    "doc_number": cs.doc_number or "FO-45-01",
                    "category": "Incomming Material",
                    "checksheet_category": "Incomming Material"
                }

                try:
                    result = await fill_checksheet_form(
                        page=page,
                        part_or_excel=part_no,
                        submit=True,
                        custom_doc_no=cs.doc_number,
                        override_items=points_payload,
                        override_metadata=meta_payload,
                        override_images=image_paths
                    )

                    status = result.get("status", "unknown")
                    final_url = result.get("final_url", "")

                    if status == "submitted":
                        # Resolved edit URL
                        resolved_url = final_url
                        if not resolved_url or not re.search(r"/checksheet-master/\d+/edit", resolved_url):
                            if cs.factoryhub_url and re.search(r"/checksheet-master/\d+/edit", cs.factoryhub_url):
                                resolved_url = cs.factoryhub_url

                        # Update DB and Log Activity with cs.assigned_to
                        async with AsyncSessionLocal() as session:
                            await update_checksheet_status(
                                session=session,
                                checksheet_id=cs.id,
                                status="Checksheet Done",
                                factoryhub_url=resolved_url,
                                keterangan="Selesai diinput via Batch Otomasi (Auto-replace gambar)"
                            )
                            await log_activity(
                                session=session,
                                action="SUBMIT FACTORYHUB",
                                part_number=part_no,
                                operator=operator_name,
                                status="SUCCESS",
                                details=f"Batch submit berhasil ({len(points_payload)} poin, {len(image_paths)} gambar WebP)",
                                link=resolved_url
                            )

                        print(f"[✓] SUKSES: {part_no} -> Status: Checksheet Done (Operator: {operator_name})")
                        success_count += 1
                    elif status == "part_not_registered":
                        async with AsyncSessionLocal() as session:
                            await update_checksheet_status(
                                session=session,
                                checksheet_id=cs.id,
                                status="Tidak Ada Part",
                                keterangan="Part belum terdaftar di Master Part FactoryHub"
                            )
                            await log_activity(
                                session=session,
                                action="SUBMIT FACTORYHUB",
                                part_number=part_no,
                                operator=operator_name,
                                status="GAGAL",
                                details="Part number belum terdaftar di Master Part FactoryHub"
                            )
                        print(f"[!] TIDAK ADA PART: {part_no} (Operator: {operator_name})")
                        fail_count += 1
                    else:
                        print(f"[?] Status: {status} untuk {part_no}")
                        fail_count += 1

                except Exception as err:
                    print(f"[ERROR] Gagal memproses {part_no}: {err}")
                    async with AsyncSessionLocal() as session:
                        await log_activity(
                            session=session,
                            action="SUBMIT FACTORYHUB",
                            part_number=part_no,
                            operator=operator_name,
                            status="ERROR",
                            details=f"Error: {str(err)[:200]}"
                        )
                    fail_count += 1

            print("\n" + "=" * 60)
            print(f"[SELESAI] Batch submission selesai: {success_count} sukses, {fail_count} gagal dari total {total} part.")
            print("=" * 60)

        finally:
            try:
                if context:
                    await context.close()
                if browser_obj:
                    await browser_obj.close()
            except Exception:
                pass

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--limit", type=int, default=None, help="Batas jumlah part yang diproses")
    args = parser.parse_args()

    asyncio.run(batch_submit(limit=args.limit))
