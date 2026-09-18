#!/usr/bin/env python3
"""
Fast Batch Part Checker for FactoryHub Checksheet Master
Checks if part numbers exist in Regular Production Part or New Project Part.

Usage:
    python search.py                          # reads from parts.txt (or documents/ fallback)
    python search.py <part1> [part2] ...      # direct part numbers (supports comma-separated)
    python search.py "part1, part2, part3"    # comma-separated string
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
import logger

load_dotenv()


def clean_code(s: str) -> str:
    """Normalize part number by stripping non-alphanumeric chars and uppercase."""
    return re.sub(r"[^0-9A-Za-z]", "", s or "").upper()


def fuzzy_code(s: str) -> str:
    """Normalize part code with O/0 and I/1 visual interchangeability and uppercase alphanumeric."""
    cleaned = clean_code(s)
    return cleaned.replace("O", "0").replace("I", "1")


def parse_comma_separated_parts(raw_parts: List[str]) -> List[str]:
    """Expand list of part arguments, splitting by comma if present."""
    expanded = []
    for item in raw_parts:
        if "," in item:
            sub = [s.strip() for s in item.split(",") if s.strip()]
            expanded.extend(sub)
        else:
            expanded.append(item.strip())
    return [p for p in expanded if p]


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
                            parts.extend([p.strip() for p in line.split(",") if p.strip()])
            else:
                parts.extend([p.strip() for p in arg.split(",") if p.strip()])
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
                    parts.extend([p.strip() for p in line.split(",") if p.strip()])
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
    master_data: Dict[str, List[Dict[str, str]]],
    local_parts_map: Optional[Dict[str, str]] = None,
    catalog_parts: Optional[List[Dict[str, Any]]] = None
) -> Dict[str, Any]:
    """Check whether target_part exists in regular or project parts with smart fuzzy token matching."""
    target_clean = clean_code(target_part)
    target_fuzzy = fuzzy_code(target_part)
    prefix_clean = target_clean[:5] if len(target_clean) >= 5 else target_clean
    prefix_fuzzy = target_fuzzy[:5] if len(target_fuzzy) >= 5 else target_fuzzy

    # Token-level representations for queries like "2120 3m0a j003"
    target_tokens = [fuzzy_code(t) for t in re.split(r"[^0-9A-Za-z]+", target_part) if t.strip()]

    local_status = "-"
    if local_parts_map:
        local_status = local_parts_map.get(target_clean)
        if not local_status:
            for lp_clean, lp_stat in local_parts_map.items():
                lp_fuz = fuzzy_code(lp_clean)
                if lp_fuz == target_fuzzy or (target_fuzzy and target_fuzzy in lp_fuz) or (lp_fuz and lp_fuz in target_fuzzy):
                    local_status = lp_stat
                    break
        if not local_status:
            local_status = "Tidak ada"

    similar = []

    def check_candidate_match(cand_val: str, cand_text: str = "", cand_extra: str = "") -> bool:
        v_clean = clean_code(cand_val)
        v_fuz = fuzzy_code(cand_val)
        t_clean = clean_code(cand_text)
        t_fuz = fuzzy_code(cand_text)
        e_clean = clean_code(cand_extra)
        e_fuz = fuzzy_code(cand_extra)

        # 1. Exact clean match
        if target_clean and (target_clean == v_clean or target_clean == e_clean or target_clean in v_clean or target_clean in t_clean):
            return True

        # 2. Fuzzy match (O <-> 0, I <-> 1)
        if target_fuzzy and (target_fuzzy == v_fuz or target_fuzzy == e_fuz or target_fuzzy in v_fuz or target_fuzzy in t_fuz or target_fuzzy in e_fuz):
            return True

        # 3. Multi-token match (all tokens like "2120", "3M0A", "J003" found in candidate)
        if target_tokens and len(target_tokens) > 1:
            combined = f"{v_fuz} {t_fuz} {e_fuz}"
            if all(tok in combined for tok in target_tokens):
                return True

        # 4. Inverted substring: e.g. candidate is substring of query or vice versa
        if len(v_fuz) >= 6 and v_fuz in target_fuzzy:
            return True

        return False

    # 1. Check Regular Production Parts
    for opt in master_data.get("regular", []):
        if check_candidate_match(opt.get("value", ""), opt.get("text", "")):
            return {
                "part_number": opt.get("value") or target_part,
                "searched_query": target_part,
                "status": "ADA",
                "category": "REGULAR",
                "details": opt.get("text") or opt.get("value", ""),
                "local_doc": local_status,
                "similar": []
            }
        elif prefix_fuzzy and (prefix_fuzzy in fuzzy_code(opt.get("value", "")) or prefix_fuzzy in fuzzy_code(opt.get("text", ""))):
            txt = opt.get("text") or opt.get("value", "")
            if txt and txt not in similar:
                similar.append(txt)

    # 2. Check New Project Parts
    for opt in master_data.get("project", []):
        if check_candidate_match(opt.get("value", ""), opt.get("text", ""), opt.get("dataNum", "")):
            return {
                "part_number": opt.get("dataNum") or opt.get("value") or target_part,
                "searched_query": target_part,
                "status": "ADA",
                "category": "NEW PROJECT",
                "details": opt.get("text") or opt.get("dataNum", "") or opt.get("value", ""),
                "local_doc": local_status,
                "similar": []
            }
        elif prefix_fuzzy and (prefix_fuzzy in fuzzy_code(opt.get("value", "")) or prefix_fuzzy in fuzzy_code(opt.get("dataNum", "")) or prefix_fuzzy in fuzzy_code(opt.get("text", ""))):
            s_label = opt.get("dataNum") or opt.get("text", "")
            if s_label and s_label not in similar:
                similar.append(s_label)

    # 3. Check Catalog Parts (1,188 comprehensive parts including templates)
    if catalog_parts:
        for cat_item in catalog_parts:
            p_num = cat_item.get("part_number", "")
            p_name = cat_item.get("part_name", "")
            p_val = cat_item.get("value", "")
            cat_type = cat_item.get("category", "REGULAR")
            if check_candidate_match(p_num, p_name, p_val):
                dtl = f"{p_num} - {p_name}" if p_name else p_num
                if cat_item.get("has_template"):
                    dtl += " (Template Checksheet Terdaftar)"
                return {
                    "part_number": p_num,
                    "searched_query": target_part,
                    "status": "ADA",
                    "category": cat_type,
                    "details": dtl,
                    "local_doc": local_status,
                    "similar": []
                }
            elif prefix_fuzzy and (prefix_fuzzy in fuzzy_code(p_num) or prefix_fuzzy in fuzzy_code(p_name)):
                s_lbl = f"{p_num} - {p_name}" if p_name else p_num
                if s_lbl not in similar:
                    similar.append(s_lbl)

    # 4. Not Found
    return {
        "part_number": target_part,
        "searched_query": target_part,
        "status": "TIDAK ADA",
        "category": "-",
        "details": "Tidak terdaftar di Regular maupun Project Part",
        "local_doc": local_status,
        "similar": similar[:3]
    }


def print_and_save_results(results: List[Dict[str, Any]], raw_query: str = ""):
    """Format and print ASCII table, save to search_results.txt, search_results.csv, and logs/history.xlsx."""
    header_sep = "=" * 115
    sub_sep = "-" * 115

    lines = []
    lines.append("\n" + header_sep)
    lines.append("                HASIL PENGECEKAN PART NUMBER DI FACTORYHUB (CREATE TEMPLATE)")
    lines.append(header_sep)
    lines.append(f"{'NO':<4} | {'PART NUMBER':<24} | {'STATUS':<11} | {'KATEGORI':<12} | {'DOKUMEN LOKAL':<14} | {'KETERANGAN'}")
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

        if len(details) > 38:
            details = details[:35] + "..."

        local_doc_str = res.get("local_doc", "-")

        lines.append(f"{i:<4} | {res['part_number']:<24} | {status_str:<11} | {res['category']:<12} | {local_doc_str:<14} | {details}")

        # Log each item into centralized logger
        logger.log_search(
            search_query=raw_query or res["part_number"],
            part_number=res["part_number"],
            fh_status=res["status"],
            category=res["category"],
            template_id="-",
            local_doc=local_doc_str,
            notes=details
        )

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
        writer.writerow(["No", "Part Number", "Status", "Kategori", "Dokumen Lokal", "Keterangan", "Rekomendasi Mirip"])
        for i, res in enumerate(results, 1):
            writer.writerow([
                i,
                res["part_number"],
                res["status"],
                res["category"],
                res.get("local_doc", "-"),
                res["details"],
                "; ".join(res.get("similar", []))
            ])

    print(f"[✓] Hasil pengecekan telah dicatat dan disimpan ke:")
    print(f"    - Excel Sheet : logs/history.xlsx (Sheet 'Search History')")
    print(f"    - Text Report : {os.path.abspath(txt_file)}")
    print(f"    - CSV Report  : {os.path.abspath(csv_file)}\n")


def build_local_parts_map() -> Dict[str, str]:
    """Map cleaned part numbers and folder names to their local document status."""
    parts = list_available_parts("documents")
    res = {}
    for p in parts:
        status_label = f"Ya ({p.get('status', 'belum')})"
        c_part = clean_code(p.get("part_number", ""))
        c_folder = clean_code(p.get("folder_name", ""))
        if c_part:
            res[c_part] = status_label
        if c_folder:
            res[c_folder] = status_label
    return res


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
            "  Contoh: python search.py \"510C1W000P, 745C0E040P, 745C0W000P\"\n"
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
        print("  2. Koma terpisah:           ./search.sh \"510C1W000P, 745C0E040P\"")
        print("  3. Atau buat file parts.txt (satu baris satu part), lalu jalankan: ./search.sh")
        print("  4. Atau cek dari folder documents/: ./search.sh --documents")
        sys.exit(1)

    print(f"\n[*] Memulai pengecekan {len(parts_to_check)} part number...")
    master_data = asyncio.run(fetch_master_options())

    total_reg = len(master_data.get("regular", []))
    total_proj = len(master_data.get("project", []))
    print(f"[+] Berhasil memuat master data: {total_reg} Regular Parts, {total_proj} Project Parts.")
    print(f"[*] Mencocokkan {len(parts_to_check)} part...")

    local_map = build_local_parts_map()

    results = []
    for part in parts_to_check:
        res = match_part(part, master_data, local_parts_map=local_map)
        results.append(res)

    raw_query_str = ", ".join(parts_to_check[:3])
    if len(parts_to_check) > 3:
        raw_query_str += f" (+{len(parts_to_check) - 3} lainnya)"

    print_and_save_results(results, raw_query=raw_query_str)


if __name__ == "__main__":
    main()
