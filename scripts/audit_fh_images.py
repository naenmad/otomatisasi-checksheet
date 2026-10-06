import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import asyncio
import re
import json
import urllib3
from concurrent.futures import ThreadPoolExecutor
from collections import defaultdict
import requests
from bs4 import BeautifulSoup

urllib3.disable_warnings()

from core.automator import launch_playwright_browser, login_factoryhub
from playwright.async_api import async_playwright

def parse_index_page(html: str):
    soup = BeautifulSoup(html, "html.parser")
    rows = soup.select("table tbody tr")
    items = []
    for tr in rows:
        edit_link = tr.select_one("a[href*='/edit']")
        if not edit_link:
            continue
        href = edit_link.get("href", "")
        m = re.search(r"/checksheet-master/(\d+)/edit", href)
        fh_id = m.group(1) if m else ""
        
        cells = tr.find_all("td")
        part = cells[0].get_text(strip=True) if len(cells) > 0 else ""
        cat = cells[1].get_text(strip=True) if len(cells) > 1 else ""
        desc = cells[2].get_text(strip=True) if len(cells) > 2 else ""
        items_cnt = cells[3].get_text(strip=True) if len(cells) > 3 else ""
        status = cells[5].get_text(strip=True) if len(cells) > 5 else ""
        
        items.append({
            "fh_id": fh_id,
            "part_number": part,
            "category": cat,
            "description": desc,
            "items_count": items_cnt,
            "status": status,
            "edit_url": href
        })
    return items

def check_template_has_image(session: requests.Session, item: dict):
    url = item["edit_url"]
    try:
        r = session.get(url, verify=False, timeout=15.0)
        has_img = ("remove_images" in r.text) or ("storage/checksheets/masters/" in r.text)
        return {
            **item,
            "has_image": has_img
        }
    except Exception as e:
        return {
            **item,
            "has_image": False,
            "error": str(e)
        }

async def audit_factoryhub_images():
    print("[*] Launching browser to obtain authenticated FactoryHub session...")
    async with async_playwright() as p:
        browser, context, page = await launch_playwright_browser(p, headless=True)
        try:
            await login_factoryhub(page)
            cookies = await context.cookies()
            print(f"[✓] Successfully authenticated! Extracted {len(cookies)} cookies.")
        finally:
            await browser.close()
            
    # Setup requests session
    s = requests.Session()
    for c in cookies:
        s.cookies.set(c["name"], c["value"])
        
    print("[*] Fetching all 68 index pages concurrently...")
    index_urls = [
        f"https://factoryhub.summitadyawinsa.co.id/quality/checksheet-master?page={page_num}"
        for page_num in range(1, 69)
    ]
    
    all_templates = []
    with ThreadPoolExecutor(max_workers=15) as executor:
        responses = list(executor.map(lambda u: s.get(u, verify=False, timeout=15.0).text, index_urls))
        for html in responses:
            all_templates.extend(parse_index_page(html))
            
    print(f"[✓] Total templates found across all 68 pages: {len(all_templates)}")
    
    print("[*] Checking image status for all templates concurrently (pool of 25 workers)...")
    with ThreadPoolExecutor(max_workers=25) as executor:
        results = list(executor.map(lambda item: check_template_has_image(s, item), all_templates))
        
    # Analyze results
    with_img = [r for r in results if r["has_image"]]
    without_img = [r for r in results if not r["has_image"]]
    
    print(f"\n==========================================")
    print(f"=== FACTORYHUB IMAGE AUDIT SUMMARY ===")
    print(f"==========================================")
    print(f"Total Templates      : {len(results)}")
    print(f"Templates WITH Image : {len(with_img)} ({len(with_img)/len(results)*100:.1f}%)")
    print(f"Templates WITHOUT Image (GADA GAMBAR): {len(without_img)} ({len(without_img)/len(results)*100:.1f}%)")
    
    by_cat_missing = defaultdict(list)
    for r in without_img:
        cat = r.get("category", "") or "Unknown"
        by_cat_missing[cat].append(r)
        
    print("\nBreakdown of GADA GAMBAR by Category:")
    for cat, items in sorted(by_cat_missing.items(), key=lambda x: -len(x[1])):
        print(f"  {cat:<25}: {len(items)} parts")
        
    # Save output
    output_path = "data/factoryhub_missing_images.json"
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump({
            "total_templates": len(results),
            "with_images_count": len(with_img),
            "without_images_count": len(without_img),
            "by_category_missing": {cat: [i["part_number"] for i in items] for cat, items in by_cat_missing.items()},
            "missing_templates": without_img
        }, f, indent=2)
    print(f"\n[✓] Detailed audit saved to: {output_path}")

if __name__ == "__main__":
    asyncio.run(audit_factoryhub_images())
