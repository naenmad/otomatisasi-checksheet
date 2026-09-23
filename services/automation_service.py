"""
Automation service that triggers Playwright form filling using database inspection points
and streams log output in real-time via async generator (for SSE/WebSocket).
"""
import asyncio
from typing import AsyncGenerator, Dict, Any
from sqlalchemy.ext.asyncio import AsyncSession

from database.crud import get_checksheet_by_id, update_checksheet_status
from automator import run_automation


async def execute_checksheet_submission(
    checksheet_id: int,
    session: AsyncSession,
    submit: bool = True,
    headless: bool = False,
    browser_channel: str = "chrome"
) -> AsyncGenerator[str, None]:
    """
    Execute checksheet submission to FactoryHub and yield log lines in real-time.
    """
    cs = await get_checksheet_by_id(session, checksheet_id)
    if not cs:
        yield f"[ERROR] Checksheet ID {checksheet_id} tidak ditemukan di database.\n"
        return

    yield f"[*] Memulai otomatisasi untuk Part: {cs.part_number} ({cs.part_name})\n"
    yield f"[*] Model: {cs.model} | Customer: {cs.customer} | Doc No: {cs.doc_number}\n"
    yield f"[*] Total Inspection Points: {len(cs.inspection_points)}\n"

    # Prepare inspection points payload
    points_payload = [
        {
            "item_no": p.item_no,
            "inspection_item": p.inspection_item,
            "standard": p.standard,
            "method": p.method,
            "master_data": p.master_data or ""
        }
        for p in cs.inspection_points
    ]

    # Reference images
    image_paths = [img.image_path for img in cs.images if img.image_path]

    yield f"[*] Menyiapkan browser {browser_channel.upper()} (profil user)...\n"

    try:
        # Run automation
        result = await run_automation(
            part_or_excel=cs.raw_file_path or cs.part_number,
            headless=headless,
            submit=submit,
            doc_number=cs.doc_number,
            browser_channel=browser_channel,
            override_items=points_payload
        )

        final_url = result.get("final_url", "")
        status = result.get("status", "unknown")

        if status == "submitted":
            yield f"[✓] Sukses submit ke FactoryHub: {final_url}\n"
            await update_checksheet_status(
                session=session,
                checksheet_id=checksheet_id,
                status="Checksheet Done",
                factoryhub_url=final_url,
                keterangan="Selesai diinput via Web Otomasi"
            )
            # Auto-sync updated status directly to Google Sheet in background
            from services.google_sheets_service import trigger_background_sheet_sync
            trigger_background_sheet_sync()
            yield f"[i] Sinkronisasi baris ke Google Sheet dipicu secara otomatis.\n"
        elif status == "part_not_registered":
            yield f"[!] Part number belum terdaftar di Master Part FactoryHub.\n"
            await update_checksheet_status(
                session=session,
                checksheet_id=checksheet_id,
                status="Tidak Ada Part",
                keterangan="Part belum terdaftar di Master Part FactoryHub"
            )
        else:
            yield f"[i] Status otomatisasi selesai: {status}\n"

    except Exception as e:
        yield f"[ERROR] Terjadi kesalahan saat otomatisasi: {str(e)}\n"


async def execute_batch_submission(
    checksheet_ids: list,
    session: AsyncSession,
    submit: bool = True,
    headless: bool = False,
    browser_channel: str = "chrome"
) -> AsyncGenerator[str, None]:
    """
    Execute batch checksheet submission sequentially and stream logs in real-time.
    """
    total = len(checksheet_ids)
    yield f"[*] Memulai batch submission untuk {total} checksheet...\n"

    success_count = 0
    fail_count = 0

    for idx, cs_id in enumerate(checksheet_ids, 1):
        cs = await get_checksheet_by_id(session, cs_id)
        pno = cs.part_number if cs else f"ID #{cs_id}"
        yield f"\n==================================================\n"
        yield f"[BATCH {idx}/{total}] Memproses: {pno}\n"
        yield f"==================================================\n"

        part_success = False
        async for line in execute_checksheet_submission(
            checksheet_id=cs_id,
            session=session,
            submit=submit,
            headless=headless,
            browser_channel=browser_channel
        ):
            yield line
            if "[✓] Sukses submit" in line:
                part_success = True

        if part_success:
            success_count += 1
        else:
            fail_count += 1

        yield f"[PROGRESS] Selesai {idx}/{total} (Sukses: {success_count}, Gagal: {fail_count})\n"

    yield f"\n[BATCH_DONE] Selesai memproses {total} part! (Sukses: {success_count}, Gagal: {fail_count})\n"
