"""
Catalog Manager for FactoryHub Master Parts & Checksheet Templates
Stores and indexes FactoryHub parts locally for instant autocomplete,
workspace folder generation, checksheet snippet creation, and gap radar.
"""

import os
import re
import json
import time
from datetime import datetime
from typing import Dict, Any, List, Optional
from extractor import list_available_parts, clear_document_caches

CATALOG_FILE = os.path.join(os.path.dirname(__file__), "data", "factoryhub_catalog.json")

_CATALOG_CACHE: Optional[Dict[str, Any]] = None
_CACHE_MTIME: float = 0.0


def clean_code(s: str) -> str:
    """Normalize part number by stripping non-alphanumeric chars and uppercase."""
    return re.sub(r"[^0-9A-Za-z]", "", s or "").upper()


def fuzzy_code(s: str) -> str:
    """Normalize part code with O/0 and I/1 visual interchangeability and uppercase alphanumeric."""
    cleaned = clean_code(s)
    return cleaned.replace("O", "0").replace("I", "1")


def load_catalog(force_reload: bool = False) -> Dict[str, Any]:
    """Load the local FactoryHub catalog from JSON with caching."""
    global _CATALOG_CACHE, _CACHE_MTIME

    if not os.path.exists(CATALOG_FILE):
        return {
            "synced_at": None,
            "stats": {
                "total_parts": 0,
                "total_regular": 0,
                "total_project": 0,
                "total_templates": 0
            },
            "parts": [],
            "templates": []
        }

    try:
        mtime = os.path.getmtime(CATALOG_FILE)
        if not force_reload and _CATALOG_CACHE is not None and mtime == _CACHE_MTIME:
            return _CATALOG_CACHE

        with open(CATALOG_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
            _CATALOG_CACHE = data
            _CACHE_MTIME = mtime
            return data
    except Exception as e:
        print(f"[!] Error loading catalog: {e}")
        return {
            "synced_at": None,
            "stats": {"total_parts": 0, "total_regular": 0, "total_project": 0, "total_templates": 0},
            "parts": [],
            "templates": []
        }


def save_catalog(catalog_data: Dict[str, Any]) -> None:
    """Save the catalog data to disk."""
    global _CATALOG_CACHE, _CACHE_MTIME
    os.makedirs(os.path.dirname(CATALOG_FILE), exist_ok=True)
    with open(CATALOG_FILE, "w", encoding="utf-8") as f:
        json.dump(catalog_data, f, indent=2, ensure_ascii=False)
    _CATALOG_CACHE = catalog_data
    _CACHE_MTIME = os.path.getmtime(CATALOG_FILE)


def get_local_documents_map(documents_dir: str = "documents") -> Dict[str, Dict[str, Any]]:
    """Scan local documents folder and index by clean part number."""
    doc_map = {}
    parts = list_available_parts(documents_dir)
    for p in parts:
        p_num = p.get("part_number") or ""
        folder = p.get("folder_name") or ""
        clean_p = clean_code(p_num)
        clean_f = clean_code(folder)

        doc_info = {
            "part_number": p_num,
            "folder": folder,
            "status": p.get("status", "belum"),
            "folder_path": p.get("folder_path", "")
        }
        if clean_p:
            doc_map[clean_p] = doc_info
        if clean_f and clean_f != clean_p:
            doc_map[clean_f] = doc_info

    return doc_map


def search_catalog(
    query: str = "",
    category: Optional[str] = None,
    limit: int = 50,
    only_gap: bool = False
) -> List[Dict[str, Any]]:
    """
    Ultra-fast in-memory search across FactoryHub master parts.
    Includes local document presence & checksheet template status.
    Supports fuzzy matching (O/0 and I/1) and multi-token searches (e.g. '2120 3m0a j003').
    """
    catalog = load_catalog()
    parts = catalog.get("parts", [])
    if not parts:
        return []

    q_clean = clean_code(query)
    q_fuzzy = fuzzy_code(query)
    q_lower = (query or "").strip().lower()
    q_tokens = [fuzzy_code(t) for t in re.split(r"[^0-9A-Za-z]+", query) if t.strip()]

    local_map = get_local_documents_map()
    results = []

    for item in parts:
        p_num = item.get("part_number", "")
        p_name = item.get("part_name", "")
        cat = item.get("category", "")
        clean_p = item.get("clean_number") or clean_code(p_num)
        fuzzy_p = fuzzy_code(clean_p)
        fuzzy_name = fuzzy_code(p_name)

        # Filter category if specified
        if category and category.upper() not in ["ALL", "SEMUA"]:
            if cat.upper() != category.upper():
                continue

        # Check local document status
        local_info = local_map.get(clean_p)
        if not local_info:
            for lk, lv in local_map.items():
                if fuzzy_code(lk) == fuzzy_p:
                    local_info = lv
                    break
        local_status = local_info["status"] if local_info else "belum_ada"
        has_local = local_info is not None

        # Filter gap if requested (only parts that don't have local folders)
        if only_gap and has_local:
            continue

        score = 0
        if not q_clean and not q_lower:
            # No query: return all (up to limit)
            score = 1
        else:
            if clean_p == q_clean:
                score = 100
            elif fuzzy_p == q_fuzzy:
                score = 95
            elif clean_p.startswith(q_clean):
                score = 85
            elif fuzzy_p.startswith(q_fuzzy):
                score = 80
            elif q_clean in clean_p:
                score = 75
            elif q_fuzzy in fuzzy_p:
                score = 70
            elif q_tokens and all(tok in fuzzy_p or tok in fuzzy_name for tok in q_tokens):
                score = 65
            elif q_lower in p_name.lower():
                score = 50
            elif q_lower in p_num.lower():
                score = 40
            else:
                continue

        result_entry = dict(item)
        result_entry["local_doc"] = local_info
        result_entry["local_status"] = local_status
        result_entry["has_local"] = has_local
        result_entry["search_score"] = score
        results.append(result_entry)

    # Sort by score descending, then alphabetically by part number
    results.sort(key=lambda x: (-x["search_score"], x.get("part_number", "")))
    return results[:limit]


def get_catalog_stats() -> Dict[str, Any]:
    """Return comprehensive catalog and workspace statistics."""
    catalog = load_catalog()
    parts = catalog.get("parts", [])
    templates = catalog.get("templates", [])
    local_map = get_local_documents_map()

    total_parts = len(parts)
    total_regular = sum(1 for p in parts if p.get("category") == "REGULAR")
    total_project = sum(1 for p in parts if p.get("category") == "NEW PROJECT")
    total_templates = len(templates)

    # Local workspace stats
    local_parts_clean = set(local_map.keys())
    parts_with_local = sum(1 for p in parts if (p.get("clean_number") or clean_code(p.get("part_number", ""))) in local_parts_clean)
    parts_with_template = sum(1 for p in parts if p.get("has_template"))
    gap_count = total_parts - parts_with_local

    return {
        "synced_at": catalog.get("synced_at"),
        "total_parts": total_parts,
        "total_regular": total_regular,
        "total_project": total_project,
        "total_templates": total_templates,
        "parts_with_local_doc": parts_with_local,
        "parts_with_template": parts_with_template,
        "gap_count": gap_count,
        "has_catalog": total_parts > 0
    }


def create_folder_from_catalog(part_number: str, target_status: str = "belum") -> Dict[str, Any]:
    """
    Create a folder in documents/<target_status>/<part_number>
    and populate it with an official info.json metadata snippet.
    """
    clean_p = clean_code(part_number)
    if not clean_p:
        raise ValueError("Part number tidak valid")

    catalog = load_catalog()
    part_info = None
    for p in catalog.get("parts", []):
        if (p.get("clean_number") or clean_code(p.get("part_number", ""))) == clean_p:
            part_info = p
            break

    folder_name = part_info.get("part_number", part_number) if part_info else part_number
    # Sanitize folder name
    safe_folder_name = re.sub(r'[\\/:*?"<>|]', '_', folder_name.strip())

    if target_status not in ["belum", "tidak_ada_part", "done"]:
        target_status = "belum"

    target_dir = os.path.join("documents", target_status, safe_folder_name)
    os.makedirs(target_dir, exist_ok=True)

    # Generate info.json snippet
    info_path = os.path.join(target_dir, "info.json")
    snippet_data = {
        "part_number": folder_name,
        "part_name": part_info.get("part_name", "") if part_info else "",
        "category": part_info.get("category", "REGULAR") if part_info else "REGULAR",
        "factoryhub_value": part_info.get("value", "") if part_info else "",
        "has_template_in_factoryhub": part_info.get("has_template", False) if part_info else False,
        "created_at": datetime.now().isoformat(),
        "notes": "Dibuat otomatis dari Katalog Master FactoryHub",
        "template_details": part_info.get("template_info") if part_info else None
    }

    with open(info_path, "w", encoding="utf-8") as f:
        json.dump(snippet_data, f, indent=2, ensure_ascii=False)

    clear_document_caches()

    return {
        "success": True,
        "folder_name": safe_folder_name,
        "status": target_status,
        "folder_path": target_dir,
        "snippet_path": info_path,
        "metadata": snippet_data
    }
