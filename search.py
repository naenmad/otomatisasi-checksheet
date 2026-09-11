#!/usr/bin/env python3
"""
Fast Batch Part Checker for FactoryHub Checksheet Master
Checks if part numbers exist in Regular Production Part or New Project Part.

Usage:
    python search.py                          # reads from parts.txt (or documents/ fallback)
    python search.py <part1> [part2] ...      # direct part numbers
    python search.py <file.txt>               # reads from custom file
    python search.py --documents              # checks all parts in documents/ folder
"""

import argparse
import asyncio
import csv
import os
import re
import sys
from typing import List, Dict, Any, Optional
from playwright.async_api import async_playwright
from dotenv import load_dotenv

from automator import login_factoryhub, CREATE_URL
from extractor import list_available_parts

load_dotenv()

def clean_code(s: str) -> str:
    """Normalize part number by stripping non-alphanumeric chars and uppercase."""
    return re.sub(r"[^0-9A-Za-z]", "", s or "").upper()

def load_part_numbers(
    args_parts: List[str],
    file_path: Optional[str] = None,
    from_documents: bool = False
) -> List[str]:
    """Load list of part numbers from arguments, file, or documents/."""
    parts = []

    # 1. If explicit part arguments given
    if args_parts:
        for arg in args_parts:
            # If argument happens to be an existing text/csv file
            if os.path.isfile(arg) and (arg.endswith(".txt") or arg.endswith(".csv")):
                with open(arg, "r", encoding="utf-8") as f:
                    for line in f:
                        line = line.strip()
                        if line and not line.startswith("#"):
                            parts.append(line)
            else:
                parts.append(arg.strip())
        return [p for p in parts if p]

    # 2. If --documents flag is set
    if from_documents:
        doc_parts = list_available_parts("documents")
        return [p["part_number"] for p in doc_parts if p.get("part_number")]

    # 3. If specific file is given or default parts.txt exists
    target_file = file_path if file_path else "parts.txt"
    if os.path.isfile(target_file):
        with open(target_file, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#"):
                    parts.append(line)
        return [p for p in parts if p]

    # 4. Fallback: check parts in documents/
    doc_parts = list_available_parts("documents")
    if doc_parts:
        print(f"[*] 'parts.txt' tidak ditemukan. Menggunakan {len(doc_parts)} part dari folder documents/...")
        return [p["part_number"] for p in doc_parts if p.get("part_number")]

    return []

async def fetch_master_options() -> Dict[str, List[Dict[str, str]]]:
    """
    Open FactoryHub /quality/checksheet-master/create once in headless mode
    and extract all Regular and Project part options into memory.
    """
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()
        
        await login_factoryhub(page)
        
        print(f"[*] Mengambil data master part dari: {CREATE_URL}...")
        await page.goto(CREATE_URL, wait_until="networkidle")
        
        data = await page.evaluate("""() => {
            const regSelect = document.getElementById('part_num_select');
            const projSelect = document.getElementById('part_project_id');
            
            const regular = regSelect ? Array.from(regSelect.options).map(o => ({
                value: o.value,
                text: o.text
            })) : [];
            
            const project = projSelect ? Array.from(projSelect.options).map(o => ({
                value: o.value,
                text: o.text,
                dataNum: o.getAttribute('data-num') || ''
            })) : [];
            
            return { regular, project };
        }""")
        
        await browser.close()
        return data

def match_part(
    target_part: str,
    master_data: Dict[str, List[Dict[str, str]]]
) -> Dict[str, Any]:
    """Check whether target_part exists in regular or project parts."""
    target_clean = clean_code(target_part)
    prefix_clean = target_clean[:5] if len(target_clean) >= 5 else target_clean

    similar = []

    # 1. Check Regular Production Parts
    for opt in master_data.get("regular", []):
        v_clean = clean_code(opt["value"])
        t_clean = clean_code(opt["text"])
        
        if v_clean == target_clean or target_clean in v_clean or target_clean in t_clean:
            return {
                "part_number": target_part,
                "status": "ADA",
                "category": "REGULAR",
                "details": opt["text"] or opt["value"],
                "similar": []
            }
        elif prefix_clean and (prefix_clean in v_clean or prefix_clean in t_clean):
            if opt["text"] not in similar:
                similar.append(opt["text"])

    # 2. Check New Project Parts
    for opt in master_data.get("project", []):
        v_clean = clean_code(opt["value"])
        d_clean = clean_code(opt.get("dataNum", ""))
        t_clean = clean_code(opt["text"])
        
        if v_clean == target_clean or d_clean == target_clean or target_clean in d_clean or target_clean in t_clean:
            return {
                "part_number": target_part,
                "status": "ADA",
                "category": "NEW PROJECT",
                "details": opt["text"] or opt.get("dataNum", "") or opt["value"],
                "similar": []
            }
        elif prefix_clean and (prefix_clean in v_clean or prefix_clean in d_clean or prefix_clean in t_clean):
            s_label = opt.get("dataNum") or opt["text"]
            if s_label and s_label not in similar:
                similar.append(s_label)

    # 3. Not Found
    return {
        "part_number": target_part,
        "status": "TIDAK ADA",
        "category": "-",
        "details": "Tidak terdaftar di Regular maupun Project Part",
        "similar": similar[:3]
    }

def print_and_save_results(results: List[Dict[str, Any]]):
    """Format and print ASCII table, save to search_results.txt and search_results.csv."""
    header_sep = "=" * 105
    sub_sep = "-" * 105

    lines = []
    lines.append("\n" + header_sep)
    lines.append("                HASIL PENGECEKAN PART NUMBER DI FACTORYHUB (CREATE TEMPLATE)")
    lines.append(header_sep)
    lines.append(f"{'NO':<4} | {'PART NUMBER':<24} | {'STATUS':<11} | {'KATEGORI':<12} | {'KETERANGAN / NAMA PART'}")
    lines.append(sub_sep)

    total_ada = 0
    total_tidak = 0
    missing_parts = []

    for i, res in enumerate(results, 1):
        status = res["status"]
        if status == "ADA":
            total_ada += 1
            status_str = "[ ADA ]"
        else:
            total_tidak += 1
            status_str = "[TIDAK]"
            missing_parts.append(res["part_number"])

        details = res["details"]
        if res["similar"]:
            details += f" (Mirip: {', '.join(res['similar'])})"

        # Truncate details if excessively long
        if len(details) > 46:
            details = details[:43] + "..."

        lines.append(f"{i:<4} | {res['part_number']:<24} | {status_str:<11} | {res['category']:<12} | {details}")

    lines.append(header_sep)
    lines.append(f" Ringkasan: Total {len(results)} part | {total_ada} ADA | {total_tidak} TIDAK ADA")
    lines.append(header_sep)

    if missing_parts:
        lines.append("\n[!] DAFTAR PART YANG TIDAK ADA (Bisa langsung dicopy untuk diajukan ke Admin):")
        for p in missing_parts:
            lines.append(f"  - {p}")
        lines.append("")

    full_output = "\n".join(lines)
    print(full_output)

    # Save to search_results.txt
    txt_file = "search_results.txt"
    with open(txt_file, "w", encoding="utf-8") as f:
        f.write(full_output + "\n")

    # Save to search_results.csv
    csv_file = "search_results.csv"
    with open(csv_file, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["No", "Part Number", "Status", "Kategori", "Keterangan", "Rekomendasi Mirip"])
        for i, res in enumerate(results, 1):
            writer.writerow([
                i,
                res["part_number"],
                res["status"],
                res["category"],
                res["details"],
                "; ".join(res.get("similar", []))
            ])

    print(f"[✓] Hasil pengecekan telah disimpan ke:")
    print(f"    - Text Report : {os.path.abspath(txt_file)}")
    print(f"    - CSV Report  : {os.path.abspath(csv_file)}\n")

def main():
    parser = argparse.ArgumentParser(
        description="Fast Batch Part Checker for FactoryHub Checksheet Master",
        formatter_class=argparse.RawTextHelpFormatter
    )
    parser.add_argument(
        "parts",
        nargs="*",
        help=(
            "Nomor part atau file teks yang ingin dicek:\n"
            "  Contoh: python search.py 62130-3K6-K001-H1 65750-T86A-K002-H1\n"
            "  Contoh: python search.py parts.txt\n"
        )
    )
    parser.add_argument(
        "-f", "--file",
        type=str,
        default=None,
        help="Path ke file teks yang memuat daftar part (satu baris satu part)"
    )
    parser.add_argument(
        "--documents",
        action="store_true",
        help="Cek semua part number yang ada di folder documents/"
    )

    args = parser.parse_args()

    parts_to_check = load_part_numbers(
        args_parts=args.parts,
        file_path=args.file,
        from_documents=args.documents
    )

    if not parts_to_check:
        print("[!] Error: Tidak ada part number yang dimasukkan untuk dicek.")
        print("\nSaran penggunaan:")
        print("  1. Masukkan part langsung:  ./search.sh 65750-T86A-K002-H1")
        print("  2. Atau buat file parts.txt (satu baris satu part), lalu jalankan: ./search.sh")
        print("  3. Atau cek dari folder documents/: ./search.sh --documents")
        sys.exit(1)

    print(f"\n[*] Memulai pengecekan {len(parts_to_check)} part number...")
    master_data = asyncio.run(fetch_master_options())

    total_reg = len(master_data.get("regular", []))
    total_proj = len(master_data.get("project", []))
    print(f"[+] Berhasil memuat master data: {total_reg} Regular Parts, {total_proj} Project Parts.")
    print(f"[*] Mencocokkan {len(parts_to_check)} part...")

    results = []
    for part in parts_to_check:
        res = match_part(part, master_data)
        results.append(res)

    print_and_save_results(results)

if __name__ == "__main__":
    main()
