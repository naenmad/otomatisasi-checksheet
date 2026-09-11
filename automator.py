"""
Playwright Automator for Checksheet Master
Automates form filling on FactoryHub:
- Login with employee_id and password
- Category part checking (Regular vs New Project Part)
- Daily checksheet selection
- Doc number setting
- Reference image upload
- Inspection points population
- Optional auto-submission or interactive review mode
"""

import os
import re
import sys
import time
import asyncio
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
        
    await page.wait_for_load_state("networkidle")
    print(f"[+] Post-login URL: {page.url}")

async def find_existing_template(page: Page, part_number: str) -> Optional[Dict[str, str]]:
    """
    Search if a checksheet master template already exists for the given part number.
    Returns dict with templateName and editUrl if found, else None.
    """
    clean_target = re.sub(r"[^0-9A-Za-z]", "", part_number).upper()
    tokens = re.split(r"[-_\s]+", part_number.strip())
    # Choose search query: prefer first 4-8 alphanumeric chars
    search_query = tokens[0] if len(tokens[0]) >= 4 else part_number[:6]

    search_url = f"{INDEX_URL}?search={search_query}"
    print(f"[*] Validasi template di master list: {search_url} (target: {part_number})...")
    await page.goto(search_url, wait_until="networkidle")

    found = await page.evaluate(r"""(target) => {
        const cleanStr = (s) => (s || "").toUpperCase().replace(/[^0-9A-Z]/g, "");
        const rows = Array.from(document.querySelectorAll("table tbody tr"));
        let exactMatch = null;
        let partialMatch = null;

        for (const tr of rows) {
            const tds = tr.querySelectorAll("td");
            if (!tds || tds.length < 2) continue;
            const nameText = tds[0].innerText.trim();
            const nameClean = cleanStr(nameText);
            const editLink = tr.querySelector("a[href*='edit']");
            if (!editLink) continue;

            if (nameClean === target) {
                exactMatch = { templateName: nameText, editUrl: editLink.href };
                break;
            } else if (nameClean.includes(target) || target.includes(nameClean)) {
                if (!partialMatch) {
                    partialMatch = { templateName: nameText, editUrl: editLink.href };
                }
            }
        }
        return exactMatch || partialMatch;
    }""", clean_target)

    return found

async def fill_checksheet_form(
    page: Page,
    part_or_excel: str,
    submit: bool = False,
    custom_doc_no: Optional[str] = None,
    manual_images_dir: Optional[str] = None,
    scan_images: Optional[bool] = None
) -> Dict[str, Any]:
    """Extract data from Excel and fill checksheet master creation/editing form."""
    print(f"\n[*] Resolving part document: {part_or_excel}")
    doc_pkg = resolve_part_document(
        part_or_path=part_or_excel,
        scan_images=scan_images,
        manual_images_dir=manual_images_dir
    )
    excel_path = doc_pkg["excel_path"]
    images = doc_pkg["images"]
    meta = doc_pkg["metadata"]
    if custom_doc_no:
        meta["doc_number"] = custom_doc_no

    print(f"[+] Part Document Resolved:")
    print(f"    - Part Number: {meta['part_number']}")
    print(f"    - Excel File : {os.path.basename(excel_path)}")
    print(f"    - Doc Number : {meta['doc_number']}")
    print(f"    - Part Name  : {meta['part_name']}")
    print(f"    - Images     : {len(images)} file(s)")

    print("[*] Extracting inspection points...")
    items = extract_inspection_points(excel_path)
    print(f"[+] Found {len(items)} inspection point(s).")

    part_no = meta["part_number"]
    existing_template = await find_existing_template(page, part_no)

    if existing_template:
        mode_used = "EDIT"
        edit_url = existing_template["editUrl"]
        print(f"\n[+] DITEMUKAN TEMPLATE: '{existing_template['templateName']}' sudah ada di database.")
        print(f"[+] Membuka mode EDIT: {edit_url}")
        await page.goto(edit_url, wait_until="networkidle")

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
            print("        Silakan daftarkan Part Number ini terlebih dahulu.")
            print("="*65 + "\n")
            
            return {
                "status": "part_not_registered",
                "part_number": part_no,
                "message": f"Part number '{part_no}' belum terdaftar di FactoryHub."
            }

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
        print(f"[*] Setting Doc Number: {doc_no}...")
        await page.fill('input[name="doc_number"]', doc_no)

        # 5. Upload Reference Images
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

        # 6. Populate Inspection Points
        print(f"[*] Populating {len(items)} inspection points into table...")
        populate_stats = await page.evaluate("""(itemsList) => {
            const tbody = document.getElementById('inspection-tbody');
            if (!tbody) return { error: 'Tbody not found' };
            
            // Clear default empty rows
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
        print(f"[+] Populated {populate_stats.get('totalRows', 0)} rows in inspection table.")

    # Save screenshot of prepared form
    screenshot_path = "checksheet_prepared.png"
    await page.screenshot(path=screenshot_path, full_page=True)
    print(f"[+] Screenshot of prepared checksheet saved to: {os.path.abspath(screenshot_path)}")

    button_text = "Update Template" if mode_used == "EDIT" else "Save Template"

    # 7. Submit or Review
    if submit:
        print(f"[*] Submitting form (clicking '{button_text}')...")
        submit_button = await page.query_selector('button[type="submit"]:has-text("Update Template"), button[type="submit"]:has-text("Save Template"), button[type="submit"]')
        if submit_button:
            await submit_button.click()
            await page.wait_for_load_state("networkidle")
            print(f"[+] Submitted! New URL: {page.url}")
            await page.screenshot(path="checksheet_submitted.png", full_page=True)
            return {"status": "submitted", "mode": mode_used, "button_text": button_text, "final_url": page.url, "inspection_points_count": len(items)}
    else:
        print(f"\n[!] REVIEW MODE ({mode_used}): Form is fully populated.")
        print(f"[!] Silakan review dan klik '{button_text}' di browser.")
        return {"status": "prepared", "mode": mode_used, "button_text": button_text, "preview_screenshot": screenshot_path, "inspection_points_count": len(items)}

async def run_automation(
    part_or_excel: str,
    headless: bool = False,
    submit: bool = False,
    doc_number: Optional[str] = None,
    manual_images_dir: Optional[str] = None,
    scan_images: Optional[bool] = None
):
    """Main runner for checksheet automation."""
    async with async_playwright() as p:
        print(f"[*] Menjalankan browser (headless={headless})...")
        browser = await p.chromium.launch(
            headless=headless,
            args=["--start-maximized"]
        )
        context = await browser.new_context(viewport=None if not headless else {"width": 1440, "height": 900})
        page = await context.new_page()

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
                print("="*60)
                print("\n[*] Tekan Enter di terminal ini jika Anda sudah selesai dan ingin menutup browser...")
                
                # Keep browser open until user presses Enter or closes window
                loop = asyncio.get_event_loop()
                await loop.run_in_executor(None, input)
                
            return result
        finally:
            await browser.close()
            print("[+] Browser telah ditutup.")
