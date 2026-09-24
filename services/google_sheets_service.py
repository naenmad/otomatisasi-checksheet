"""
Google Sheets Synchronization Service for Checksheet Automation.
Formats and synchronizes checksheet records across 3 worksheets:
1. Overview (Ringkasan KPI, Statistik PIC, Model & Status)
2. Data Master (Database lengkap seluruh part checksheet)
3. Log (Histori proses, aktivitas input, pembaruan, dan otomasi)
"""
import os
import asyncio
from datetime import datetime
from collections import Counter
from typing import Dict, Any, Optional, List
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from database.models import Checksheet, SubmissionQueue
from database.connection import AsyncSessionLocal

DEFAULT_SHEET_URL = "https://docs.google.com/spreadsheets/d/1iHoOMUJryHYAnjjC0-n6HN2zrcpU_y7u6TCoceLrTUY/edit?usp=sharing"
GOOGLE_SHEET_URL = os.getenv("GOOGLE_SHEET_URL", DEFAULT_SHEET_URL).strip()


def clean_cell(val: Any) -> str:
    """Clean tab and newline characters from string values to preserve TSV layout."""
    if val is None:
        return "-"
    return str(val).replace("\t", " ").replace("\n", " ").replace("\r", " ").strip()


def build_overview_tsv(checksheets: list) -> str:
    """Build cleanly formatted executive summary TSV for the Overview tab."""
    total = len(checksheets)
    done_count = sum(1 for c in checksheets if c.status == "Checksheet Done")
    ready_count = sum(1 for c in checksheets if c.status == "Belum Di Input")
    rev_count = sum(1 for c in checksheets if c.status == "Butuh Revisi")
    no_part_count = sum(1 for c in checksheets if c.status == "Tidak Ada Part")
    total_points = sum(len(c.inspection_points) if c.inspection_points else 0 for c in checksheets)

    pct_done = f"{(done_count / total * 100):.1f}%" if total > 0 else "0.0%"
    pct_ready = f"{(ready_count / total * 100):.1f}%" if total > 0 else "0.0%"
    pct_rev = f"{(rev_count / total * 100):.1f}%" if total > 0 else "0.0%"
    pct_no_part = f"{(no_part_count / total * 100):.1f}%" if total > 0 else "0.0%"

    lines = []
    lines.append("RINGKASAN & STATISTIK MASTER CHECKSHEET - PT. SUMMIT ADYAWINSA INDONESIA")
    lines.append(f"Waktu Sinkronisasi Terakhir:\t{datetime.now().strftime('%d/%m/%Y %H:%M:%S')}")
    lines.append("")

    # Section 1: KPI Metrics
    lines.append("METRIK STATUS UTAMA\tJUMLAH PART\tPERSENTASE\tDESKRIPSI")
    lines.append(f"Total Part Terdaftar\t{total}\t100.0%\tSeluruh katalog checksheet aktif")
    lines.append(f"Checksheet Selesai (Done)\t{done_count}\t{pct_done}\tData terisi lengkap dan siap otomasi")
    lines.append(f"Belum Di Input (Ready)\t{ready_count}\t{pct_ready}\tMenunggu input balloon dan inspeksi")
    lines.append(f"Butuh Revisi\t{rev_count}\t{pct_rev}\tPerlu perbaikan sketsa atau data inspeksi")
    lines.append(f"Tidak Ada Part\t{no_part_count}\t{pct_no_part}\tPart tidak ditemukan pada master drawing")
    lines.append(f"Total Poin Inspeksi Terdaftar\t{total_points}\t-\tAkumulasi seluruh item pengukuran")
    lines.append("")

    # Section 2: PIC Breakdown
    lines.append("STATISTIK PENANGGUNG JAWAB (PIC)\tTOTAL TUGAS\tDONE\tBELUM INPUT\tREVISI\tPROGRESS (%)")
    pic_groups: Dict[str, List] = {}
    for cs in checksheets:
        pic = cs.assigned_to if (cs.assigned_to and cs.assigned_to not in ("Unassigned", "Belum Ditugaskan")) else "Belum Ditugaskan"
        pic_groups.setdefault(pic, []).append(cs)

    for pic, items in sorted(pic_groups.items(), key=lambda x: len(x[1]), reverse=True):
        p_total = len(items)
        p_done = sum(1 for c in items if c.status == "Checksheet Done")
        p_ready = sum(1 for c in items if c.status == "Belum Di Input")
        p_rev = sum(1 for c in items if c.status == "Butuh Revisi")
        p_pct = f"{(p_done / p_total * 100):.1f}%" if p_total > 0 else "0.0%"
        lines.append(f"{pic}\t{p_total}\t{p_done}\t{p_ready}\t{p_rev}\t{p_pct}")
    lines.append("")

    # Section 3: Model Breakdown
    lines.append("DISTRIBUSI MODEL PRODUK\tJUMLAH PART")
    models = Counter(cs.model or "-" for cs in checksheets)
    for model, count in models.most_common(15):
        lines.append(f"{model}\t{count}")

    return "\n".join(lines)


def build_master_tsv(checksheets: list) -> str:
    """Build cleanly formatted TSV table with headers and all part rows for Data Master."""
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
            clean_cell(cs.part_number),
            clean_cell(cs.part_name),
            clean_cell(cs.model),
            clean_cell(cs.customer),
            clean_cell(cs.doc_number),
            str(len(cs.inspection_points) if cs.inspection_points else 0),
            clean_cell(cs.status),
            clean_cell(cs.keterangan),
            clean_cell(cs.factoryhub_url),
            updated
        ]
        lines.append("\t".join(row))

    return "\n".join(lines)


def build_log_tsv(activity_logs: list) -> str:
    """Build cleanly formatted audit and activity history TSV for the Log tab."""
    headers = [
        "No",
        "Waktu (Timestamp)",
        "Part Number / Target",
        "Penanggung Jawab / Operator",
        "Tipe Proses / Aksi",
        "Status",
        "Keterangan / Catatan Detail"
    ]

    lines = ["\t".join(headers)]
    log_counter = 1

    for log in activity_logs:
        t_time = log.created_at.strftime("%d/%m/%Y %H:%M:%S") if log.created_at else datetime.now().strftime("%d/%m/%Y %H:%M:%S")
        lines.append("\t".join([
            str(log_counter),
            t_time,
            clean_cell(log.part_number or "-"),
            clean_cell(log.operator or "Operator"),
            clean_cell(log.action or "-"),
            clean_cell(log.status or "-"),
            clean_cell(log.details or "-")
        ]))
        log_counter += 1

    return "\n".join(lines)


async def sync_all_checksheets_to_sheet(sheet_url: Optional[str] = None) -> Dict[str, Any]:
    """
    Fetch all checksheets & activity logs, build TSVs for 3 worksheets:
    Overview, Data Master, and Log, and paste directly into Google Spreadsheet.
    """
    from playwright.async_api import async_playwright

    target_url = sheet_url or GOOGLE_SHEET_URL
    print(f"[*] Menyiapkan sinkronisasi 3 Sheet Google: {target_url}...")

    # Load data from database
    async with AsyncSessionLocal() as session:
        from database.crud import list_checksheets, list_activity_logs, log_activity
        checksheets = await list_checksheets(session=session, limit=1000)

        # Record this sync event in ActivityLog so it appears in the log
        await log_activity(
            session=session,
            action="SYNC GOOGLE SHEET",
            part_number="ALL PARTS",
            operator="SYSTEM",
            status="SUCCESS",
            details=f"Sinkronisasi 3 sheets berhasil untuk {len(checksheets)} part master data"
        )

        activity_logs = await list_activity_logs(session=session, limit=200)

    if not checksheets:
        return {"status": "empty", "message": "Tidak ada data checksheet di database."}

    # Generate TSV content for all 3 sheets
    overview_tsv = build_overview_tsv(checksheets)
    master_tsv = build_master_tsv(checksheets)
    log_tsv = build_log_tsv(activity_logs)

    tab_data_map = [
        ("Data Master", master_tsv),
        ("Overview", overview_tsv),
        ("Log", log_tsv),
    ]

    async with async_playwright() as p:
        # Launch browser with Chrome channel or default chromium
        try:
            browser = await p.chromium.launch(headless=True, channel="chrome")
        except Exception:
            browser = await p.chromium.launch(headless=True)

        context = await browser.new_context(viewport={"width": 1400, "height": 900})
        await context.grant_permissions(["clipboard-read", "clipboard-write"])
        page = await context.new_page()

        try:
            await page.goto(target_url, wait_until="domcontentloaded")
            await page.wait_for_timeout(4000)
            await page.keyboard.press("Escape")

            synced_tabs = []

            for tab_name, tsv_content in tab_data_map:
                tab_locator = page.locator(".docs-sheet-tab", has_text=tab_name).first
                if await tab_locator.count() > 0:
                    print(f"[*] Mengarahkan ke tab '{tab_name}'...")
                    await tab_locator.click()
                    await page.wait_for_timeout(1200)

                    # Clear formula or focus
                    await page.keyboard.press("Escape")
                    await page.wait_for_timeout(300)

                    # Jump to cell A1 via Name Box
                    name_box = page.locator("#t-name-box")
                    if await name_box.count() > 0:
                        await name_box.click()
                        await name_box.fill("A1")
                        await page.keyboard.press("Enter")
                        await page.wait_for_timeout(500)

                    # Copy TSV to clipboard and paste
                    await page.evaluate("(text) => navigator.clipboard.writeText(text)", tsv_content)
                    await page.wait_for_timeout(300)
                    await page.keyboard.press("ControlOrMeta+v")
                    await page.wait_for_timeout(3000)
                    synced_tabs.append(tab_name)
                    print(f"[✓] Berhasil sinkronisasi tab '{tab_name}'")
                else:
                    print(f"[!] Tab '{tab_name}' tidak ditemukan, melewati tab ini.")

            # Return focus to Overview tab so it is the default visible sheet
            overview_tab = page.locator(".docs-sheet-tab", has_text="Overview").first
            if await overview_tab.count() > 0:
                await overview_tab.click()
                await page.wait_for_timeout(1000)

            print(f"[✓] Selesai! Berhasil sinkronisasi 3 sheet: {synced_tabs}")
            return {
                "status": "success",
                "synced_count": len(checksheets),
                "synced_tabs": synced_tabs,
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
