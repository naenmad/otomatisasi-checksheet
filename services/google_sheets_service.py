"""
Google Sheets Synchronization Service for Checksheet Automation.
Formats and synchronizes checksheet records directly to Google Spreadsheets.
"""
import os
import asyncio
from datetime import datetime
from typing import Dict, Any, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from database.models import Checksheet
from database.connection import AsyncSessionLocal

DEFAULT_SHEET_URL = "https://docs.google.com/spreadsheets/d/1iHoOMUJryHYAnjjC0-n6HN2zrcpU_y7u6TCoceLrTUY/edit?usp=sharing"
GOOGLE_SHEET_URL = os.getenv("GOOGLE_SHEET_URL", DEFAULT_SHEET_URL).strip()


def build_spreadsheet_tsv(checksheets: list) -> str:
    """Build cleanly formatted TSV table with headers and data."""
    headers = [
        "No",
        "Penanggung Jawab (PIC)",
        "Part Number",
        "Part Name",
        "Model",
        "Customer",
        "Doc Number",
        "Total Poin Inspeksi",
        "Status Checksheet",
        "Keterangan / Status FactoryHub",
        "Link FactoryHub",
        "Terakhir Diperbarui"
    ]

    lines = ["\t".join(headers)]

    for idx, cs in enumerate(checksheets, 1):
        updated = cs.updated_at.strftime("%d/%m/%Y %H:%M") if cs.updated_at else datetime.now().strftime("%d/%m/%Y %H:%M")
        row = [
            str(idx),
            (cs.assigned_to if (cs.assigned_to and cs.assigned_to not in ("Unassigned", "Belum Ditugaskan")) else "Belum Ditugaskan"),
            cs.part_number or "-",
            cs.part_name or "-",
            cs.model or "-",
            cs.customer or "-",
            cs.doc_number or "-",
            str(len(cs.inspection_points) if cs.inspection_points else 0),
            cs.status or "-",
            cs.keterangan or "-",
            cs.factoryhub_url or "-",
            updated
        ]
        # Clean any accidental newlines or tabs in cell content
        clean_row = [str(cell).replace("\t", " ").replace("\n", " ").replace("\r", " ") for cell in row]
        lines.append("\t".join(clean_row))

    return "\n".join(lines)


async def sync_all_checksheets_to_sheet(sheet_url: Optional[str] = None) -> Dict[str, Any]:
    """
    Fetch all checksheets from database, build formatted TSV table,
    and paste into Google Spreadsheet via Playwright.
    """
    from playwright.async_api import async_playwright

    target_url = sheet_url or GOOGLE_SHEET_URL
    print(f"[*] Menyiapkan sinkronisasi Google Sheet: {target_url}...")

    # Load all checksheets
    async with AsyncSessionLocal() as session:
        from database.crud import list_checksheets
        checksheets = await list_checksheets(session=session, limit=500)

    if not checksheets:
        return {"status": "empty", "message": "Tidak ada data checksheet di database."}

    tsv_data = build_spreadsheet_tsv(checksheets)

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True, channel="chrome")
        context = await browser.new_context(viewport={"width": 1400, "height": 900})
        await context.grant_permissions(["clipboard-read", "clipboard-write"])
        page = await context.new_page()

        try:
            await page.goto(target_url, wait_until="domcontentloaded")
            await page.wait_for_timeout(4000)
            await page.keyboard.press("Escape")

            # Select A1 in Name Box
            name_box = page.locator("#t-name-box")
            await name_box.click()
            await name_box.fill("A1")
            await page.keyboard.press("Enter")
            await page.wait_for_timeout(600)

            # Paste formatted TSV table
            await page.evaluate("(text) => navigator.clipboard.writeText(text)", tsv_data)
            await page.wait_for_timeout(300)
            await page.keyboard.press("Meta+v")
            await page.wait_for_timeout(3500)

            print(f"[✓] Berhasil sinkronisasi {len(checksheets)} baris ke Google Sheet!")
            return {
                "status": "success",
                "synced_count": len(checksheets),
                "sheet_url": target_url,
                "synced_at": datetime.now().isoformat()
            }
        finally:
            await browser.close()


def trigger_background_sheet_sync():
    """Trigger background sync task without blocking request flow."""
    try:
        loop = asyncio.get_event_loop()
        if loop.is_running():
            asyncio.create_task(sync_all_checksheets_to_sheet())
        else:
            asyncio.run(sync_all_checksheets_to_sheet())
    except Exception as e:
        print(f"[Warning] Gagal memicu background sheet sync: {e}")
