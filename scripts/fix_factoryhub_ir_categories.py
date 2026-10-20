"""
Auto-fix misclassified IR checksheets on FactoryHub:
Moves 58 IR Monthly and IR Child Part templates from
'FINAL INSPECTION ASSY', 'INCOMMING STD PART', and 'SSW'
to 'IR MONTHLY REPORT' (and sets format to 'monthly_mmki').
"""
import os
import sys
import asyncio
from playwright.async_api import async_playwright

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from core.automator import login_factoryhub
from database.connection import AsyncSessionLocal
from database.models import Checksheet
from sqlalchemy import select, update
from database.crud import get_checksheets_summary_list
import json

async def run_fix(dry_run: bool = False, limit: int = None):
    print("=" * 70)
    print("  FACTORYHUB IR CATEGORY AUTO-FIX TOOL")
    print(f"  Mode: {'DRY RUN (Simulasi)' if dry_run else 'LIVE UPDATE'}")
    print("=" * 70)

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()
        await login_factoryhub(page)

        print("[*] Mengambil daftar 746 template dari FactoryHub...")
        all_templates = []
        for page_num in range(1, 76):
            await page.goto(f'https://factoryhub.summitadyawinsa.co.id/quality/checksheet-master?category=all&page={page_num}', wait_until='networkidle')
            rows = await page.evaluate('''() => {
                const trs = document.querySelectorAll('table tbody tr');
                return Array.from(trs).map(tr => {
                    const editA = tr.querySelector('a[href*="/edit"]');
                    return {
                        part: tr.cells[0] ? tr.cells[0].innerText.trim() : '',
                        cat: tr.cells[1] ? tr.cells[1].innerText.trim() : '',
                        desc: tr.cells[2] ? tr.cells[2].innerText.trim() : '',
                        doc: tr.cells[4] ? tr.cells[4].innerText.replace(/\\s+/g, ' ').trim() : '',
                        editUrl: editA ? editA.href : ''
                    };
                }).filter(r => r.part && r.editUrl);
            }''')
            all_templates.extend(rows)
            if not rows:
                break

        # Filter items that should be IR MONTHLY REPORT
        misclassified = []
        for t in all_templates:
            doc_u = t['doc'].upper()
            cat_u = t['cat'].upper()
            is_ir = any(k in doc_u for k in ['IR MONTHLY', 'IR CHILD', 'IR REPORT']) or doc_u.startswith('IR ')
            if is_ir and cat_u != 'IR MONTHLY REPORT':
                misclassified.append(t)

        print(f"[+] Ditemukan {len(misclassified)} template IR yang salah kategori di FactoryHub.")
        if limit:
            misclassified = misclassified[:limit]
            print(f"[*] Dibatasi hanya {limit} item untuk proses ini.")

        if dry_run:
            print("\n[DRY RUN] Daftar template yang akan diperbarui:")
            for idx, item in enumerate(misclassified, 1):
                print(f"  {idx:2d}. {item['part']:<18} | Saat ini: {item['cat']:<22} -> Target: IR MONTHLY REPORT ({item['doc']})")
            await browser.close()
            return

        print("\n[*] Memulai update live ke FactoryHub...")
        success_count = 0
        fail_count = 0

        for idx, item in enumerate(misclassified, 1):
            pn = item['part']
            edit_url = item['editUrl']
            old_cat = item['cat']
            print(f"\n[{idx}/{len(misclassified)}] Memproses Part: {pn} (Kategori Lama: {old_cat})...")

            try:
                await page.goto(edit_url, wait_until='networkidle')

                # Update Category & Format in edit form
                updated = await page.evaluate('''() => {
                    const catSel = document.querySelector('select[name="category"]');
                    if (!catSel) return false;

                    // 1. Select IR MONTHLY REPORT
                    for (let i = 0; i < catSel.options.length; i++) {
                        if (catSel.options[i].value === 'IR MONTHLY REPORT' || catSel.options[i].text.includes('IR MONTHLY')) {
                            catSel.selectedIndex = i;
                            catSel.dispatchEvent(new Event('input', { bubbles: true }));
                            catSel.dispatchEvent(new Event('change', { bubbles: true }));
                            break;
                        }
                    }

                    // 2. Select format monthly_mmki if format selector exists
                    const fmtSel = document.querySelector('select[name="format"]');
                    if (fmtSel) {
                        fmtSel.value = 'monthly_mmki';
                        fmtSel.dispatchEvent(new Event('input', { bubbles: true }));
                        fmtSel.dispatchEvent(new Event('change', { bubbles: true }));
                    }

                    return true;
                }''')

                if not updated:
                    print(f"  [!] Gagal menemukan select category pada form {edit_url}")
                    fail_count += 1
                    continue

                # Submit form
                submit_btn = await page.query_selector('button[type="submit"]:has-text("Update Template"), button[type="submit"]:has-text("Save"), button[type="submit"]')
                if submit_btn:
                    await submit_btn.click()
                    try:
                        await page.wait_for_load_state('networkidle', timeout=10000)
                    except Exception:
                        await page.wait_for_timeout(2000)
                    print(f"  [+] Sukses update kategori '{pn}' -> IR MONTHLY REPORT")
                    success_count += 1

                    # Sync local DB
                    try:
                        async with AsyncSessionLocal() as db_session:
                            stmt = (
                                update(Checksheet)
                                .where(Checksheet.part_number == pn)
                                .values(category="IR MONTHLY REPORT")
                            )
                            await db_session.execute(stmt)
                            await db_session.commit()
                    except Exception as db_e:
                        print(f"  [!] Note: Gagal sync DB lokal untuk {pn}: {db_e}")
                else:
                    print(f"  [!] Tombol submit tidak ditemukan.")
                    fail_count += 1

            except Exception as e:
                print(f"  [!] Error saat update {pn}: {e}")
                fail_count += 1

        print("\n" + "=" * 70)
        print(f"  SELESAI! Sukses: {success_count} | Gagal: {fail_count}")
        print("=" * 70)

        # Refresh local summary cache
        try:
            print("[*] Merefresh cache ringkasan lokal...")
            async with AsyncSessionLocal() as db_session:
                summary = await get_checksheets_summary_list(db_session)
                cache_path = os.path.join(PROJECT_ROOT, "data", "checksheets_summary_cache.json")
                with open(cache_path, "w", encoding="utf-8") as f:
                    json.dump(summary, f, ensure_ascii=False)
            print("[+] Cache ringkasan lokal berhasil diperbarui!")
        except Exception as ce:
            print(f"[!] Warning: Gagal refresh cache lokal: {ce}")

        await browser.close()

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true", help="Simulasi tanpa update")
    parser.add_argument("--limit", type=int, default=None, help="Batasi jumlah part")
    args = parser.parse_args()

    asyncio.run(run_fix(dry_run=args.dry_run, limit=args.limit))
