"""
Fast Document & Sheet Search Service for QC Checksheets.
Recursively indexes and searches multi-sheet Excel files and documents
in the documents/ directory in milliseconds.
"""
import os
import re
import time
import zipfile
from typing import Dict, Any, List, Optional

DOCUMENTS_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "documents")

_INDEX_CACHE: Optional[List[Dict[str, Any]]] = None
_CACHE_TIMESTAMP: float = 0.0
CACHE_TTL = 300.0  # 5 minutes cache


def normalize_code(s: str) -> str:
    """Normalize code by removing all non-alphanumeric chars and lowercasing."""
    return re.sub(r"[^A-Za-z0-9]", "", str(s or "")).lower()


def build_documents_index(force_refresh: bool = False) -> List[Dict[str, Any]]:
    """
    Build an in-memory index of all Excel files in documents/ including
    all sheet names and cell text strings (< 0.5s for 370+ workbooks).
    """
    global _INDEX_CACHE, _CACHE_TIMESTAMP

    now = time.time()
    if not force_refresh and _INDEX_CACHE is not None and (now - _CACHE_TIMESTAMP < CACHE_TTL):
        return _INDEX_CACHE

    if not os.path.isdir(DOCUMENTS_DIR):
        return []

    index = []
    for root, _, files in os.walk(DOCUMENTS_DIR):
        for f in files:
            if not f.endswith((".xlsx", ".xlsm")) or f.startswith("~$") or f.startswith("."):
                continue

            full_path = os.path.join(root, f)
            rel_path = os.path.relpath(full_path, os.path.dirname(DOCUMENTS_DIR)).replace("\\", "/")

            try:
                with zipfile.ZipFile(full_path, "r") as z:
                    sheet_names = []
                    if "xl/workbook.xml" in z.namelist():
                        wb_xml = z.read("xl/workbook.xml").decode("utf-8", errors="ignore")
                        sheet_names = re.findall(r"<sheet [^>]*name=\"([^\"]+)\"", wb_xml)

                    shared_strings = []
                    if "xl/sharedStrings.xml" in z.namelist():
                        ss_xml = z.read("xl/sharedStrings.xml").decode("utf-8", errors="ignore")
                        shared_strings = re.findall(r"<t(?: [^>]*)?>([^<]+)</t>", ss_xml)

                    index.append({
                        "file_path": rel_path,
                        "filename": f,
                        "folder": os.path.dirname(rel_path),
                        "sheets": sheet_names,
                        "strings": shared_strings
                    })
            except Exception:
                pass

    _INDEX_CACHE = index
    _CACHE_TIMESTAMP = now
    return index


def search_part_in_documents(
    query: str,
    max_results: int = 15,
    force_refresh: bool = False
) -> List[Dict[str, Any]]:
    """
    Find which Excel files and sheets contain the given part number query.
    Supports exact, clean, substring, and reverse token matching.
    """
    if not query or not str(query).strip():
        return []

    q_clean = normalize_code(query)
    if len(q_clean) < 3:
        return []

    index = build_documents_index(force_refresh=force_refresh)
    results = []
    seen_files = set()

    for item in index:
        rel_path = item["file_path"]
        fn = item["filename"]
        fn_clean = normalize_code(fn)

        # 1. Filename match
        if q_clean in fn_clean or (len(q_clean) >= 6 and q_clean[:6] in fn_clean):
            if rel_path not in seen_files:
                seen_files.add(rel_path)
                results.append({
                    "file_path": rel_path,
                    "filename": fn,
                    "folder": item["folder"],
                    "sheet_name": item["sheets"][0] if item["sheets"] else "-",
                    "match_type": "Filename",
                    "matched_text": fn,
                    "confidence": "high" if q_clean in fn_clean else "medium"
                })
                if len(results) >= max_results:
                    break
            continue

        # 2. Sheet name match
        matched_sheet = None
        for s in item["sheets"]:
            s_clean = normalize_code(s)
            if not s_clean:
                continue

            # Exact or substring match (protecting against 1-char sheet names like "1", "A")
            if s_clean == q_clean:
                matched_sheet = (s, "high")
                break
            elif len(s_clean) >= 4 and (s_clean in q_clean or q_clean in s_clean):
                matched_sheet = (s, "high")
                break
            elif len(q_clean) >= 5 and len(s_clean) >= 4 and (q_clean[:5] == s_clean[:5]):
                matched_sheet = (s, "medium")

        if matched_sheet:
            if rel_path not in seen_files:
                seen_files.add(rel_path)
                results.append({
                    "file_path": rel_path,
                    "filename": fn,
                    "folder": item["folder"],
                    "sheet_name": matched_sheet[0],
                    "match_type": "Sheet",
                    "matched_text": matched_sheet[0],
                    "confidence": matched_sheet[1]
                })
                if len(results) >= max_results:
                    break
            continue

        # 3. Cell strings match
        matched_cell_text = None
        for text in item["strings"]:
            t_clean = normalize_code(text)
            if q_clean in t_clean and len(q_clean) >= 4:
                matched_cell_text = text.strip()
                break

        if matched_cell_text:
            if rel_path not in seen_files:
                seen_files.add(rel_path)
                # Try to identify which sheet likely holds this cell
                sheet_guess = item["sheets"][0] if item["sheets"] else "-"
                results.append({
                    "file_path": rel_path,
                    "filename": fn,
                    "folder": item["folder"],
                    "sheet_name": sheet_guess,
                    "match_type": "Cell",
                    "matched_text": matched_cell_text[:80],
                    "confidence": "high"
                })
                if len(results) >= max_results:
                    break

    return results
