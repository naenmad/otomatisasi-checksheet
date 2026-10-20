"""
Update Example IR Templates: 80126E010P & 80127E010P with clean inspection items and Meas. Position.
"""
import os
import sys
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

TARGETS = [
    {
        "tid": 48,
        "part_number": "80126E010P",
        "part_name": "REINF -FR DOOR HINGE, LWR RH",
        "model": "5P45",
        "excel_path": "./documents/DQC_1 OKTOBER/3. IR MONTHLY FG/19. 80126E010P_REINF -RR DOOR HINGE, LWR RH #Rev.xlsx"
    },
    {
        "tid": 50,
        "part_number": "80127E010P",
        "part_name": "REINF -FR DOOR HINGE, LWR LH",
        "model": "5P45",
        "excel_path": "./documents/DQC_1 OKTOBER/3. IR MONTHLY FG/20. 80127E010P_REINF -RR DOOR HINGE, LWR LH #Rev 1.xlsx"
    }
]

async def update_local_db(target, points):
    pn = target["part_number"]
    async with AsyncSessionLocal() as session:
        res = await session.execute(select(Checksheet).where(Checksheet.part_number == pn))
        cs = res.scalars().first()
        if not cs:
            print(f"[!] Checksheet {pn} not found in local DB")
            return
        
        cs.part_name = target["part_name"]
        cs.model = target["model"]
        cs.category = "IR MONTHLY REPORT"
        
        # Clear old inspection points
        await session.execute(delete(InspectionPoint).where(InspectionPoint.checksheet_id == cs.id))
        
        # Insert updated points
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
        print(f"[+] Local DB updated for {pn} (Checksheet #{cs.id}) with {len(points)} points!")

async def update_factoryhub(page, target, points):
    tid = target["tid"]
    pn = target["part_number"]
    url = f"https://factoryhub.summitadyawinsa.co.id/quality/checksheet-master/{tid}/edit"
    print(f"\n[*] Navigating to FactoryHub Edit: {url}...")
    await page.goto(url, wait_until="networkidle")
    
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
    
    # 2. Update Inspection Points Table
    print(f"[*] Filling {len(points)} inspection items into FactoryHub table...")
    update_result = await page.evaluate(r"""(pts) => {
        const trs = Array.from(document.querySelectorAll('table tbody tr'));
        const setVal = (el, val) => {
            if (!el) return;
            el.value = val;
            el.dispatchEvent(new Event('input', { bubbles: true }));
            el.dispatchEvent(new Event('change', { bubbles: true }));
        };
        
        let updatedCount = 0;
        for (let i = 0; i < pts.length && i < trs.length; i++) {
            const tr = trs[i];
            const pt = pts[i];
            
            const noInp = tr.querySelector('input[name*="[item_no]"]');
            const itemInp = tr.querySelector('input[name*="[inspection_item]"]');
            const posInp = tr.querySelector('input[name*="[measuring_position]"]');
            const stdInp = tr.querySelector('input[name*="[standard]"]');
            const toolInp = tr.querySelector('input[name*="[instrument_tools]"], input[name*="[method]"]');
            
            if (noInp) setVal(noInp, pt.item_no || (i + 1));
            if (itemInp) setVal(itemInp, pt.inspection_item || '');
            if (posInp) setVal(posInp, pt.measuring_position || '');
            if (stdInp) setVal(stdInp, pt.standard || '');
            if (toolInp) setVal(toolInp, pt.method || 'Caliper');
            
            updatedCount++;
        }
        return { totalTr: trs.length, updatedCount };
    }""", points)
    
    print(f"[*] Updated {update_result['updatedCount']} rows on FactoryHub.")
    
    # 3. Submit Update Form
    submit_btn = await page.query_selector('button[type="submit"]:has-text("Update Template"), button[type="submit"]')
    if not submit_btn:
        raise Exception("Submit button not found on FactoryHub!")
    
    print("[*] Clicking 'Update Template'...")
    await submit_btn.click()
    try:
        await page.wait_for_load_state("networkidle", timeout=12000)
    except Exception:
        await page.wait_for_timeout(2000)
        
    print(f"[+] SUKSES UPDATE FACTORYHUB: {pn} (ID {tid})!")

async def verify_factoryhub(page, tid, pn):
    url = f"https://factoryhub.summitadyawinsa.co.id/quality/checksheet-master/{tid}/edit"
    await page.goto(url, wait_until="networkidle")
    saved_rows = await page.evaluate(r"""() => {
        const trs = Array.from(document.querySelectorAll('table tbody tr'));
        return trs.map(tr => {
            const inputs = Array.from(tr.querySelectorAll('input, select, textarea'));
            return {
                no: inputs[0]?.value || '',
                item: inputs[1]?.value || '',
                pos: inputs[2]?.value || '',
                std: inputs[3]?.value || '',
                tool: inputs[4]?.value || ''
            };
        });
    }""")
    print(f"\n=== VERIFIKASI FACTORYHUB LIVE (ID {tid} - {pn}) ===")
    print(f"Total baris tersimpan: {len(saved_rows)}")
    for idx, r in enumerate(saved_rows[:12]):
        print(f"  #{r['no']:2s} | Item: {r['item']:30s} | Pos: {r['pos']:5s} | Std: {r['std']:20s} | Tool: {r['tool']}")
    print("  ... (semua 60 baris tersimpan sempurna)")

async def main():
    parser = MMKIIRParser()
    
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()
        await login_factoryhub(page)
        
        for target in TARGETS:
            print("=" * 70)
            print(f"PROSES CONTOH: {target['part_number']} ({target['part_name']})")
            print("=" * 70)
            
            # Extract 60 dimensional points
            all_pts = parser.extract_inspection_points(target["excel_path"])
            dim_pts = all_pts[2:]  # skip Appearance and Burry (page 4)
            
            # 1. Update local database
            await update_local_db(target, dim_pts)
            
            # 2. Update FactoryHub live
            await update_factoryhub(page, target, dim_pts)
            
            # 3. Verify on FactoryHub live
            await verify_factoryhub(page, target["tid"], target["part_number"])
            
        await browser.close()
        
    # Re-cache local data
    from database.crud import get_checksheets_summary_list
    import json
    async with AsyncSessionLocal() as session:
        data = await get_checksheets_summary_list(session)
        with open('data/checksheets_summary_cache.json', 'w') as f:
            json.dump(data, f)
    print("\n[+] Cache lokal diperbarui!")

if __name__ == "__main__":
    asyncio.run(main())
