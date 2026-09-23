"""
Playwright Automator for Checksheet Master
Automates form filling on FactoryHub:
- Login with employee_id and password
- Category part checking (Regular vs New Project Part)
- Daily checksheet selection
- Doc number setting
- Reference image upload
- Inspection points population
- Template Diff comparison for existing templates (EDIT mode)
- Centralized execution logging (Excel, JSON, text)
- Optional auto-submission or interactive review mode
"""

import os
import re
import sys
import time
import asyncio
import urllib.parse
from typing import Optional, Dict, Any, List
from playwright.async_api import async_playwright, Page, Browser
from dotenv import load_dotenv

from extractor import (
    extract_metadata,
    extract_reference_images,
    extract_inspection_points,
    get_reference_images,
    resolve_part_document
)
import logger

# Load configurations from .env
load_dotenv()

FACTORYHUB_BASE_URL = os.getenv("FACTORYHUB_BASE_URL", "https://factoryhub.summitadyawinsa.co.id")
LOGIN_URL = f"{FACTORYHUB_BASE_URL}/login"
CREATE_URL = f"{FACTORYHUB_BASE_URL}/quality/checksheet-master/create"
INDEX_URL = f"{FACTORYHUB_BASE_URL}/quality/checksheet-master"

DEFAULT_NIK = os.getenv("FACTORYHUB_NIK", "")
DEFAULT_PASSWORD = os.getenv("FACTORYHUB_PASSWORD", "")


async def login_factoryhub(page: Page, nik: str = DEFAULT_NIK, password: str = DEFAULT_PASSWORD):
    """Ensure user is logged into FactoryHub."""
    print(f"[*] Checking session / navigating to {LOGIN_URL}...")
    await page.goto(LOGIN_URL, wait_until="networkidle")

    # If already logged in (redirected to dashboard or checksheet)
    if "login" not in page.url:
        print(f"[+] Already logged in: {page.url}")
        return

    print(f"[*] Logging in with NIK: {nik}...")
    await page.fill('input[name="employee_id"]', nik)
    await page.fill('input[name="password"]', password)

    # Submit login
    submit_btn = await page.query_selector('button[type="submit"]')
    if submit_btn:
        await submit_btn.click()
    else:
        await page.keyboard.press("Enter")

    # Wait for navigation
    await page.wait_for_load_state("networkidle")
    print(f"[+] Login complete. Current URL: {page.url}")


async def find_existing_template(page: Page, part_no: str) -> Optional[Dict[str, str]]:
    """
    Search for existing checksheet master template by Part Number on FactoryHub.
    FactoryHub paginates templates (10 items per page), so we MUST query using
    the server-side search parameter (?search=...) to search across all pages.
    Returns dict with editUrl, templateName, partNumber if found, else None.
    """
    clean_target = re.sub(r"[^A-Za-z0-9]", "", part_no or "").upper()
    print(f"[*] Memeriksa apakah template untuk '{part_no}' (clean: {clean_target}) sudah pernah dibuat sebelumnya...")

    # Candidates to query via server-side search
    candidates = [clean_target]
    if part_no and part_no.strip() not in candidates:
        candidates.append(part_no.strip())

    prefix_match = re.match(r"^([A-Z0-9]{5,8})", clean_target)
    if prefix_match:
        pref = prefix_match.group(1)
        if pref not in candidates:
            candidates.append(pref)

    for term in candidates:
        search_url = f"{INDEX_URL}?search={urllib.parse.quote(term)}"
        try:
            await page.goto(search_url, wait_until="networkidle")
        except Exception as e:
            print(f"[!] Warning: Gagal memuat {search_url}: {e}")
            continue

        found = await page.evaluate(r"""(target) => {
            const rows = document.querySelectorAll('table tbody tr');
            let exactMatch = null;
            let partialMatch = null;

            for (let tr of rows) {
                const editLink = tr.querySelector('a[href*="/edit"]');
                if (!editLink) continue; // Skip header or 'No templates found' row

                const partCell = tr.cells && tr.cells[0] ? tr.cells[0].innerText.trim() : '';
                const formatCell = tr.cells && tr.cells[1] ? tr.cells[1].innerText.trim() : '';
                const descCell = tr.cells && tr.cells[2] ? tr.cells[2].innerText.trim() : '';
                const cleanPart = partCell.toUpperCase().replace(/[^A-Za-z0-9]/g, '');

                const matchData = {
                    templateName: formatCell || tr.innerText.split('\n')[0],
                    partNumber: partCell,
                    description: descCell,
                    editUrl: editLink.href
                };

                // Alphanumeric clean match takes strict priority
                if (cleanPart === target) {
                    exactMatch = matchData;
                    break;
                }
            }
            return exactMatch;
        }""", clean_target)

        if found:
            print(f"[+] DITEMUKAN TEMPLATE: Part '{found.get('partNumber')}' | Format '{found['templateName']}' (ID: {found['editUrl'].split('/')[-2]}) -> {found['editUrl']}")
            return found

    print(f"[-] Belum ada template di database untuk part '{part_no}'.")
    return None


def compute_template_diff(
    old_meta: Dict[str, Any],
    old_items: List[Dict[str, str]],
    new_meta: Dict[str, Any],
    new_items: List[Dict[str, str]]
) -> Dict[str, Any]:
    """
    Compare previous template state on FactoryHub with incoming Excel/PDF checksheet data.
    Detects doc_number differences, part_name/description changes, added, removed, and modified inspection points.
    """
    meta_diff = {}
    old_doc = str(old_meta.get("doc_number") or "").strip()
    new_doc = str(new_meta.get("doc_number") or "").strip()
    if old_doc and new_doc and old_doc.lower() != new_doc.lower():
        meta_diff["doc_number"] = {"old": old_doc, "new": new_doc}

    old_desc = str(old_meta.get("description") or "").strip()
    new_desc = str(new_meta.get("part_name") or "").strip()
    if old_desc and new_desc and old_desc.lower() != new_desc.lower():
        meta_diff["description"] = {"old": old_desc, "new": new_desc}

    added = []
    removed = []
    modified = []
    unchanged = []

    old_pool = list(old_items)
    used_old_indices = set()

    for n_idx, n_item in enumerate(new_items):
        n_no = str(n_item.get("item_no", "")).strip()
        n_name = str(n_item.get("inspection_item", "")).strip().lower()
        n_std = str(n_item.get("standard", "")).strip()
        n_method = str(n_item.get("method", "")).strip()

        matched_old_idx = None
        # 1. Exact match on item_no and inspection_item
        for o_idx, o_item in enumerate(old_pool):
            if o_idx in used_old_indices:
                continue
            o_no = str(o_item.get("item_no", "")).strip()
            o_name = str(o_item.get("inspection_item", "")).strip().lower()
            if o_no == n_no and (o_name == n_name or n_name in o_name or o_name in n_name):
                matched_old_idx = o_idx
                break

        # 2. Fallback match on item_no
        if matched_old_idx is None and n_no:
            for o_idx, o_item in enumerate(old_pool):
                if o_idx in used_old_indices:
                    continue
                o_no = str(o_item.get("item_no", "")).strip()
                if o_no == n_no:
                    matched_old_idx = o_idx
                    break

        if matched_old_idx is not None:
            used_old_indices.add(matched_old_idx)
            o_item = old_pool[matched_old_idx]
            o_std = str(o_item.get("standard", "")).strip()
            o_method = str(o_item.get("method", "")).strip()
            o_name_orig = str(o_item.get("inspection_item", "")).strip()

            is_modified = False
            mod_detail = {
                "item_no": n_item.get("item_no"),
                "inspection_item": n_item.get("inspection_item"),
                "changes": []
            }

            if o_std != n_std:
                is_modified = True
                mod_detail["changes"].append(f"Standard: '{o_std}' -> '{n_std}'")
                mod_detail["old_standard"] = o_std
                mod_detail["new_standard"] = n_std

            if n_method and o_method != n_method:
                is_modified = True
                mod_detail["changes"].append(f"Method: '{o_method}' -> '{n_method}'")
                mod_detail["old_method"] = o_method
                mod_detail["new_method"] = n_method

            if o_name_orig != n_item.get("inspection_item"):
                is_modified = True
                mod_detail["changes"].append(f"Item Name: '{o_name_orig}' -> '{n_item.get('inspection_item')}'")
                mod_detail["old_inspection_item"] = o_name_orig
                mod_detail["new_inspection_item"] = n_item.get("inspection_item")

            if is_modified:
                modified.append(mod_detail)
            else:
                unchanged.append(n_item)
        else:
            added.append(n_item)

    # Remaining old items were removed
    for o_idx, o_item in enumerate(old_pool):
        if o_idx not in used_old_indices:
            removed.append(o_item)

    # Build unified comparison rows for tabular display
    comparison_rows = []
    for it in added:
        comparison_rows.append({
            "status": "ADDED",
            "item_no": it.get("item_no"),
            "inspection_item": it.get("inspection_item"),
            "old_standard": "-",
            "new_standard": it.get("standard") or "-",
            "old_method": "-",
            "new_method": it.get("method") or "-",
            "changes": ["Titik baru ditambahkan"]
        })
    for it in modified:
        comparison_rows.append({
            "status": "MODIFIED",
            "item_no": it.get("item_no"),
            "inspection_item": it.get("inspection_item"),
            "old_standard": it.get("old_standard") or "-",
            "new_standard": it.get("new_standard") or "-",
            "old_method": it.get("old_method") or "-",
            "new_method": it.get("new_method") or "-",
            "changes": it.get("changes", [])
        })
    for it in removed:
        comparison_rows.append({
            "status": "REMOVED",
            "item_no": it.get("item_no"),
            "inspection_item": it.get("inspection_item"),
            "old_standard": it.get("standard") or "-",
            "new_standard": "-",
            "old_method": it.get("method") or "-",
            "new_method": "-",
            "changes": ["Titik lama dihapus"]
        })
    for it in unchanged:
        comparison_rows.append({
            "status": "UNCHANGED",
            "item_no": it.get("item_no"),
            "inspection_item": it.get("inspection_item"),
            "old_standard": it.get("standard") or "-",
            "new_standard": it.get("standard") or "-",
            "old_method": it.get("method") or "-",
            "new_method": it.get("method") or "-",
            "changes": ["Identik"]
        })

    def _sort_key(x):
        num_str = re.search(r"\d+", str(x.get("item_no") or ""))
        return (int(num_str.group(0)) if num_str else 9999, str(x.get("inspection_item") or ""))

    comparison_rows.sort(key=_sort_key)

    diff_parts = []
    if added:
        diff_parts.append(f"+{len(added)} ditambah")
    if removed:
        diff_parts.append(f"-{len(removed)} dihapus")
    if modified:
        diff_parts.append(f"{len(modified)} diubah")
    if not diff_parts:
        diff_parts.append("Titik inspeksi identik")

    summary_str = f"{', '.join(diff_parts)} ({len(old_items)} lama -> {len(new_items)} baru)"
    if meta_diff:
        changes = [f"{k}: '{v['old']}' -> '{v['new']}'" for k, v in meta_diff.items()]
        summary_str += f" | Meta: {', '.join(changes)}"

    return {
        "summary": summary_str,
        "meta_diff": meta_diff,
        "added": added,
        "removed": removed,
        "modified": modified,
        "unchanged": unchanged,
        "unchanged_count": len(unchanged),
        "old_count": len(old_items),
        "new_count": len(new_items),
        "comparison_rows": comparison_rows
    }


def print_template_diff(diff: Dict[str, Any], part_no: str):
    """Print an eye-catching ASCII diff table in the console."""
    print("\n" + "=" * 70)
    print(f"           PERBANDINGAN TEMPLATE (DIFF EDIT MODE): {part_no}")
    print("=" * 70)

    if diff.get("meta_diff"):
        print("[*] Perubahan Metadata:")
        for field, vals in diff["meta_diff"].items():
            print(f"    • {field.upper()}: '{vals['old']}' ➔ '{vals['new']}'")
        print("-" * 70)

    print(f"[*] Ringkasan Titik: {diff['old_count']} lama ➔ {diff['new_count']} baru ({diff['summary']})")

    if diff.get("added"):
        print(f"\n[+] TITIK DITAMBAH ({len(diff['added'])} titik):")
        for it in diff["added"][:10]:
            print(f"    + [Item {it.get('item_no')}] {it.get('inspection_item')} | Std: {it.get('standard') or '-'} | Method: {it.get('method') or '-'}")
        if len(diff["added"]) > 10:
            print(f"    ... dan {len(diff['added']) - 10} titik tambahan lainnya")

    if diff.get("modified"):
        print(f"\n[~] TITIK DIUBAH ({len(diff['modified'])} titik):")
        for it in diff["modified"][:10]:
            chg_str = ", ".join(it["changes"])
            print(f"    ~ [Item {it.get('item_no')}] {it.get('inspection_item')}: {chg_str}")
        if len(diff["modified"]) > 10:
            print(f"    ... dan {len(diff['modified']) - 10} titik perubahan lainnya")

    if diff.get("removed"):
        print(f"\n[-] TITIK DIHAPUS ({len(diff['removed'])} titik):")
        for it in diff["removed"][:10]:
            print(f"    - [Item {it.get('item_no')}] {it.get('inspection_item')} | Std: {it.get('standard') or '-'}")
        if len(diff["removed"]) > 10:
            print(f"    ... dan {len(diff['removed']) - 10} titik dihapus lainnya")

    print("=" * 70 + "\n")


async def fill_checksheet_form(
    page: Page,
    part_or_excel: str,
    submit: bool = False,
    custom_doc_no: Optional[str] = None,
    manual_images_dir: Optional[str] = None,
    scan_images: Optional[bool] = None,
    override_items: Optional[List[Dict[str, str]]] = None
) -> Dict[str, Any]:
    """Extract data from Excel/PDF and fill checksheet master creation/editing form."""
    print(f"\n[*] Resolving part document: {part_or_excel}")
    doc_pkg = resolve_part_document(
        part_or_path=part_or_excel,
        scan_images=scan_images,
        manual_images_dir=manual_images_dir
    )
    doc_path = doc_pkg["file_path"]
    file_type = doc_pkg["file_type"]
    images = doc_pkg["images"]
    meta = doc_pkg["metadata"]
    scan_mode_str = "Scan Dokumen" if doc_pkg["scan_images"] else "Folder Images"

    if custom_doc_no:
        meta["doc_number"] = custom_doc_no

    print(f"[+] Part Document Resolved:")
    print(f"    - Part Number: {meta['part_number']}")
    print(f"    - Document   : {os.path.basename(doc_path)} ({file_type.upper()})")
    print(f"    - Doc Number : {meta['doc_number']}")
    print(f"    - Part Name  : {meta['part_name']}")
    print(f"    - Images     : {len(images)} file(s)")

    if override_items is not None:
        items = override_items
        print(f"[+] Menggunakan {len(items)} inspection point(s) dari direct input (server scrape/override).")
    else:
        print(f"[*] Extracting inspection points from {file_type.upper()}...")
        items = extract_inspection_points(doc_path)
        print(f"[+] Found {len(items)} inspection point(s).")

    part_no = meta["part_number"]
    existing_template = await find_existing_template(page, part_no)
    diff_data = None

    if existing_template:
        mode_used = "EDIT"
        edit_url = existing_template["editUrl"]
        print(f"\n[+] DITEMUKAN TEMPLATE: '{existing_template['templateName']}' sudah ada di database.")
        print(f"[+] Membuka mode EDIT: {edit_url}")
        await page.goto(edit_url, wait_until="networkidle")

        # Scrape current template values for Diff comparison
        print("[*] Mengambil data template lama dari browser untuk perbandingan (diff)...")
        old_template_data = await page.evaluate(r"""() => {
            const docInp = document.querySelector('input[name="doc_number"]');
            const descInp = document.querySelector('input[name="description"]');
            const tbody = document.getElementById('inspection-tbody');

            const oldItems = [];
            if (tbody) {
                const trs = tbody.querySelectorAll('tr.inspection-row, tr');
                trs.forEach((tr, index) => {
                    const getVal = (sel) => {
                        const el = tr.querySelector(sel);
                        return el ? el.value.trim() : '';
                    };
                    const itemNo = getVal('input[name*="[item_no]"]') || (index + 1).toString();
                    const itemDesc = getVal('input[name*="[inspection_item]"]');
                    const std = getVal('input[name*="[standard]"]');
                    const method = getVal('input[name*="[method]"], input[name*="[instrument_tools]"]') ||
                                   (tr.cells && tr.cells[5] && tr.cells[5].querySelector('input') ? tr.cells[5].querySelector('input').value.trim() : '');
                    const master = getVal('input[name*="[master_data]"]') ||
                                   (tr.cells && tr.cells[6] && tr.cells[6].querySelector('input') ? tr.cells[6].querySelector('input').value.trim() : '');

                    if (itemDesc || std) {
                        oldItems.push({
                            item_no: itemNo,
                            inspection_item: itemDesc,
                            standard: std,
                            method: method,
                            master_data: master
                        });
                    }
                });
            }

            return {
                doc_number: docInp ? docInp.value.trim() : '',
                description: descInp ? descInp.value.trim() : '',
                items: oldItems
            };
        }""")

        # Compute and display Diff
        diff_data = compute_template_diff(
            old_meta=old_template_data,
            old_items=old_template_data.get("items", []),
            new_meta=meta,
            new_items=items
        )
        print_template_diff(diff_data, part_no)

        # 1. Update Doc Number if input exists
        doc_no = meta["doc_number"]
        if doc_no:
            print(f"[*] Updating Doc Number: {doc_no}...")
            doc_inp = await page.query_selector('input[name="doc_number"]')
            if doc_inp:
                await doc_inp.fill(doc_no)

        # 2. Update Description if input exists
        if meta.get("part_name"):
            desc_inp = await page.query_selector('input[name="description"]')
            if desc_inp:
                await desc_inp.fill(meta["part_name"])

        # 3. Upload Reference Images if available
        if images:
            print(f"[*] Uploading {len(images)} reference image(s)...")
            img_input = await page.query_selector('input[name="images[]"]')
            if img_input:
                await img_input.set_input_files(images)
                uploaded_count = await page.evaluate("""() => {
                    const inp = document.querySelector('input[name="images[]"]');
                    return inp ? inp.files.length : 0;
                }""")
                print(f"[+] {uploaded_count} image(s) attached to form input.")

        # 4. Populate inspection points (replace existing rows)
        print(f"[*] Mengganti baris lama dengan {len(items)} titik inspeksi baru...")
        populate_stats = await page.evaluate("""(itemsList) => {
            const tbody = document.getElementById('inspection-tbody');
            if (!tbody) return { error: 'Tbody not found' };

            // Clear existing rows completely
            tbody.innerHTML = '';

            itemsList.forEach((item, index) => {
                if (typeof addNewRow === 'function') {
                    addNewRow();
                } else if (typeof addItem === 'function') {
                    addItem();
                }

                const tr = tbody.children[index];
                if (tr) {
                    const setVal = (inp, val) => {
                        if (inp) {
                            inp.value = val;
                            inp.dispatchEvent(new Event('input', { bubbles: true }));
                            inp.dispatchEvent(new Event('change', { bubbles: true }));
                        }
                    };

                    const itemNoInp = tr.querySelector('input[name*="[item_no]"]');
                    setVal(itemNoInp, item.item_no || (index + 1));

                    const itemInp = tr.querySelector('input[name*="[inspection_item]"]');
                    setVal(itemInp, item.inspection_item || '');

                    const stdInp = tr.querySelector('input[name*="[standard]"]');
                    setVal(stdInp, item.standard || '');

                    const methodInp = tr.querySelector('input[name*="[method]"], input[name*="[instrument_tools]"]') ||
                                      (tr.cells && tr.cells[5] ? tr.cells[5].querySelector('input') : null);
                    setVal(methodInp, item.method || '');

                    const masterInp = tr.querySelector('input[name*="[master_data]"]') ||
                                      (tr.cells && tr.cells[6] ? tr.cells[6].querySelector('input') : null);
                    setVal(masterInp, item.master_data || '');
                }
            });

            return {
                totalRows: tbody.querySelectorAll('tr.inspection-row').length
            };
        }""", items)
        print(f"[+] Berhasil mengisi {populate_stats.get('totalRows', 0)} baris di tabel inspeksi.")

    else:
        mode_used = "CREATE"
        print(f"\n[*] BELUM ADA TEMPLATE: Part {part_no} belum terdaftar.")
        print(f"[*] Membuka mode CREATE baru: {CREATE_URL}")
        await page.goto(CREATE_URL, wait_until="networkidle")

        # 1. Part Category Type Selection
        print(f"[*] Checking Part Number: {part_no}...")
        part_selection_result = await page.evaluate(r"""(partNo) => {
            const cleanStr = (s) => (s || '').toUpperCase().replace(/[-\s_]/g, '');
            const targetClean = cleanStr(partNo);
            const prefixClean = targetClean.slice(0, 5);

            // Step 1: Check Regular Production Part select options
            const regularSelect = document.getElementById('part_num_select');
            let regularFound = false;
            let similar = [];

            if (regularSelect) {
                for (let i = 0; i < regularSelect.options.length; i++) {
                    const opt = regularSelect.options[i];
                    const optValClean = cleanStr(opt.value);
                    const optTextClean = cleanStr(opt.text);
                    if (optValClean.includes(targetClean) || optTextClean.includes(targetClean)) {
                        regularSelect.selectedIndex = i;
                        regularFound = true;
                        if (typeof updateTemplateName === 'function') {
                            updateTemplateName();
                        }
                        break;
                    } else if (prefixClean && (optValClean.includes(prefixClean) || optTextClean.includes(prefixClean))) {
                        similar.push(opt.text || opt.value);
                    }
                }
            }

            if (regularFound) {
                return { type: 'regular', found: true, selectedValue: regularSelect.value, similar: [] };
            }

            // Step 2: Switch to New Project Part
            if (typeof togglePartType === 'function') {
                togglePartType('project');
            }
            const projRadio = document.querySelector('input[name="part_type"][value="project"]');
            if (projRadio) {
                projRadio.checked = true;
            }

            const projSelect = document.getElementById('part_project_id');
            let projFound = false;
            if (projSelect) {
                for (let i = 0; i < projSelect.options.length; i++) {
                    const opt = projSelect.options[i];
                    const optTextClean = cleanStr(opt.text);
                    const dataNumClean = cleanStr(opt.getAttribute('data-num'));
                    if (optTextClean.includes(targetClean) || dataNumClean.includes(targetClean)) {
                        projSelect.selectedIndex = i;
                        projFound = true;
                        if (typeof updateTemplateNameProject === 'function') {
                            updateTemplateNameProject();
                        }
                        break;
                    } else if (prefixClean && (optTextClean.includes(prefixClean) || dataNumClean.includes(prefixClean))) {
                        similar.push(opt.text || dataNumClean);
                    }
                }
            }

            return {
                type: 'project',
                found: projFound,
                selectedValue: projSelect ? projSelect.value : null,
                similar: similar.slice(0, 5)
            };
        }""", part_no)

        print(f"[+] Part selection: Category = {part_selection_result['type']}, Found = {part_selection_result['found']}")
        if not part_selection_result["found"]:
            print("\n" + "="*65)
            print(" [!] PERHATIAN: PART NUMBER BELUM TERDAFTAR DI FACTORYHUB!")
            print("="*65)
            print(f" Part Number '{part_no}' tidak ditemukan di:")
            print("   1. Master Checksheet Template (Template belum pernah dibuat)")
            print("   2. Regular Production Part (Belum terdaftar di Master Part)")
            print("   3. New Project Part (Belum terdaftar di Master Part)")

            similar = part_selection_result.get("similar", [])
            if similar:
                print("\n Part yang mirip ditemukan di FactoryHub:")
                for s in similar:
                    print(f"   • {s}")

            print("\n [INFO] Di portal FactoryHub, Template Name bersifat read-only")
            print("        dan HANYA bisa dibuat jika Part Number sudah didaftarkan")
            print("        ke Master Part oleh tim Quality / Admin.")
            print("="*65 + "\n")

            # Log this failed run
            logger.log_execution(
                part_number=part_no,
                doc_file=doc_path,
                file_type=file_type,
                scan_mode=scan_mode_str,
                result_action="TIDAK ADA",
                points_count=len(items),
                images_count=len(images),
                diff_summary="-",
                notes="Part number belum terdaftar di Master Part FactoryHub"
            )

            return {
                "status": "part_not_registered",
                "part_number": part_no,
                "message": f"Part number '{part_no}' belum terdaftar di FactoryHub."
            }

        # 1b. Checksheet Category (Accuracy vs General)
        checksheet_cat = meta.get("checksheet_category") or "Accuracy"
        print(f"[*] Selecting Category: {checksheet_cat}...")
        await page.evaluate(r"""(catName) => {
            const catSelect = document.querySelector('select[name="category"]');
            if (catSelect && catName) {
                for (let i = 0; i < catSelect.options.length; i++) {
                    const opt = catSelect.options[i];
                    if (opt.value.toLowerCase() === catName.toLowerCase() || opt.text.toLowerCase() === catName.toLowerCase()) {
                        catSelect.selectedIndex = i;
                        break;
                    }
                }
            }
        }""", checksheet_cat)

        # 2. Checksheet Format: Daily Checksheet
        print("[*] Selecting Format: daily (Daily Checksheet)...")
        await page.evaluate("""() => {
            const formatSelect = document.getElementById('format_select');
            if (formatSelect) {
                formatSelect.value = 'daily';
                if (typeof updateTableHead === 'function') {
                    updateTableHead();
                }
            }
        }""")

        # 3. Category (Default to Accuracy if available)
        await page.evaluate("""() => {
            const catSelect = document.querySelector('select[name="category"]');
            if (catSelect) {
                for (let opt of catSelect.options) {
                    if (opt.value.toLowerCase() === 'accuracy') {
                        catSelect.value = opt.value;
                        break;
                    }
                }
            }
        }""")

        # 4. Doc Number
        doc_no = meta["doc_number"]
        if doc_no:
            print(f"[*] Setting Doc Number: {doc_no}...")
            await page.fill('input[name="doc_number"]', doc_no)

        # 5. Reference Images Upload
        if images:
            print(f"[*] Uploading {len(images)} reference image(s)...")
            img_input = await page.query_selector('input[name="images[]"]')
            if img_input:
                await img_input.set_input_files(images)
                uploaded_count = await page.evaluate("""() => {
                    const inp = document.querySelector('input[name="images[]"]');
                    return inp ? inp.files.length : 0;
                }""")
                print(f"[+] {uploaded_count} image(s) attached to form input.")

        # 6. Inspection Points Population
        print(f"[*] Populating {len(items)} inspection points...")
        populate_stats = await page.evaluate("""(itemsList) => {
            const tbody = document.getElementById('inspection-tbody');
            if (!tbody) return { error: 'Tbody not found' };

            tbody.innerHTML = '';

            itemsList.forEach((item, index) => {
                if (typeof addNewRow === 'function') {
                    addNewRow();
                } else if (typeof addItem === 'function') {
                    addItem();
                }

                const tr = tbody.children[index];
                if (tr) {
                    const setVal = (inp, val) => {
                        if (inp) {
                            inp.value = val;
                            inp.dispatchEvent(new Event('input', { bubbles: true }));
                            inp.dispatchEvent(new Event('change', { bubbles: true }));
                        }
                    };

                    const itemNoInp = tr.querySelector('input[name*="[item_no]"]');
                    setVal(itemNoInp, item.item_no || (index + 1));

                    const itemInp = tr.querySelector('input[name*="[inspection_item]"]');
                    setVal(itemInp, item.inspection_item || ('Point ' + (index + 1)));

                    const stdInp = tr.querySelector('input[name*="[standard]"]');
                    setVal(stdInp, item.standard || '-');

                    const methodInp = tr.querySelector('input[name*="[method]"], input[name*="[instrument_tools]"]') ||
                                      (tr.cells && tr.cells[5] ? tr.cells[5].querySelector('input') : null);
                    setVal(methodInp, item.method || 'Visual');

                    const masterInp = tr.querySelector('input[name*="[master_data]"]') ||
                                      (tr.cells && tr.cells[6] ? tr.cells[6].querySelector('input') : null);
                    setVal(masterInp, item.master_data || '');
                }
            });

            return {
                totalRows: tbody.querySelectorAll('tr.inspection-row').length
            };
        }""", items)
        print(f"[+] Populated {populate_stats.get('totalRows', 0)} rows in inspection table.")

    # Save screenshot of prepared form
    screenshot_path = "checksheet_prepared.png"
    await page.screenshot(path=screenshot_path, full_page=True)
    print(f"[+] Screenshot of prepared checksheet saved to: {os.path.abspath(screenshot_path)}")

    button_text = "Update Template" if mode_used == "EDIT" else "Save Template"
    diff_summary_str = diff_data["summary"] if diff_data else "-"

    # Log to Centralized History (Excel & JSON)
    logger.log_execution(
        part_number=part_no,
        doc_file=doc_path,
        file_type=file_type,
        scan_mode=scan_mode_str,
        result_action="UPDATE" if mode_used == "EDIT" else "BARU",
        points_count=len(items),
        images_count=len(images),
        diff_summary=diff_summary_str,
        diff_details=diff_data,
        notes="Template berhasil diupdate" if mode_used == "EDIT" else "Template baru berhasil disiapkan"
    )

    # 7. Submit or Review
    if submit:
        print(f"[*] Submitting form (clicking '{button_text}')...")
        submit_button = await page.query_selector('button[type="submit"]:has-text("Update Template"), button[type="submit"]:has-text("Save Template"), button[type="submit"]')
        if submit_button:
            await submit_button.click()
            await page.wait_for_load_state("networkidle")
            
            # Verify if redirected or still on create
            if "/create" in page.url:
                print(f"[!] Warning: Page still on {page.url}. Checking for validation errors...")
                errors = await page.evaluate("""() => {
                    const errs = [];
                    document.querySelectorAll('.invalid-feedback, .alert-danger, :invalid').forEach(el => {
                        errs.push(el.innerText || el.validationMessage || el.name || 'validation_error');
                    });
                    return errs;
                }""")
                if errors:
                    print(f"[X] Validation errors prevented submission: {errors}")
                    await page.screenshot(path="checksheet_submitted_error.png", full_page=True)
                    raise RuntimeError(f"Submission failed due to validation errors: {errors}")
                else:
                    # Wait up to 10s for possible navigation
                    try:
                        await page.wait_for_url(lambda u: "/create" not in u, timeout=8000)
                    except Exception:
                        pass
            
            print(f"[+] Final submission URL: {page.url}")
            await page.screenshot(path="checksheet_submitted.png", full_page=True)
            return {
                "status": "submitted" if "/create" not in page.url else "failed",
                "mode": mode_used,
                "button_text": button_text,
                "final_url": page.url,
                "inspection_points_count": len(items),
                "diff": diff_data,
                "part_number": part_no,
                "doc_file": doc_path,
                "file_type": file_type,
                "images_count": len(images)
            }
    else:
        print(f"\n[!] REVIEW MODE ({mode_used}): Form is fully populated.")
        print(f"[!] Silakan review dan klik '{button_text}' di browser.")
        return {
            "status": "prepared",
            "mode": mode_used,
            "button_text": button_text,
            "preview_screenshot": screenshot_path,
            "inspection_points_count": len(items),
            "diff": diff_data,
            "part_number": part_no,
            "doc_file": doc_path,
            "file_type": file_type,
            "images_count": len(images)
        }


async def run_automation(
    part_or_excel: str,
    headless: bool = False,
    submit: bool = False,
    doc_number: Optional[str] = None,
    manual_images_dir: Optional[str] = None,
    scan_images: Optional[bool] = None,
    browser_channel: Optional[str] = None
):
    """Main runner for checksheet automation with Playwright."""
    async with async_playwright() as p:
        channel = (browser_channel or os.getenv("BROWSER_CHANNEL", "chromium")).strip().lower()
        if channel in ["edge", "ms-edge"]:
            channel = "msedge"

        browser_obj = None
        context = None
        page = None

        # 1. Check if user configured CDP port
        cdp_port = os.getenv("CDP_PORT", "")
        if cdp_port:
            try:
                browser_obj = await p.chromium.connect_over_cdp(f"http://localhost:{cdp_port}")
                if browser_obj.contexts:
                    context = browser_obj.contexts[0]
                else:
                    context = await browser_obj.new_context()
                page = await context.new_page()
                print(f"[✓] Terhubung ke browser aktif via CDP (Port {cdp_port})!")
            except Exception:
                browser_obj = None
                context = None
                page = None

        # 2. Launch browser
        if not page:
            viewport_cfg = None if not headless else {"width": 1440, "height": 900}

            async def _launch_chromium_testing():
                nonlocal browser_obj, context, page
                print(f"[*] Menjalankan browser Chrome Testing (Chromium) (headless={headless})...")
                browser_obj = await p.chromium.launch(
                    headless=headless,
                    args=["--start-maximized"]
                )
                context = await browser_obj.new_context(viewport=viewport_cfg)
                page = await context.new_page()

            async def _launch_persistent(channel_name: str, profile_dir: str, browser_label: str):
                nonlocal context, page
                os.makedirs(profile_dir, exist_ok=True)
                print(f"[*] Menjalankan {browser_label} (headless={headless}, profil={profile_dir})...")
                context = await p.chromium.launch_persistent_context(
                    user_data_dir=profile_dir,
                    channel=channel_name,
                    headless=headless,
                    args=["--start-maximized", "--no-first-run", "--no-default-browser-check"],
                    viewport=viewport_cfg
                )
                page = context.pages[0] if context.pages else await context.new_page()

            launch_errors: List[str] = []

            async def _try_launch(step_name: str, launcher):
                try:
                    await launcher()
                    return True
                except Exception as e:
                    launch_errors.append(f"{step_name}: {e}")
                    print(f"[!] {step_name} gagal: {e}")
                    return False

            if channel == "chrome":
                ok = await _try_launch(
                    "Google Chrome",
                    lambda: _launch_persistent("chrome", os.path.expanduser("~/.factoryhub_chrome_profile"), "Google Chrome")
                )
                if not ok:
                    await _try_launch("Chrome Testing (Chromium)", _launch_chromium_testing)

            elif channel == "msedge":
                ok = await _try_launch(
                    "Microsoft Edge",
                    lambda: _launch_persistent("msedge", os.path.expanduser("~/.factoryhub_msedge_profile"), "Microsoft Edge")
                )
                if not ok:
                    await _try_launch("Chrome Testing (Chromium)", _launch_chromium_testing)

            else:
                # Default: Chromium / Chrome Testing.
                # Jika browser Playwright belum terpasang, fallback ke browser sistem.
                ok = await _try_launch("Chrome Testing (Chromium)", _launch_chromium_testing)
                if not ok:
                    ok = await _try_launch(
                        "Google Chrome",
                        lambda: _launch_persistent("chrome", os.path.expanduser("~/.factoryhub_chrome_profile"), "Google Chrome")
                    )
                if not ok:
                    await _try_launch(
                        "Microsoft Edge",
                        lambda: _launch_persistent("msedge", os.path.expanduser("~/.factoryhub_msedge_profile"), "Microsoft Edge")
                    )

            if not page:
                err_joined = " | ".join(launch_errors) if launch_errors else "Unknown launch error"
                raise RuntimeError(
                    "Gagal menjalankan browser otomatis. "
                    "Jika ingin memakai mode 'chromium', jalankan: playwright install chromium. "
                    f"Detail: {err_joined}"
                )

        try:
            await login_factoryhub(page)
            result = await fill_checksheet_form(
                page=page,
                part_or_excel=part_or_excel,
                submit=submit,
                custom_doc_no=doc_number,
                manual_images_dir=manual_images_dir,
                scan_images=scan_images
            )

            if result.get("status") == "part_not_registered":
                return result

            if not headless and not submit:
                item_count = result.get("inspection_points_count", "Semua")
                mode = result.get("mode", "CREATE")
                btn = result.get("button_text", "Save Template")
                print("\n" + "="*60)
                print(f" [✓] MODE {mode}: SEMUA FORM DAN {item_count} INSPECTION POINTS TELAH TERISI LENGKAP!")
                print(" [✓] Jendela browser terbuka di layar Anda.")
                print(f" [✓] Silakan periksa/review langsung dan klik '{btn}' sendiri.")
                print(" [*] Sistem akan otomatis mendeteksi saat Anda mengklik simpan di browser.")
                print("="*60)

                start_url = page.url
                submitted_by_user = False

                if sys.stdin.isatty():
                    print("\n[*] Menunggu: Anda dapat klik tombol simpan di browser, ATAU tekan Enter di sini untuk selesai...")

                    async def watch_stdin():
                        loop = asyncio.get_event_loop()
                        await loop.run_in_executor(None, input)

                    stdin_task = asyncio.create_task(watch_stdin())

                    while not stdin_task.done():
                        await asyncio.sleep(0.5)
                        try:
                            if page.is_closed():
                                break
                            curr_url = page.url
                            if curr_url != start_url and ("/create" not in curr_url and "/edit" not in curr_url):
                                print(f"\n[✓] Terdeteksi submit di browser! Halaman beralih ke: {curr_url}")
                                submitted_by_user = True
                                break
                        except Exception:
                            break

                    if not stdin_task.done():
                        stdin_task.cancel()
                else:
                    print("\n[*] Menunggu interaksi Anda di browser (klik tombol simpan atau tutup browser)...")
                    for _ in range(600):  # up to 5 minutes, polls every 500ms
                        await asyncio.sleep(0.5)
                        try:
                            if page.is_closed():
                                print("[*] Browser ditutup oleh pengguna.")
                                break
                            curr_url = page.url
                            if curr_url != start_url and ("/create" not in curr_url and "/edit" not in curr_url):
                                print(f"\n[✓] Terdeteksi submit di browser! Form berhasil disimpan. URL: {curr_url}")
                                submitted_by_user = True
                                try:
                                    await page.wait_for_load_state("networkidle", timeout=4000)
                                except Exception:
                                    pass
                                try:
                                    await page.screenshot(path="checksheet_submitted.png", full_page=True)
                                except Exception:
                                    pass
                                break
                        except Exception:
                            break

                if submitted_by_user:
                    result["status"] = "submitted"
                    result["final_url"] = page.url if not page.is_closed() else ""
                    result["notes"] = f"Template berhasil di-{btn.lower()} oleh user di browser"
                    # Re-log to execution history as submitted
                    logger.log_execution(
                        part_number=result.get("part_number", part_or_excel),
                        doc_file=result.get("doc_file", ""),
                        file_type=result.get("file_type", "excel"),
                        scan_mode=result.get("scan_mode", "auto"),
                        result_action="UPDATE" if mode == "EDIT" else "BARU",
                        points_count=result.get("inspection_points_count", 0),
                        images_count=result.get("images_count", 0),
                        diff_summary=result.get("diff", {}).get("summary", "-") if result.get("diff") else "-",
                        diff_details=result.get("diff"),
                        notes=f"Template berhasil di-{btn.lower()} oleh user di browser"
                    )

            return result
        finally:
            try:
                if context:
                    await context.close()
                if browser_obj:
                    await browser_obj.close()
            except Exception:
                pass
            print("[+] Browser telah ditutup.")
