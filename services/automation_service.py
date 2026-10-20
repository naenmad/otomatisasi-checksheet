"""
Automation service that triggers Playwright form filling using database inspection points
and streams log output in real-time via async generator (for SSE/WebSocket).
"""
from __future__ import annotations
import os
import re
import asyncio
import tempfile
import base64
import urllib.request
from typing import AsyncGenerator, Dict, Any, List, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from playwright.async_api import async_playwright

from database.models import User
from database.crud import get_checksheet_by_id, update_checksheet_status, log_activity, clean_str
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


def resolve_image_for_automation(img, cs, temp_collector: Optional[List[str]] = None) -> Optional[str]:
    """
    Robust image resolver for FactoryHub automation.
    Attempts multiple resolution strategies:
    1. Direct local disk path (if valid file)
    2. Smart multi-path candidate matching on local disk (raw pn, clean pn, no-space pn, templates)
       with extension cross-matching (.webp <-> .png <-> .jpg)
    3. Decoding embedded base64 from database if present
    4. Downloading from cloud CDN (Supabase Storage) with browser headers and extension fallbacks
    """
    p = (img.image_path or "").strip()
    url = (img.image_url or "").strip()

    # 1. Direct path check (if not URL)
    if p and not p.startswith("http://") and not p.startswith("https://"):
        local_p = p if os.path.isabs(p) else os.path.abspath(p)
        if os.path.isfile(local_p):
            return local_p

    # 2. Extract base filename to search candidate local folders
    fname = ""
    if p and not p.startswith("http://") and not p.startswith("https://"):
        fname = os.path.basename(p.replace("\\", "/"))
    elif url:
        fname = os.path.basename(url.split("?")[0])

    if fname:
        stem, orig_ext = os.path.splitext(fname)
        exts = [orig_ext, ".webp", ".png", ".jpg", ".jpeg"]
        pn = (cs.part_number or "").strip()
        c_pn = clean_str(pn)
        pn_nospace = pn.replace(" ", "")

        cand_dirs = [
            os.path.join("storage", "images", pn),
            os.path.join("storage", "images", c_pn),
            os.path.join("storage", "images", pn_nospace),
            os.path.join("storage", "images", "templates"),
            os.path.join("extracted_images", pn),
            os.path.join("extracted_images", c_pn),
        ]

        for d in cand_dirs:
            if not os.path.isdir(d):
                continue
            for ext in exts:
                cand_file = os.path.abspath(os.path.join(d, stem + ext))
                if os.path.isfile(cand_file):
                    return cand_file

    # 3. Base64 fallback from database row
    if getattr(img, "image_base64", None) and len(img.image_base64) > 100:
        b64 = img.image_base64.strip()
        if "," in b64:
            b64 = b64.split(",", 1)[1]
        try:
            raw_bytes = base64.b64decode(b64)
            suffix = os.path.splitext(fname)[1] if fname else ".webp"
            tmp = tempfile.NamedTemporaryFile(delete=False, suffix=suffix or ".webp")
            tmp.write(raw_bytes)
            tmp.close()
            if temp_collector is not None:
                temp_collector.append(tmp.name)
            return tmp.name
        except Exception as b64_err:
            logger.debug(f"Failed decoding base64 image: {b64_err}")

    # 4. Cloud CDN download (Supabase Storage) with browser User-Agent & extension fallback
    download_urls = []
    if url.startswith("http://") or url.startswith("https://"):
        download_urls.append(url)
        if url.endswith(".png"):
            download_urls.append(url[:-4] + ".webp")
        elif url.endswith(".webp"):
            download_urls.append(url[:-5] + ".png")
    elif p.startswith("http://") or p.startswith("https://"):
        download_urls.append(p)

    for dl_url in download_urls:
        try:
            suffix = os.path.splitext(dl_url.split("?")[0])[-1] or ".webp"
            tmp = tempfile.NamedTemporaryFile(delete=False, suffix=suffix)
            req = urllib.request.Request(
                dl_url,
                headers={"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"}
            )
            with urllib.request.urlopen(req, timeout=10) as resp:
                if resp.status == 200:
                    tmp.write(resp.read())
                    tmp.close()
                    if temp_collector is not None:
                        temp_collector.append(tmp.name)
                    return tmp.name
        except Exception:
            continue

    return None


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

    op_name = cs.assigned_to if (cs.assigned_to and cs.assigned_to not in ("Unassigned", "Belum Ditugaskan")) else "Operator"
    yield f"[*] {get_full_banner()}\n"
    yield f"[*] Memulai otomatisasi untuk Part: {cs.part_number} ({cs.part_name}) | PIC Revisi: {op_name}\n"
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

    # Reference images from database: multi-strategy local candidate + cloud resolver
    image_paths = []
    _temp_files: List[str] = []  # track temp files to clean up after automation
    for img in cs.images:
        resolved = resolve_image_for_automation(img, cs, temp_collector=_temp_files)
        if resolved:
            image_paths.append(resolved)
        else:
            logger.warning(f"[!] Gagal resolve/download gambar untuk part {cs.part_number}: {img.image_url or img.image_path}")

    meta_payload = {
        "part_number": cs.part_number,
        "part_name": cs.part_name or "",
        "model": cs.model or "-",
        "customer": cs.customer or "PT. HPM",
        "doc_number": cs.doc_number or "FO-45-01",
        "category": cs.category or "Accuracy",
        "checksheet_category": cs.category or "Accuracy"
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
            op_name = cs.assigned_to if (cs.assigned_to and cs.assigned_to not in ("Unassigned", "Belum Ditugaskan")) else "Operator"
            is_admin = getattr(requesting_user, "role", "") == "admin"
            submitter_note = f" (disubmit oleh Admin {requesting_user.name})" if requesting_user and is_admin and requesting_user.name != cs.assigned_to else ""
            yield f"[✓] Sukses submit ke FactoryHub (PIC Revisi: {op_name}): {resolved_url}\n"
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
                operator=op_name,
                status="SUCCESS",
                details=f"Berhasil submit form dengan {len(cs.inspection_points)} poin inspeksi{submitter_note}",
                link=resolved_url
            )
            from services.google_sheets_service import trigger_background_sheet_sync
            trigger_background_sheet_sync()
            yield f"[i] Sinkronisasi baris ke Google Sheet dipicu secara otomatis (PIC: {op_name}).\n"
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

        # Strict user ownership check: Cannot batch parts belonging to others or unassigned parts
        if not requesting_user:
            yield f"[!] Ditolak: Anda belum login. Batch submission memerlukan autentikasi pengguna.\n"
            skipped_count += 1
            continue

        is_admin = getattr(requesting_user, "role", "") == "admin"
        assigned_clean = (cs.assigned_to or "").strip().lower()
        is_my_part = (
            is_admin
            or assigned_clean == requesting_user.name.strip().lower()
            or assigned_clean == requesting_user.username.strip().lower()
        )
        if not is_my_part:
            owner_str = cs.assigned_to or "Unassigned"
            yield f"[!] Lewati Part {cs.part_number}: Ditugaskan ke '{owner_str}'. Anda tidak dapat melakukan batch part milik orang lain. Silakan ambil task terlebih dahulu.\n"
            skipped_count += 1
            continue

        # Enforce that only parts marked as 'Reviewed' or 'Siap Kirim' can be submitted in batch
        status_clean = (cs.status or "").strip().lower()
        if status_clean not in ("reviewed", "siap kirim", "siap_kirim"):
            yield f"[!] Lewati Part {cs.part_number}: Status saat ini '{cs.status}'. Batch hanya mengizinkan part berstatus 'Siap Kirim' / 'Reviewed' (telah diverifikasi di Review & Edit).\n"
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

                op_name = cs.assigned_to if (cs.assigned_to and cs.assigned_to not in ("Unassigned", "Belum Ditugaskan")) else "Operator"
                yield f"\n==================================================\n"
                yield f"[BATCH {idx}/{total}] Memproses: {cs.part_number} ({cs.part_name or '-'}) | PIC Revisi: {op_name}\n"
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
                        resolved = resolve_image_for_automation(img, cs, temp_collector=_temp_files_batch)
                        if resolved:
                            image_paths.append(resolved)
                        else:
                            yield f"[!] Lewati gambar (gagal resolve/download): {img.image_url or img.image_path}\n"

                    meta_payload = {
                        "part_number": cs.part_number,
                        "part_name": cs.part_name or "",
                        "model": cs.model or "-",
                        "customer": cs.customer or "PT. HPM",
                        "doc_number": cs.doc_number or "FO-45-01",
                        "category": cs.category or "Accuracy",
                        "checksheet_category": cs.category or "Accuracy"
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
                        op_name = cs.assigned_to if (cs.assigned_to and cs.assigned_to not in ("Unassigned", "Belum Ditugaskan")) else "Operator"
                        submitter_note = f" (disubmit oleh Admin {requesting_user.name})" if requesting_user and is_admin and requesting_user.name != cs.assigned_to else ""
                        yield f"[✓] Sukses submit {cs.part_number} ke FactoryHub (PIC Revisi: {op_name}): {resolved_url}\n"
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
                            operator=op_name,
                            status="SUCCESS",
                            details=f"Batch submit berhasil ({len(points_payload)} poin){submitter_note}",
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

