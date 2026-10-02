"""
Automation service that triggers Playwright form filling using database inspection points
and streams log output in real-time via async generator (for SSE/WebSocket).
"""
from __future__ import annotations
import os
import re
import asyncio
import tempfile
import urllib.request
from typing import AsyncGenerator, Dict, Any, List, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from playwright.async_api import async_playwright

from database.models import User
from database.crud import get_checksheet_by_id, update_checksheet_status, log_activity
from core.automator import run_automation, launch_playwright_browser, login_factoryhub, fill_checksheet_form
from core.version import get_full_banner

import logging
logger = logging.getLogger("automation_service")

# Registry of active batch cancellation requests
ACTIVE_BATCH_CANCELLATIONS: set = set()


def cancel_batch(batch_id: str = "current"):
    """Flag a batch run to cancel immediately."""
    ACTIVE_BATCH_CANCELLATIONS.add(batch_id)


def is_batch_cancelled(batch_id: str = "current") -> bool:
    """Check if cancellation was requested for a batch."""
    return batch_id in ACTIVE_BATCH_CANCELLATIONS


def clear_batch_cancellation(batch_id: str = "current"):
    """Clear cancellation flag for a batch."""
    ACTIVE_BATCH_CANCELLATIONS.discard(batch_id)


async def execute_checksheet_submission(
    checksheet_id: int,
    session: AsyncSession,
    submit: bool = True,
    headless: bool = True,
    browser_channel: str = "chrome",
    requesting_user: Optional[User] = None
) -> AsyncGenerator[str, None]:
    """
    Execute single checksheet submission to FactoryHub and yield log lines in real-time.
    """
    cs = await get_checksheet_by_id(session, checksheet_id)
    if not cs:
        yield f"[ERROR] Checksheet ID {checksheet_id} tidak ditemukan di database.\n"
        return

    # Operator ownership validation
    if requesting_user and requesting_user.role == "operator":
        if cs.assigned_to != requesting_user.name:
            owner_str = cs.assigned_to or "Unassigned"
            yield f"[ERROR] Ditolak: Part {cs.part_number} bukan tugas Anda (Pemilik: '{owner_str}'). Hanya pemilik task atau Admin yang dapat mengirim part ini.\n"
            return

    yield f"[*] {get_full_banner()}\n"
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

    # Reference images from database: prefer Supabase CDN URL, fallback to local disk
    image_paths = []
    _temp_files: List[str] = []  # track temp files to clean up after automation
    for img in cs.images:
        p = img.image_path or ""
        url = (img.image_url or "").strip()

        if url.startswith("https://") or url.startswith("http://"):
            # Image is on Supabase CDN — download to a temp file
            try:
                suffix = os.path.splitext(url.split("?")[0])[-1] or ".webp"
                tmp = tempfile.NamedTemporaryFile(delete=False, suffix=suffix)
                urllib.request.urlretrieve(url, tmp.name)
                image_paths.append(tmp.name)
                _temp_files.append(tmp.name)
            except Exception as dl_err:
                logger.warning(f"[!] Gagal download gambar dari cloud: {url} ({dl_err})")
        elif p:
            # Local path fallback
            local_p = p if os.path.isabs(p) else os.path.abspath(p)
            if os.path.isfile(local_p):
                image_paths.append(local_p)

    meta_payload = {
        "part_number": cs.part_number,
        "part_name": cs.part_name or "",
        "model": cs.model or "-",
        "customer": cs.customer or "PT. HPM",
        "doc_number": cs.doc_number or "FO-45-01",
    }

    mode_str = "Background (Headless)" if headless else "Layar Aktif (Visible)"
    yield f"[*] Menyiapkan browser {browser_channel.upper()} [{mode_str}]...\n"
    yield f"[*] Data sumber: 100% Supabase Database (Points: {len(points_payload)}, Sketsa: {len(image_paths)}, Zero doc parsing)\n"

    try:
        result = await run_automation(
            part_or_excel=cs.part_number,
            headless=headless,
            submit=submit,
            doc_number=cs.doc_number,
            browser_channel=browser_channel,
            override_items=points_payload,
            override_metadata=meta_payload,
            override_images=image_paths
        )

        final_url = result.get("final_url", "")
        status = result.get("status", "unknown")

        # Ensure link points to specific template edit page (/checksheet-master/{id}/edit) rather than generic index
        resolved_url = final_url
        if not resolved_url or not re.search(r"/checksheet-master/\d+/edit", resolved_url):
            if cs.factoryhub_url and re.search(r"/checksheet-master/\d+/edit", cs.factoryhub_url):
                resolved_url = cs.factoryhub_url
            else:
                from services.parser_service import match_catalog_status
                cat_match = match_catalog_status(cs.part_number)
                if cat_match and cat_match.get("edit_url"):
                    resolved_url = cat_match["edit_url"]

        if status == "submitted":
            yield f"[✓] Sukses submit ke FactoryHub: {resolved_url}\n"
            await update_checksheet_status(
                session=session,
                checksheet_id=checksheet_id,
                status="Checksheet Done",
                factoryhub_url=resolved_url,
                keterangan="Selesai diinput via Web Otomasi"
            )
            await log_activity(
                session=session,
                action="SUBMIT FACTORYHUB",
                part_number=cs.part_number,
                operator=cs.assigned_to or "Operator",
                status="SUCCESS",
                details=f"Berhasil submit form dengan {len(cs.inspection_points)} poin inspeksi",
                link=resolved_url
            )
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
            await log_activity(
                session=session,
                action="SUBMIT FACTORYHUB",
                part_number=cs.part_number,
                operator=cs.assigned_to or "Operator",
                status="GAGAL",
                details="Part number belum terdaftar di Master Part FactoryHub"
            )
        else:
            yield f"[i] Status otomatisasi selesai: {status}\n"
            if not submit:
                await log_activity(
                    session=session,
                    action="DRY RUN",
                    part_number=cs.part_number,
                    operator=cs.assigned_to or "Operator",
                    status="SUCCESS",
                    details=f"Pratinjau form dan {len(cs.inspection_points)} poin inspeksi selesai (tanpa submit)"
                )

    except Exception as e:
        yield f"[ERROR] Terjadi kesalahan saat otomatisasi: {str(e)}\n"
    finally:
        # Clean up temporary files downloaded from Supabase CDN
        for tf in _temp_files:
            try:
                os.unlink(tf)
            except Exception:
                pass


async def execute_batch_submission(
    checksheet_ids: list,
    session: AsyncSession,
    submit: bool = True,
    headless: bool = True,
    browser_channel: str = "chrome",
    batch_id: str = "current",
    requesting_user: Optional[User] = None
) -> AsyncGenerator[str, None]:
    """
    Execute batch checksheet submission sequentially using a SINGLE browser session
    with one-time login for maximum speed, background execution, and instant cancellation.
    """
    clear_batch_cancellation(batch_id)

    # 1. Filter and validate permission for all requested checksheets
    runnable_checksheets = []
    skipped_count = 0

    for cs_id in checksheet_ids:
        cs = await get_checksheet_by_id(session, cs_id)
        if not cs:
            yield f"[!] Checksheet ID #{cs_id} tidak ditemukan di database.\n"
            skipped_count += 1
            continue

        if requesting_user and requesting_user.role == "operator":
            if cs.assigned_to != requesting_user.name:
                owner_str = cs.assigned_to or "Unassigned"
                yield f"[!] Lewati Part {cs.part_number}: Ditugaskan ke '{owner_str}'. Anda hanya bisa batch kirim part milik Anda sendiri. Silakan ambil task terlebih dahulu.\n"
                skipped_count += 1
                continue

        # Enforce that only parts marked as 'Reviewed' can be submitted in batch
        if cs.status != "Reviewed":
            yield f"[!] Lewati Part {cs.part_number}: Status saat ini '{cs.status}'. Batch hanya mengizinkan part berstatus 'Reviewed' (telah diverifikasi di Review & Edit).\n"
            skipped_count += 1
            continue

        runnable_checksheets.append(cs)

    total = len(runnable_checksheets)
    if total == 0:
        yield f"[!] Tidak ada checksheet yang dapat diproses (seluruh part dilewati karena bukan milik Anda atau tidak ditemukan).\n"
        return

    yield f"==================================================\n"
    yield f"[*] {get_full_banner()}\n"
    yield f"[*] Memulai batch submission untuk {total} checksheet...\n"
    yield f"[*] Mode: {'Background (Headless)' if headless else 'Layar Aktif (Visible)'} | Browser: {browser_channel.upper()}\n"
    yield f"==================================================\n"

    success_count = 0
    fail_count = 0
    submitted_any = False

    # 2. Launch browser ONCE for the entire batch
    async with async_playwright() as p:
        browser_obj = None
        context = None
        page = None
        try:
            yield f"[*] Menyiapkan browser Playwright di background...\n"
            browser_obj, context, page = await launch_playwright_browser(
                p=p,
                headless=headless,
                browser_channel=browser_channel
            )

            # 3. Login to FactoryHub ONCE for the entire batch
            yield f"[*] Melakukan login ke FactoryHub (1x untuk seluruh batch)...\n"
            await login_factoryhub(page)
            yield f"[✓] Berhasil login ke FactoryHub! Memulai pemrosesan antrean {total} part...\n"

            # 4. Process each checksheet in sequence
            for idx, cs in enumerate(runnable_checksheets, 1):
                # Check cancellation signal before processing each part
                if is_batch_cancelled(batch_id):
                    yield f"\n[!] BATCH DIHENTIKAN OLEH PENGGUNA pada antrean ke-{idx}/{total} (Part: {cs.part_number}).\n"
                    break

                yield f"\n==================================================\n"
                yield f"[BATCH {idx}/{total}] Memproses: {cs.part_number} ({cs.part_name or '-'})\n"
                yield f"==================================================\n"

                try:
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

                    image_paths = []
                    _temp_files_batch: List[str] = []
                    for img in cs.images:
                        p_img = img.image_path or ""
                        img_url = (img.image_url or "").strip()

                        if img_url.startswith("https://") or img_url.startswith("http://"):
                            try:
                                suffix = os.path.splitext(img_url.split("?")[0])[-1] or ".webp"
                                tmp = tempfile.NamedTemporaryFile(delete=False, suffix=suffix)
                                urllib.request.urlretrieve(img_url, tmp.name)
                                image_paths.append(tmp.name)
                                _temp_files_batch.append(tmp.name)
                            except Exception as dl_err:
                                yield f"[!] Gagal download gambar dari cloud: {img_url} ({dl_err})\n"
                        elif p_img:
                            local_p = p_img if os.path.isabs(p_img) else os.path.abspath(p_img)
                            if os.path.isfile(local_p):
                                image_paths.append(local_p)

                    meta_payload = {
                        "part_number": cs.part_number,
                        "part_name": cs.part_name or "",
                        "model": cs.model or "-",
                        "customer": cs.customer or "PT. HPM",
                        "doc_number": cs.doc_number or "FO-45-01",
                    }

                    yield f"[*] Mengisi checksheet master ({len(points_payload)} poin, {len(image_paths)} gambar)...\n"
                    result = await fill_checksheet_form(
                        page=page,
                        part_or_excel=cs.part_number,
                        submit=submit,
                        custom_doc_no=cs.doc_number,
                        override_items=points_payload,
                        override_metadata=meta_payload,
                        override_images=image_paths
                    )

                    status = result.get("status", "unknown")
                    final_url = result.get("final_url", "")

                    # Ensure link points to specific template edit page (/checksheet-master/{id}/edit) rather than generic index
                    resolved_url = final_url
                    if not resolved_url or not re.search(r"/checksheet-master/\d+/edit", resolved_url):
                        if cs.factoryhub_url and re.search(r"/checksheet-master/\d+/edit", cs.factoryhub_url):
                            resolved_url = cs.factoryhub_url
                        else:
                            from services.parser_service import match_catalog_status
                            cat_match = match_catalog_status(cs.part_number)
                            if cat_match and cat_match.get("edit_url"):
                                resolved_url = cat_match["edit_url"]

                    if status == "submitted":
                        yield f"[✓] Sukses submit {cs.part_number} ke FactoryHub: {resolved_url}\n"
                        await update_checksheet_status(
                            session=session,
                            checksheet_id=cs.id,
                            status="Checksheet Done",
                            factoryhub_url=resolved_url,
                            keterangan="Selesai diinput via Batch Otomasi"
                        )
                        await log_activity(
                            session=session,
                            action="SUBMIT FACTORYHUB",
                            part_number=cs.part_number,
                            operator=cs.assigned_to or (requesting_user.name if requesting_user else "Operator"),
                            status="SUCCESS",
                            details=f"Batch submit berhasil ({len(points_payload)} poin)",
                            link=resolved_url
                        )
                        success_count += 1
                        submitted_any = True
                    elif status == "part_not_registered":
                        yield f"[!] Part number {cs.part_number} belum terdaftar di Master Part FactoryHub.\n"
                        await update_checksheet_status(
                            session=session,
                            checksheet_id=cs.id,
                            status="Tidak Ada Part",
                            keterangan="Part belum terdaftar di Master Part FactoryHub"
                        )
                        await log_activity(
                            session=session,
                            action="SUBMIT FACTORYHUB",
                            part_number=cs.part_number,
                            operator=cs.assigned_to or "Operator",
                            status="GAGAL",
                            details="Part number belum terdaftar di Master Part FactoryHub"
                        )
                        fail_count += 1
                    else:
                        yield f"[i] Status otomatisasi selesai: {status}\n"
                        if not submit:
                            yield f"[✓] Dry-run form {cs.part_number} selesai.\n"
                            success_count += 1
                        else:
                            fail_count += 1

                except Exception as err:
                    yield f"[ERROR] Gagal memproses {cs.part_number}: {str(err)}\n"
                    fail_count += 1

                yield f"[PROGRESS] Selesai {idx}/{total} (Sukses: {success_count}, Gagal: {fail_count})\n"

            # 5. Sync to Google Sheets ONCE at the end of the batch
            if submitted_any and submit:
                yield f"\n[*] Memicu sinkronisasi data ke Google Sheets (1x untuk seluruh batch)...\n"
                from services.google_sheets_service import trigger_background_sheet_sync
                trigger_background_sheet_sync()
                yield f"[✓] Sinkronisasi 3 Sheet Google dijadwalkan di background.\n"

            yield f"\n[BATCH_DONE] Selesai memproses batch! (Sukses: {success_count}, Gagal: {fail_count}, Dilewati: {skipped_count})\n"

        except Exception as batch_err:
            yield f"[ERROR] Kesalahan fatal pada sesi batch: {str(batch_err)}\n"

        finally:
            try:
                if context:
                    await context.close()
                if browser_obj:
                    await browser_obj.close()
            except Exception:
                pass
            # Clean up all temp image files downloaded from Supabase CDN during this batch
            for tf in locals().get("_temp_files_batch", []):
                try:
                    os.unlink(tf)
                except Exception:
                    pass
            clear_batch_cancellation(batch_id)
            yield f"[+] Sesi browser Playwright background telah ditutup bersih.\n"

