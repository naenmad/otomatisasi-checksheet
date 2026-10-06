"""
Reconciliation & Audit Service for FactoryHub Checksheets.

Performs two-way automated reconciliation between active templates on FactoryHub
and the Supabase PostgreSQL database:
1. Crawls FactoryHub /quality/checksheet-master (all pagination pages).
2. Cross-references active templates with database checksheets:
   - Template active on FactoryHub but DB status is NOT 'Checksheet Done' -> updates DB to 'Checksheet Done' + saves edit URL.
   - DB status is 'Checksheet Done' but template missing on FactoryHub -> updates DB to 'Butuh Revisi' (alerting team).
   - Syncs missing edit URLs for matched parts.
3. Records clean 1-row audit entry into ActivityLog.
4. Triggers background Google Sheets sync for real-time reflection across Overview, Data Master, and Log.
"""
import os
import re
import time
import logging
from datetime import datetime
from typing import Dict, Any, List
from playwright.async_api import async_playwright
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from core.automator import login_factoryhub, INDEX_URL
from database.models import Checksheet
from database.crud import clean_str, log_activity
from services.google_sheets_service import trigger_background_sheet_sync

logger = logging.getLogger("reconciliation_service")


async def scrape_all_factoryhub_templates(
    headless: bool = True,
    browser_channel: str = "chrome"
) -> List[Dict[str, Any]]:
    """
    Scrapes all checksheet master templates across all pagination pages on FactoryHub.
    Returns list of dicts with part_number, clean_part_number, template_name, desc, edit_url, fh_id.
    """
    templates: List[Dict[str, Any]] = []
    seen_urls = set()

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=headless, channel=browser_channel)
        page = await browser.new_page()

        try:
            print("[*] Logging into FactoryHub for master audit...")
            await login_factoryhub(page)

            curr_page = 1
            max_pages = 50  # Safety limit

            while curr_page <= max_pages:
                page_url = f"{INDEX_URL}?page={curr_page}" if curr_page > 1 else INDEX_URL
                print(f"[*] Auditing FactoryHub page {curr_page}: {page_url}...")
                await page.goto(page_url, wait_until="networkidle")

                page_data = await page.evaluate(r"""() => {
                    const rows = document.querySelectorAll('table tbody tr');
                    const items = [];

                    for (let tr of rows) {
                        const editLink = tr.querySelector('a[href*="/edit"]');
                        if (!editLink) continue;

                        const partCell = tr.cells && tr.cells[0] ? tr.cells[0].innerText.trim() : '';
                        const categoryCell = tr.cells && tr.cells[1] ? tr.cells[1].innerText.trim() : '';
                        const descCell = tr.cells && tr.cells[2] ? tr.cells[2].innerText.trim() : '';
                        const itemsCountCell = tr.cells && tr.cells[3] ? tr.cells[3].innerText.trim() : '';
                        const docRevCell = tr.cells && tr.cells[4] ? tr.cells[4].innerText.trim() : '';
                        const statusCell = tr.cells && tr.cells[5] ? tr.cells[5].innerText.trim() : '';

                        items.push({
                            part_number: partCell,
                            category: categoryCell,
                            template_name: partCell,
                            description: descCell,
                            items_count: itemsCountCell,
                            doc_rev: docRevCell,
                            status: statusCell,
                            edit_url: editLink.href
                        });
                    }

                    // Check if there is a next page link
                    const nextLink = document.querySelector('a[rel="next"]');
                    return {
                        items: items,
                        hasNext: !!nextLink
                    };
                }""")

                page_items = page_data.get("items", [])
                if not page_items:
                    break

                for item in page_items:
                    edit_url = item.get("edit_url", "")
                    if edit_url in seen_urls:
                        continue
                    seen_urls.add(edit_url)

                    # Extract ID from /quality/checksheet-master/{id}/edit
                    fh_id = ""
                    id_match = re.search(r"/checksheet-master/(\d+)/edit", edit_url)
                    if id_match:
                        fh_id = id_match.group(1)

                    p_num = item.get("part_number", "")
                    c_num = clean_str(p_num)

                    templates.append({
                        "part_number": p_num,
                        "clean_part_number": c_num,
                        "category": item.get("category", ""),
                        "template_name": item.get("template_name", ""),
                        "description": item.get("description", ""),
                        "items_count": item.get("items_count", ""),
                        "doc_rev": item.get("doc_rev", ""),
                        "status": item.get("status", ""),
                        "edit_url": edit_url,
                        "fh_id": fh_id
                    })

                if not page_data.get("hasNext", False):
                    print(f"[✓] Reached last page of FactoryHub at page {curr_page}.")
                    break

                curr_page += 1

        finally:
            await browser.close()

    print(f"[+] Total active templates scraped from FactoryHub: {len(templates)}")
    return templates


def normalize_cat_key(c: str) -> str:
    s = (c or "").lower().strip()
    if "subcont" in s:
        return "subcont"
    if "material" in s:
        return "material"
    if "std" in s:
        return "std"
    if "ssw" in s:
        return "ssw"
    if "accuracy" in s:
        return "accuracy"
    if "general" in s:
        return "general"
    return s


async def run_factoryhub_reconciliation(
    session: AsyncSession,
    headless: bool = True,
    browser_channel: str = "chrome"
) -> Dict[str, Any]:
    """
    Executes full two-way audit between FactoryHub and Supabase database.
    Supports multi-template per part number with category matching.
    """
    t0 = time.time()
    fh_templates = await scrape_all_factoryhub_templates(headless=headless, browser_channel=browser_channel)

    # Index FactoryHub templates by (clean_part_number, normalized_category) and by clean_part_number
    from typing import Tuple
    fh_by_cat: Dict[Tuple[str, str], Dict[str, Any]] = {}
    fh_by_part: Dict[str, List[Dict[str, Any]]] = {}

    for tmpl in fh_templates:
        c_num = tmpl["clean_part_number"]
        n_cat = normalize_cat_key(tmpl.get("category", ""))
        if c_num:
            fh_by_cat[(c_num, n_cat)] = tmpl
            fh_by_part.setdefault(c_num, []).append(tmpl)

    # Fetch all checksheets from Supabase
    all_cs = (await session.scalars(select(Checksheet))).all()

    updated_to_done = 0
    updated_to_revisi = 0
    updated_urls = 0

    for cs in all_cs:
        c_num = cs.clean_part_number
        cs_cat = normalize_cat_key(cs.category or "Accuracy")

        # 1. Exact match by clean part number AND category
        fh_match = fh_by_cat.get((c_num, cs_cat))

        # 2. Also check sub-parts if part_number contains / or ,
        if not fh_match and cs.part_number and ("/" in cs.part_number or "," in cs.part_number):
            sub_parts = [p.strip() for p in re.split(r'[/,]', cs.part_number) if p.strip()]
            for sp in sub_parts:
                sp_clean = clean_str(sp)
                if (sp_clean, cs_cat) in fh_by_cat:
                    fh_match = fh_by_cat[(sp_clean, cs_cat)]
                    break

        # 3. Fallback: If no exact category match, but this part only has 1 template on FactoryHub (e.g. legacy 'ACCURACY')
        if not fh_match and c_num in fh_by_part:
            candidates = fh_by_part[c_num]
            if len(candidates) == 1:
                fh_match = candidates[0]

        # Check if part exists on FactoryHub
        if fh_match:
            # If part was explicitly Canceled (e.g. incoming material coil/plat), preserve Canceled status!
            if cs.status in ("Canceled", "CANCELED"):
                if not cs.factoryhub_url or cs.factoryhub_url != fh_match["edit_url"]:
                    cs.factoryhub_url = fh_match["edit_url"]
                    cs.factoryhub_id = fh_match["fh_id"]
                    updated_urls += 1
            # Case 1: Exists on FactoryHub, but DB status is NOT 'Checksheet Done'
            elif cs.status != "Checksheet Done":
                cs.status = "Checksheet Done"
                cs.factoryhub_url = fh_match["edit_url"]
                cs.factoryhub_id = fh_match["fh_id"]
                cs.keterangan = "Sinkron dari FactoryHub (Terdeteksi aktif)"
                updated_to_done += 1
            else:
                # Case 3: Already Done, but factoryhub_url missing or different
                if not cs.factoryhub_url or cs.factoryhub_url != fh_match["edit_url"]:
                    cs.factoryhub_url = fh_match["edit_url"]
                    cs.factoryhub_id = fh_match["fh_id"]
                    updated_urls += 1
        else:
            # Case 2: In DB status is 'Checksheet Done', but template not detected in this scrape session.
            # Do NOT automatically downgrade to 'Butuh Revisi' to prevent false alerts or overwriting valid parts.
            pass

    await session.commit()
    elapsed = round(time.time() - t0, 1)

    details_str = (
        f"Audit selesai dalam {elapsed}s. {len(fh_templates)} template aktif di FactoryHub. "
        f"Hasil: {updated_to_done} diperbarui ke Done, {updated_to_revisi} ditandai Butuh Revisi, {updated_urls} URL diperbarui."
    )

    # Trigger automatic Google Sheets background sync for 3 sheets (Overview, Data Master, Log)
    trigger_background_sheet_sync()

    return {
        "status": "success",
        "elapsed_seconds": elapsed,
        "total_fh_templates": len(fh_templates),
        "total_db_checksheets": len(all_cs),
        "updated_to_done": updated_to_done,
        "updated_to_revisi": updated_to_revisi,
        "updated_urls": updated_urls,
        "synced_at": datetime.now().isoformat(),
        "details": details_str
    }
