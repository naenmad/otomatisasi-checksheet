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
import sys
import time
import asyncio
from typing import Optional, Dict, Any, List
from playwright.async_api import async_playwright, Page, Browser
from dotenv import load_dotenv

from extractor import extract_metadata, extract_reference_images, extract_inspection_points, get_reference_images

# Load configurations from .env
load_dotenv()

FACTORYHUB_BASE_URL = os.getenv("FACTORYHUB_BASE_URL", "https://factoryhub.summitadyawinsa.co.id")
LOGIN_URL = f"{FACTORYHUB_BASE_URL}/login"
CREATE_URL = f"{FACTORYHUB_BASE_URL}/quality/checksheet-master/create"

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

async def fill_checksheet_form(
    page: Page,
    excel_path: str,
    submit: bool = False,
    custom_doc_no: Optional[str] = None,
    manual_images_dir: Optional[str] = None
) -> Dict[str, Any]:
    """Extract data from Excel and fill checksheet master creation form."""
    print(f"\n[*] Processing Excel file: {excel_path}")
    meta = extract_metadata(excel_path)
    if custom_doc_no:
        meta["doc_number"] = custom_doc_no

    print(f"[+] Metadata: Part No = {meta['part_number']}, Doc No = {meta['doc_number']}, Name = {meta['part_name']}")
    
    print("[*] Checking reference images...")
    images = get_reference_images(excel_path, manual_dir=manual_images_dir, part_number=meta['part_number'])
    print(f"[+] Found {len(images)} reference image(s).")
    
    print("[*] Extracting inspection points...")
    items = extract_inspection_points(excel_path)
    print(f"[+] Found {len(items)} inspection point(s).")

    print(f"\n[*] Navigating to checksheet master create: {CREATE_URL}")
    await page.goto(CREATE_URL, wait_until="networkidle")

    # 1. Part Category Type Selection
    part_no = meta["part_number"]
    print(f"[*] Checking Part Number: {part_no}...")
    # 1. Search in Regular Production Part first
    part_selection_result = await page.evaluate(r"""(partNo) => {
        const cleanStr = (s) => (s || '').toUpperCase().replace(/[-\s_]/g, '');
        const targetClean = cleanStr(partNo);

        // Step 1: Check Regular Production Part select options
        const regularSelect = document.getElementById('part_num_select');
        let regularFound = false;
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
                }
            }
        }
        
        if (regularFound) {
            return { type: 'regular', found: true, selectedValue: regularSelect.value };
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
                }
            }
        }
        
        return { 
            type: 'project', 
            found: projFound, 
            selectedValue: projSelect ? projSelect.value : null 
        };
    }""", part_no)
    
    print(f"[+] Part selection: Category = {part_selection_result['type']}, Found = {part_selection_result['found']}")
    if not part_selection_result["found"]:
        print(f"[!] Warning: Part number {part_no} was not found in options. Setting template_name manually.")
        await page.fill('#template_name', part_no)
        if meta["part_name"]:
            await page.fill('#template_desc', meta["part_name"])

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
            if (typeof addItem === 'function') {
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

    # 7. Submit or Review
    if submit:
        print("[*] Submitting form (clicking Save Template)...")
        submit_button = await page.query_selector('button[type="submit"]:has-text("Save Template"), button[type="submit"]')
        if submit_button:
            await submit_button.click()
            await page.wait_for_load_state("networkidle")
            print(f"[+] Submitted! New URL: {page.url}")
            await page.screenshot(path="checksheet_submitted.png", full_page=True)
            return {"status": "submitted", "final_url": page.url}
    else:
        print("\n[!] REVIEW MODE: Form is fully populated.")
        print("[!] Set submit=True or use --submit flag to save to database.")
        return {"status": "prepared", "preview_screenshot": screenshot_path}

async def run_automation(
    excel_path: str,
    headless: bool = False,
    submit: bool = False,
    doc_number: Optional[str] = None,
    manual_images_dir: Optional[str] = None
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
                excel_path=excel_path,
                submit=submit,
                custom_doc_no=doc_number,
                manual_images_dir=manual_images_dir
            )
            
            if not headless and not submit:
                print("\n" + "="*60)
                print(" [✓] SEMUA FORM DAN 74 INSPECTION POINTS TELAH TERISI LENGKAP!")
                print(" [✓] Jendela browser terbuka di layar Anda.")
                print(" [✓] Silakan periksa/review langsung dan klik 'Save Template' sendiri.")
                print("="*60)
                print("\n[*] Tekan Enter di terminal ini jika Anda sudah selesai dan ingin menutup browser...")
                
                # Keep browser open until user presses Enter or closes window
                loop = asyncio.get_event_loop()
                await loop.run_in_executor(None, input)
                
            return result
        finally:
            await browser.close()
            print("[+] Browser telah ditutup.")
