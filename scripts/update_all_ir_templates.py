"""
Batch Updater: Update all IR Checksheet Master Templates to 'IR MONTHLY REPORT' & 'monthly_mmki',
cleaning inspection item names and populating the 'measuring_position' (Meas. Position) column.
"""
import os
import sys
import re
import asyncio
from playwright.async_api import async_playwright
from sqlalchemy import select, delete, update

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from core.automator import login_factoryhub
from database.connection import AsyncSessionLocal
from database.models import Checksheet, InspectionPoint
from parsers.mmki_ir import MMKIIRParser

ALREADY_DONE_TIDS = set()

async def get_all_ir_targets():
    parser = MMKIIRParser()
    
    # Map excel files by part number
    excel_files = {}
    for root_dir in ['documents/DQC_1 OKTOBER/3. IR MONTHLY FG', 'documents/DQC_1 OKTOBER/2. IR CHILD PART']:
        if os.path.exists(root_dir):
            for f in os.listdir(root_dir):
                if f.endswith('.xlsx'):
                    m = re.search(r'([0-9A-Za-z]{9,12})', f)
                    if m:
                        excel_files[m.group(1).upper()] = os.path.join(root_dir, f)

    targets = []
    async with AsyncSessionLocal() as session:
        res = await session.execute(
            select(Checksheet)
            .where(Checksheet.category == 'IR MONTHLY REPORT')
            .order_by(Checksheet.id)
        )
        cs_list = res.scalars().all()
        
        seen_tids = set()
        for cs in cs_list:
            m = re.search(r'/checksheet-master/(\d+)', cs.factoryhub_url or '')
            if not m:
                continue
            tid = int(m.group(1))
            if tid in seen_tids:
                continue
            seen_tids.add(tid)
            
            pn = cs.part_number.upper().strip()
            # find matching excel
            fpath = excel_files.get(pn)
            if not fpath:
                for f_pn, p in excel_files.items():
                    if pn in f_pn or f_pn in pn:
                        fpath = p
                        break
                        
            targets.append({
                "tid": tid,
                "part_number": pn,
                "part_name": cs.part_name or "",
                "model": cs.model or "5P45",
                "excel_path": fpath
            })
            
    return targets

async def update_local_db(target, points):
    pn = target["part_number"]
    async with AsyncSessionLocal() as session:
        res = await session.execute(select(Checksheet).where(Checksheet.part_number == pn))
        cs_records = res.scalars().all()
        if not cs_records:
            return
            
        for cs in cs_records:
            cs.category = "IR MONTHLY REPORT"
            cs.format = "monthly_mmki"
            if target.get("part_name"):
                cs.part_name = target["part_name"]
            if target.get("model"):
                cs.model = target["model"]
                
            # Clear old points & insert clean points
            await session.execute(delete(InspectionPoint).where(InspectionPoint.checksheet_id == cs.id))
            for idx, pt in enumerate(points):
                ip = InspectionPoint(
                    checksheet_id=cs.id,
                    item_no=str(pt.get("item_no") or (idx + 1)),
                    inspection_item=pt.get("inspection_item") or "",
                    measuring_position=pt.get("measuring_position") or "",
                    standard=pt.get("standard") or "",
                    method=pt.get("method") or "Caliper",
                    master_data=pt.get("master_data") or "",
                    order_index=idx
                )
                session.add(ip)
        await session.commit()

async def update_factoryhub_template(page, target, points):
    tid = target["tid"]
    pn = target["part_number"]
    url = f"https://factoryhub.summitadyawinsa.co.id/quality/checksheet-master/{tid}/edit"
    
    await page.goto(url, wait_until="domcontentloaded")
    await page.wait_for_selector("#inspection-tbody", timeout=15000)
    
    # 1. Update Category & Format
    await page.evaluate(r"""() => {
        const catSel = document.querySelector('select[name="category"]');
        if (catSel) {
            for (let i = 0; i < catSel.options.length; i++) {
                if (catSel.options[i].value === 'IR MONTHLY REPORT') {
                    catSel.selectedIndex = i;
                    catSel.dispatchEvent(new Event('change', { bubbles: true }));
                    break;
                }
            }
        }
        const fmtSel = document.querySelector('select[name="format"]');
        if (fmtSel) {
            fmtSel.value = 'monthly_mmki';
            fmtSel.dispatchEvent(new Event('change', { bubbles: true }));
        }
    }""")
    
    # 2. Synchronize row count and update items
    res = await page.evaluate(r"""(pts) => {
        const tbody = document.getElementById('inspection-tbody');
        let trs = Array.from(tbody.querySelectorAll('tr'));
        const initialCount = trs.length;
        
        // Remove excess rows
        while (trs.length > pts.length) {
            const last = trs.pop();
            last.remove();
        }
        
        // Add missing rows
        while (trs.length < pts.length) {
            if (typeof window.addNewRow === 'function') {
                window.addNewRow();
            }
            trs = Array.from(tbody.querySelectorAll('tr'));
        }
        
        const setVal = (el, val) => {
            if (!el) return;
            el.value = val;
            el.dispatchEvent(new Event('input', { bubbles: true }));
            el.dispatchEvent(new Event('change', { bubbles: true }));
        };
        
        let count = 0;
        for (let i = 0; i < pts.length && i < trs.length; i++) {
            const tr = trs[i];
            const pt = pts[i];
            
            let noInp = tr.querySelector('input[name*="[item_no]"]');
            let itemInp = tr.querySelector('input[name*="[inspection_item]"]');
            let posInp = tr.querySelector('input[name*="[measuring_position]"]');
            let stdInp = tr.querySelector('input[name*="[standard]"]');
            let toolInp = tr.querySelector('input[name*="[instrument_tools]"], input[name*="[method]"]');
            
            if (!posInp && itemInp) {
                const itemTd = itemInp.closest('td');
                if (itemTd) {
                    const newTd = document.createElement('td');
                    newTd.className = 'px-2 py-2';
                    newTd.innerHTML = `<input type="text" name="items[${i}][measuring_position]" class="w-full text-xs p-1 rounded border-gray-300" placeholder="Position">`;
                    itemTd.after(newTd);
                    posInp = newTd.querySelector('input');
                }
            }
            
            if (noInp) {
                noInp.name = `items[${i}][item_no]`;
                setVal(noInp, pt.item_no || (i + 1));
            }
            if (itemInp) {
                itemInp.name = `items[${i}][inspection_item]`;
                setVal(itemInp, pt.inspection_item || '');
            }
            if (posInp) {
                posInp.name = `items[${i}][measuring_position]`;
                setVal(posInp, pt.measuring_position || '');
            }
            if (stdInp) {
                stdInp.name = `items[${i}][standard]`;
                setVal(stdInp, pt.standard || '');
            }
            if (toolInp) {
                toolInp.name = `items[${i}][instrument_tools]`;
                setVal(toolInp, pt.method || 'Caliper');
            }
            
            count++;
        }
        return { initialCount, finalCount: trs.length, updated: count };
    }""", points)
    
    # 3. Submit Update Form
    submit_btn = await page.query_selector('button[type="submit"]:has-text("Update Template"), button[type="submit"]')
    if not submit_btn:
        raise Exception(f"Submit button not found for TID {tid}")
        
    await submit_btn.click()
    try:
        await page.wait_for_load_state("networkidle", timeout=10000)
    except Exception:
        await page.wait_for_timeout(2000)
        
    return res

async def main():
    print("=" * 70)
    print("  BATCH STANDARDIZATION & UPLOAD: ALL IR TEMPLATES TO FACTORYHUB")
    print("  Format: monthly_mmki | Category: IR MONTHLY REPORT | Meas. Position")
    print("=" * 70)
    
    all_targets = await get_all_ir_targets()
    to_process = [t for t in all_targets if t["tid"] not in ALREADY_DONE_TIDS]
    
    print(f"Total IR Templates: {len(all_targets)}")
    print(f"Already done: {len(ALREADY_DONE_TIDS)} (TID 48, 50)")
    print(f"To update: {len(to_process)}")
    
    parser = MMKIIRParser()
    success = 0
    failed = 0
    
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()
        await login_factoryhub(page)
        
        for idx, target in enumerate(to_process):
            tid = target["tid"]
            pn = target["part_number"]
            fpath = target["excel_path"]
            prefix = f"[{idx+1}/{len(to_process)}] TID {tid} ({pn})"
            
            if not fpath or not os.path.exists(fpath):
                print(f"  [!] {prefix}: Excel file not found, skipping...")
                failed += 1
                continue
                
            try:
                # 1. Parse Excel points
                all_pts = parser.extract_inspection_points(fpath)
                dim_pts = all_pts[2:] if len(all_pts) > 2 and all_pts[0].get("inspection_item") == "Appearance" else all_pts
                
                # 2. Update local DB
                await update_local_db(target, dim_pts)
                
                # 3. Update FactoryHub live
                res = await update_factoryhub_template(page, target, dim_pts)
                print(f"  [+] {prefix}: OK! {res.get('initialCount')} -> {res.get('finalCount')} rows, Cat=IR MONTHLY REPORT, Fmt=monthly_mmki", flush=True)
                success += 1
                
            except Exception as e:
                print(f"  [-] {prefix}: FAILED -> {e}", flush=True)
                failed += 1
                
        await browser.close()
        
    print("\n" + "=" * 70)
    print(f"  SELESAI! Sukses: {success} | Gagal: {failed} | Total: {len(to_process)}")
    print("=" * 70)
    
    # Refresh cache
    from database.crud import get_checksheets_summary_list
    import json
    async with AsyncSessionLocal() as session:
        data = await get_checksheets_summary_list(session)
        with open('data/checksheets_summary_cache.json', 'w') as f:
            json.dump(data, f)
    print("[+] Cache lokal diperbarui!")

if __name__ == "__main__":
    asyncio.run(main())
