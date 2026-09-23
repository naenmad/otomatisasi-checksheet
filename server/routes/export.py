"""
Export & Google Sheets Sync API Router.
"""
import io
import os
import openpyxl
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
from fastapi import APIRouter, Depends, Query, HTTPException
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from database.connection import get_db
from database.crud import list_checksheets

router = APIRouter(prefix="/api/export", tags=["Export"])

SPREADSHEET_URL = "https://docs.google.com/spreadsheets/d/12ZFCuc_zS2sfSf36Vg6NibccOC6zIfGoLS-bvn3wQk0/edit?gid=249591028#gid=249591028"


@router.get("/excel")
async def export_excel(
    assigned_to: str = Query("ALL"),
    db: AsyncSession = Depends(get_db)
):
    """
    Generate and download styled Excel report of current checksheets.
    """
    checksheets = await list_checksheets(session=db, assigned_to=assigned_to, limit=500)

    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "REPORT CHECKSHEET"

    # Header styling
    header_fill = PatternFill(start_color="312E81", end_color="312E81", fill_type="solid")
    header_font = Font(name="Arial", size=10, bold=True, color="FFFFFF")
    data_font = Font(name="Arial", size=9)
    thin_border = Border(
        left=Side(style='thin', color='CBD5E1'),
        right=Side(style='thin', color='CBD5E1'),
        top=Side(style='thin', color='CBD5E1'),
        bottom=Side(style='thin', color='CBD5E1')
    )

    headers = ["No", "Pembagian", "Part No.", "Part Name", "Model", "Customer", "Status", "Keterangan"]
    ws.append(headers)

    for col_idx in range(1, len(headers) + 1):
        cell = ws.cell(1, col_idx)
        cell.fill = header_fill
        cell.font = header_font
        cell.alignment = Alignment(horizontal="center", vertical="center")

    for idx, cs in enumerate(checksheets, 1):
        row = [
            idx,
            cs.assigned_to,
            cs.part_number,
            cs.part_name,
            cs.model,
            cs.customer,
            cs.status,
            cs.keterangan
        ]
        ws.append(row)
        for col_idx in range(1, len(row) + 1):
            c = ws.cell(idx + 1, col_idx)
            c.font = data_font
            c.border = thin_border
            if col_idx in [1, 2, 5, 6, 7]:
                c.alignment = Alignment(horizontal="center", vertical="center")

    # Column widths
    widths = [6, 14, 25, 32, 12, 14, 18, 40]
    for i, w in enumerate(widths, 1):
        col_letter = openpyxl.utils.get_column_letter(i)
        ws.column_dimensions[col_letter].width = w

    output = io.BytesIO()
    wb.save(output)
    output.seek(0)

    filename = f"REKAP_CHECKSHEET_{assigned_to.upper()}.xlsx"
    return StreamingResponse(
        output,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f"attachment; filename={filename}"}
    )


@router.post("/sync-google-sheet")
async def sync_to_google_sheet(
    assigned_to: str = Query("Zul"),
    db: AsyncSession = Depends(get_db)
):
    """
    Sync current checksheets for a team member directly to the Google Spreadsheet.
    """
    from playwright.async_api import async_playwright

    checksheets = await list_checksheets(session=db, assigned_to=assigned_to, limit=200)
    if not checksheets:
        return {"status": "empty", "message": f"Tidak ada data untuk {assigned_to}"}

    tsv_data = "\n".join([
        f"{cs.part_number}\t{cs.part_name}\t{cs.model}\t{cs.customer}\t{cs.status}\t{cs.keterangan}"
        for cs in checksheets
    ])

    user_data_dir = os.path.expanduser("~/.factoryhub_chrome_profile")
    try:
        async with async_playwright() as p:
            browser = await p.chromium.launch_persistent_context(
                user_data_dir=user_data_dir,
                channel="chrome",
                headless=True,
                viewport={"width": 1400, "height": 900}
            )
            page = await browser.new_page()
            await page.goto(SPREADSHEET_URL)
            await page.wait_for_timeout(3500)
            await page.keyboard.press("Escape")

            # Paste into D5 for Zul (or appropriate start cell)
            start_cell = "D5"
            name_box = page.locator("#t-name-box")
            await name_box.click()
            await name_box.fill(start_cell)
            await page.keyboard.press("Enter")
            await page.wait_for_timeout(600)

            # Paste via clipboard
            await browser.pages[0].context.grant_permissions(["clipboard-read", "clipboard-write"])
            await page.evaluate("(text) => navigator.clipboard.writeText(text)", tsv_data)
            await page.wait_for_timeout(300)
            await page.keyboard.press("Meta+v")
            await page.wait_for_timeout(2500)

            await browser.close()
            return {
                "status": "success",
                "synced_count": len(checksheets),
                "assigned_to": assigned_to,
                "sheet_url": SPREADSHEET_URL
            }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Gagal sync ke Google Spreadsheet: {str(e)}")
