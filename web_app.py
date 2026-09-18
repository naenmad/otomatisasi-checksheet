"""
Web Dashboard Backend for Checksheet Master Automation
Features:
- Document Management across 3 categories: belum, tidak_ada_part, done
- Automatic document status migration upon run completion
- In-Web Excel Logbook reader (both Execution History & Search History sheets)
- On-Demand Diff Comparison Engine
- FactoryHub Reverse Proxy for In-App iframe embedding
"""

import os
import re
import shutil
import json
import asyncio
from typing import List, Dict, Any, Optional
import subprocess
import threading
from fastapi import FastAPI, HTTPException, Request, Response, Query, UploadFile, File, Form
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, JSONResponse, HTMLResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import openpyxl
import httpx
try:
    from PIL import Image
except ImportError:
    Image = None

from extractor import (
    list_available_parts,
    resolve_part_document,
    extract_reference_images,
    extract_inspection_points,
    extract_metadata,
    get_cached_image_info,
    clear_document_caches,
    get_documents_fingerprint
)

_DOCUMENTS_CACHE: Dict[str, Any] = {"fingerprint": "", "data": None}
_DOCUMENTS_LOCK = threading.Lock()
from automator import (
    run_automation,
    compute_template_diff,
    find_existing_template,
    login_factoryhub,
    INDEX_URL,
    FACTORYHUB_BASE_URL
)
from duplicate import duplicate_part
from server_duplicator import duplicate_server_to_server

from search import (
    fetch_master_options,
    match_part,
    build_local_parts_map,
    parse_comma_separated_parts
)
from datetime import datetime
from compress_webp import get_image_stats, convert_images_to_webp
from catalog_manager import (
    load_catalog,
    save_catalog,
    search_catalog,
    get_catalog_stats,
    create_folder_from_catalog,
    clean_code as clean_part_code
)
from catalog_syncer import sync_factoryhub_catalog
import logger

app = FastAPI(title="Summit Checksheet Master Automation Dashboard")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
def prewarm_cache_on_startup():
    # Pre-warm documents in a background thread so the server starts in milliseconds and immediately serves requests
    threading.Thread(target=get_documents, kwargs={"force": False}, daemon=True).start()


@app.get("/favicon.ico", include_in_schema=False)
async def favicon():
    return Response(status_code=204)


CACHED_MASTER_OPTIONS: Optional[Dict[str, List[Dict[str, str]]]] = None


class RunRequest(BaseModel):
    part: str
    scan_mode: Optional[str] = "auto"  # "auto", "scan", "folder"
    submit: bool = False
    headless: bool = False
    doc_number: Optional[str] = None
    browser_channel: Optional[str] = "chromium"  # "chromium" (Chrome Testing), "chrome", "msedge"


class SearchRequest(BaseModel):
    query: str


class MoveDocRequest(BaseModel):
    folder_name: str
    from_status: str  # "belum", "tidak_ada_part", "done"
    to_status: str    # "belum", "tidak_ada_part", "done"


class CheckServerAvailabilityRequest(BaseModel):
    folder_name: Optional[str] = None
    live: bool = True



class DiffRequest(BaseModel):
    part: str


class DuplicatePartRequest(BaseModel):
    source_part: str
    target_part: str
    target_status: Optional[str] = "belum"
    rename_files: Optional[bool] = True


class ServerDuplicateRequest(BaseModel):
    source_part: str
    target_part: str
    target_status: Optional[str] = "belum"
    submit: Optional[bool] = False
    headless: Optional[bool] = False
    browser_channel: Optional[str] = "chromium"




class CompressImagesRequest(BaseModel):
    target: Optional[str] = "all"  # "all", "documents", or "extracted_images"
    quality: Optional[int] = 82
    max_dimension: Optional[int] = 1920
    delete_original: Optional[bool] = True


def get_part_preview_images(part_or_folder: str, scan_mode: Optional[str] = None) -> Dict[str, Any]:
    """
    Returns rich preview images with dimensions, source badge, and resolution.
    Always provides preview whether from local folder screenshots or extracted document sketches.
    Reuses existing cached/extracted images to ensure instantaneous dashboard loading.
    """
    scan_arg = None
    if scan_mode in ("scan", "extract"):
        scan_arg = True
    elif scan_mode == "folder":
        scan_arg = False

    valid_exts = (".png", ".jpg", ".jpeg", ".webp")

    # Fast path: when scanning is not requested and part_or_folder is an existing folder
    if scan_arg is False and os.path.isdir(part_or_folder):
        folder_path = os.path.abspath(part_or_folder)
        folder_name = os.path.basename(folder_path)
        part_no = folder_name
        status = "belum"
        if "done" in folder_path:
            status = "done"
        elif "tidak_ada_part" in folder_path:
            status = "tidak_ada_part"

        local_imgs = [
            os.path.abspath(os.path.join(folder_path, f))
            for f in sorted(os.listdir(folder_path))
            if f.lower().endswith(valid_exts)
        ]
        sub_img = os.path.join(folder_path, "images")
        if os.path.isdir(sub_img):
            local_imgs.extend([
                os.path.abspath(os.path.join(sub_img, f))
                for f in sorted(os.listdir(sub_img))
                if f.lower().endswith(valid_exts)
            ])
        images = [img for img in local_imgs if not get_cached_image_info(img).get("is_logo", False)]
        if not images:
            clean_sub = re.sub(r"[^0-9A-Za-z_-]", "_", folder_name)
            for sub_name in [folder_name, clean_sub]:
                ext_dir = os.path.join("extracted_images", sub_name)
                if os.path.isdir(ext_dir):
                    found = [
                        os.path.abspath(os.path.join(ext_dir, f))
                        for f in sorted(os.listdir(ext_dir))
                        if f.lower().endswith(valid_exts)
                    ]
                    if found:
                        images = found
                        break

        source = "extracted" if not local_imgs and images else "folder"
        source_label = "Ekstrak Dokumen (Sketsa Bersih)" if source == "extracted" else "Screenshot Folder (Hasil Scan Data)"
        image_items = []
        for img_path in images:
            if not os.path.isfile(img_path):
                continue
            info = get_cached_image_info(img_path)
            w, h, fmt, size_kb = info["width"], info["height"], info["format"], info["size_kb"]
            base_fn = os.path.basename(img_path)
            image_items.append({
                "url": f"/api/part/{part_no}/image/{base_fn}",
                "filename": base_fn,
                "width": w,
                "height": h,
                "dimensions": f"{w} × {h} px" if w and h else "Dimensi Standar",
                "size_kb": size_kb,
                "format": fmt,
                "source": source,
                "source_label": source_label
            })
        return {
            "part_number": part_no,
            "folder_name": folder_name,
            "status": status,
            "file_type": "excel",
            "source": source,
            "source_label": source_label,
            "total_images": len(image_items),
            "images": image_items
        }

    # Optimization: if scan_mode is auto, try finding local folder images or existing extracted images first
    # to avoid re-parsing Excel/PDF files on every preview request
    if scan_arg is None:
        base_name = os.path.basename(part_or_folder.strip("/\\"))
        folder_candidates = []
        if os.path.isdir(part_or_folder):
            folder_candidates.append(part_or_folder)
        for cat in ["belum", "tidak_ada_part", "done"]:
            folder_candidates.append(os.path.join("documents", cat, base_name))

        for candidate_dir in folder_candidates:
            if os.path.isdir(candidate_dir):
                local_imgs = [
                    os.path.join(candidate_dir, f)
                    for f in sorted(os.listdir(candidate_dir))
                    if f.lower().endswith(valid_exts)
                ]
                sub_img = os.path.join(candidate_dir, "images")
                if os.path.isdir(sub_img):
                    local_imgs.extend([
                        os.path.join(sub_img, f)
                        for f in sorted(os.listdir(sub_img))
                        if f.lower().endswith(valid_exts)
                    ])
                if local_imgs:
                    scan_arg = False
                    break

        if scan_arg is None:
            clean_sub = re.sub(r"[^0-9A-Za-z_-]", "_", base_name)
            for sub_name in [base_name, clean_sub, part_or_folder]:
                ext_dir = os.path.join("extracted_images", sub_name)
                if os.path.isdir(ext_dir):
                    ext_imgs = [
                        os.path.join(ext_dir, f)
                        for f in sorted(os.listdir(ext_dir))
                        if f.lower().endswith(valid_exts)
                    ]
                    if ext_imgs:
                        scan_arg = False
                        break

        if scan_arg is None:
            scan_arg = False

    try:
        resolved = resolve_part_document(part_or_folder, scan_images=scan_arg)
    except Exception:
        return {
            "part_number": part_or_folder,
            "folder_name": part_or_folder,
            "source": "none",
            "source_label": "Tidak Ada Gambar",
            "total_images": 0,
            "images": []
        }

    status = resolved.get("status", "belum")
    folder_name = os.path.basename(resolved["folder_path"])
    images = resolved.get("images", [])
    part_no = resolved.get("part_number", part_or_folder)

    # If resolved images list is empty, check extracted_images folder fallback
    if not images:
        clean_sub = re.sub(r"[^0-9A-Za-z_-]", "_", part_no)
        for sub_name in [part_no, clean_sub, folder_name]:
            ext_dir = os.path.join("extracted_images", sub_name)
            if os.path.isdir(ext_dir):
                found = [
                    os.path.join(ext_dir, f)
                    for f in sorted(os.listdir(ext_dir))
                    if f.lower().endswith(valid_exts)
                ]
                if found:
                    images = found
                    resolved["scan_images"] = True
                    break

    is_scan_from_doc = resolved.get("scan_images", False)
    source = "extracted" if is_scan_from_doc else "folder"
    source_label = "Ekstrak Dokumen (Sketsa Bersih)" if is_scan_from_doc else "Screenshot Folder (Hasil Scan Data)"

    image_items = []
    for img_path in images:
        if not os.path.isfile(img_path):
            continue
        info = get_cached_image_info(img_path)
        w, h, fmt, size_kb = info["width"], info["height"], info["format"], info["size_kb"]
        base_fn = os.path.basename(img_path)
        rel_sub = base_fn
        if "/images/" in img_path:
            rel_sub = f"images/{base_fn}"

        image_items.append({
            "url": f"/api/part/{resolved['part_number']}/image/{base_fn}",
            "filename": base_fn,
            "width": w,
            "height": h,
            "dimensions": f"{w} × {h} px" if w and h else "Dimensi Standar",
            "size_kb": size_kb,
            "format": fmt,
            "source": source,
            "source_label": source_label
        })

    return {
        "part_number": resolved["part_number"],
        "folder_name": folder_name,
        "status": status,
        "file_type": resolved["file_type"],
        "source": source,
        "source_label": source_label,
        "total_images": len(image_items),
        "images": image_items
    }


@app.get("/api/part/{part_or_folder}/image/{filename:path}")
def get_part_image_file(part_or_folder: str, filename: str):
    """Directly serve a part reference image by part number or folder name."""
    try:
        resolved = resolve_part_document(part_or_folder)
        folder_path = resolved.get("folder_path")
        part_no = resolved.get("part_number", part_or_folder)
    except Exception:
        folder_path = None
        part_no = part_or_folder

    clean_fn = os.path.basename(filename)
    clean_root, _ = os.path.splitext(clean_fn)
    candidate_names = [clean_fn]
    for ext in [".webp", ".png", ".jpg", ".jpeg"]:
        cand = clean_root + ext
        if cand not in candidate_names:
            candidate_names.append(cand)

    search_dirs = []
    if folder_path and os.path.isdir(folder_path):
        search_dirs.append(folder_path)
        search_dirs.append(os.path.join(folder_path, "images"))

    for p_key in [part_no, part_or_folder, clean_sub if 'clean_sub' in locals() else '']:
        if p_key:
            search_dirs.append(os.path.join("extracted_images", p_key))

    for cat in ["belum", "tidak_ada_part", "done"]:
        d1 = os.path.join("documents", cat, part_or_folder)
        if os.path.isdir(d1):
            search_dirs.append(d1)
            search_dirs.append(os.path.join(d1, "images"))

    for sdir in search_dirs:
        if not os.path.isdir(sdir):
            continue
        for cname in candidate_names:
            target = os.path.join(sdir, cname)
            if os.path.isfile(target):
                return FileResponse(target)

    raise HTTPException(status_code=404, detail="File gambar tidak ditemukan")


@app.get("/api/media/{status}/{folder}/{subpath:path}")
def get_media_file(status: str, folder: str, subpath: str):
    """Serve images stored in documents folder or extracted_images with robust fallback."""
    try:
        return get_part_image_file(folder, subpath)
    except HTTPException:
        target_path = os.path.join("documents", status, folder, subpath)
        if os.path.isfile(target_path):
            return FileResponse(target_path)
        raise HTTPException(status_code=404, detail="File gambar tidak ditemukan")


@app.get("/api/documents")
def get_documents(force: bool = Query(False)):
    """Return all documents separated into 'belum', 'tidak_ada_part', and 'done' with sub-millisecond cache."""
    fp = get_documents_fingerprint("documents")
    if not force and fp and _DOCUMENTS_CACHE.get("fingerprint") == fp and _DOCUMENTS_CACHE.get("data"):
        return _DOCUMENTS_CACHE["data"]

    with _DOCUMENTS_LOCK:
        # Re-check cache inside lock in case another thread just completed the scan
        if not force and fp and _DOCUMENTS_CACHE.get("fingerprint") == fp and _DOCUMENTS_CACHE.get("data"):
            return _DOCUMENTS_CACHE["data"]

        parts = list_available_parts("documents")
        belum_list = []
        tidak_ada_list = []
        done_list = []

        for p in parts:
            folder_path = p["folder_path"]
            status = p.get("status", "belum")

            preview_info = get_part_preview_images(folder_path, scan_mode="folder")

            doc_item = {
                **p,
                "preview_images": [img["url"] for img in preview_info["images"][:6]],
                "preview_details": preview_info["images"][:6],
                "total_images": preview_info["total_images"],
                "image_source": preview_info["source"],
                "image_source_label": preview_info["source_label"],
                "is_scan_data": preview_info["source"] == "folder" and preview_info["total_images"] > 0
            }

            if status == "done":
                done_list.append(doc_item)
            elif status == "tidak_ada_part":
                tidak_ada_list.append(doc_item)
            else:
                belum_list.append(doc_item)

        result_data = {
            "total": len(parts),
            "counts": {
                "belum": len(belum_list),
                "tidak_ada_part": len(tidak_ada_list),
                "done": len(done_list)
            },
            "belum": belum_list,
            "tidak_ada_part": tidak_ada_list,
            "done": done_list
        }
        _DOCUMENTS_CACHE["fingerprint"] = fp
        _DOCUMENTS_CACHE["data"] = result_data
        return result_data


@app.get("/api/part/{part_or_folder}/preview-images")
def get_preview_images_endpoint(part_or_folder: str, scan_mode: Optional[str] = Query(None)):
    """API endpoint to get live image previews for a part under specified scan_mode."""
    return get_part_preview_images(part_or_folder, scan_mode=scan_mode)


@app.get("/api/documents/{status}/{folder}/details")
def get_document_details(status: str, folder: str):
    """Get full details of a specific document including inspection points sample and full image gallery."""
    try:
        resolved = resolve_part_document(folder)
    except Exception:
        folder_path = os.path.join("documents", status, folder)
        if not os.path.isdir(folder_path):
            folder_path = os.path.join("documents", folder)
            if not os.path.isdir(folder_path):
                raise HTTPException(status_code=404, detail="Folder part tidak ditemukan")
        resolved = resolve_part_document(folder_path)

    try:
        items = extract_inspection_points(resolved["file_path"])
        real_status = resolved.get("status", status)
        real_folder = os.path.basename(resolved["folder_path"])
        preview_info = get_part_preview_images(resolved["folder_path"])

        return {
            "part_number": resolved["part_number"],
            "status": real_status,
            "folder_name": real_folder,
            "document_file": os.path.basename(resolved["file_path"]),
            "file_type": resolved["file_type"],
            "metadata": resolved["metadata"],
            "images_count": preview_info["total_images"],
            "image_source": preview_info["source"],
            "image_source_label": preview_info["source_label"],
            "images": preview_info["images"],
            "points_count": len(items),
            "inspection_points": items,
            "all_points_count": len(items)
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/documents/move")
def move_document(req: MoveDocRequest):
    """Move a document folder between 'belum', 'tidak_ada_part', and 'done'."""
    src = os.path.join("documents", req.from_status, req.folder_name)
    dest_dir = os.path.join("documents", req.to_status)
    dest = os.path.join(dest_dir, req.folder_name)

    if not os.path.isdir(src):
        # Try resolving real location if from_status was different
        parts = list_available_parts("documents")
        found_p = next((p for p in parts if p["folder_name"] == req.folder_name), None)
        if found_p:
            src = found_p["folder_path"]
        else:
            raise HTTPException(status_code=404, detail=f"Folder sumber '{req.folder_name}' tidak ditemukan")

    os.makedirs(dest_dir, exist_ok=True)
    if os.path.exists(dest) and src != dest:
        raise HTTPException(status_code=400, detail=f"Folder tujuan '{dest}' sudah ada")

    if src != dest:
        shutil.move(src, dest)
        clear_document_caches()
        _DOCUMENTS_CACHE["fingerprint"] = ""
        _DOCUMENTS_CACHE["data"] = None

    return {
        "success": True,
        "message": f"Part '{req.folder_name}' berhasil dipindahkan ke '{req.to_status}'",
        "folder_name": req.folder_name,
        "new_status": req.to_status
    }


@app.post("/api/documents/check-server-availability")
async def api_check_server_availability(req: CheckServerAvailabilityRequest):
    """
    Checks whether part folders in 'documents/tidak_ada_part' are now registered in FactoryHub.
    If registered, moves them to 'documents/belum'. If not, keeps them in 'documents/tidak_ada_part'.
    """
    tidak_ada_dir = os.path.join("documents", "tidak_ada_part")
    if not os.path.isdir(tidak_ada_dir):
        return {
            "success": True,
            "source": "none",
            "checked_count": 0,
            "moved_count": 0,
            "moved_parts": [],
            "remaining_count": 0,
            "remaining_parts": []
        }

    if req.folder_name:
        folder_candidates = [req.folder_name]
    else:
        folder_candidates = [
            f for f in sorted(os.listdir(tidak_ada_dir))
            if not f.startswith(".") and os.path.isdir(os.path.join(tidak_ada_dir, f))
        ]

    if not folder_candidates:
        return {
            "success": True,
            "source": "none",
            "checked_count": 0,
            "moved_count": 0,
            "moved_parts": [],
            "remaining_count": 0,
            "remaining_parts": []
        }

    master_data = None
    source = "catalog"

    if req.live:
        try:
            master_data = await fetch_master_options()
            source = "live"
            # Sync into local catalog cache
            try:
                cat = load_catalog()
                reg_opts = master_data.get("regular", [])
                proj_opts = master_data.get("project", [])
                new_parts_list = []
                for r in reg_opts:
                    val = r.get("value", "")
                    txt = r.get("text", "")
                    pname = txt.split(" - ")[-1].strip() if " - " in txt else ""
                    new_parts_list.append({
                        "value": val,
                        "part_number": val,
                        "clean_number": clean_part_code(val),
                        "part_name": pname,
                        "category": "REGULAR"
                    })
                for p in proj_opts:
                    val = p.get("dataNum") or p.get("value", "")
                    txt = p.get("text", "")
                    new_parts_list.append({
                        "value": val,
                        "part_number": val,
                        "clean_number": clean_part_code(val),
                        "part_name": txt,
                        "category": "PROJECT"
                    })
                if new_parts_list:
                    cat["parts"] = new_parts_list
                    cat["total_parts"] = len(new_parts_list)
                    cat["synced_at"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                    save_catalog(cat)
            except Exception as ex_c:
                print(f"[Warning] Failed updating local catalog cache: {ex_c}")
        except Exception as ex_live:
            print(f"[!] Live fetch failed ({ex_live}), falling back to local catalog.")

    if not master_data:
        cat = load_catalog()
        cat_parts = cat.get("parts", [])
        master_data = {
            "regular": [{"value": p["value"], "text": p.get("part_name", "")} for p in cat_parts if p.get("category") == "REGULAR"],
            "project": [{"value": p["value"], "text": p.get("part_name", "")} for p in cat_parts if p.get("category") == "PROJECT"]
        }

    moved_parts = []
    remaining_parts = []

    for f_name in folder_candidates:
        src_folder = os.path.join(tidak_ada_dir, f_name)
        if not os.path.isdir(src_folder):
            continue

        # Determine part number to query
        part_to_query = f_name
        info_file = os.path.join(src_folder, "info.json")
        if os.path.isfile(info_file):
            try:
                with open(info_file, "r", encoding="utf-8") as fi:
                    idat = json.load(fi)
                    if idat.get("part_number"):
                        part_to_query = idat["part_number"]
            except Exception:
                pass

        match_res = match_part(part_to_query, master_data)
        if match_res.get("status") == "ADA":
            dest_dir = os.path.join("documents", "belum")
            os.makedirs(dest_dir, exist_ok=True)
            dest_folder = os.path.join(dest_dir, f_name)

            # Move folder to 'belum'
            if not os.path.exists(dest_folder):
                shutil.move(src_folder, dest_folder)

                # Update or create info.json with authoritative FactoryHub metadata
                try:
                    target_info = os.path.join(dest_folder, "info.json")
                    info_dict = {}
                    if os.path.isfile(target_info):
                        try:
                            with open(target_info, "r", encoding="utf-8") as tfi:
                                content = tfi.read().strip()
                                if content:
                                    info_dict = json.loads(content)
                        except Exception:
                            info_dict = {}

                    official_name = ""
                    details = match_res.get("details", "")
                    if " - " in details:
                        official_name = details.split(" - ", 1)[1].strip()
                    elif details:
                        official_name = details.strip()

                    if not info_dict.get("part_name") and official_name:
                        info_dict["part_name"] = official_name
                    if not info_dict.get("part_number"):
                        info_dict["part_number"] = match_res.get("part_number") or part_to_query
                    if not info_dict.get("checksheet_category"):
                        info_dict["checksheet_category"] = "Accuracy"

                    with open(target_info, "w", encoding="utf-8") as tfi:
                        json.dump(info_dict, tfi, indent=2, ensure_ascii=False)
                except Exception as ex_info:
                    print(f"[Warning] Failed writing info.json: {ex_info}")

            moved_parts.append({
                "folder_name": f_name,
                "part_number": part_to_query,
                "category": match_res.get("category"),
                "details": match_res.get("details", "")
            })
        else:
            remaining_parts.append({
                "folder_name": f_name,
                "part_number": part_to_query,
                "reason": "Belum terdaftar di Regular maupun Project Part"
            })

    if moved_parts:
        clear_document_caches()
        _DOCUMENTS_CACHE["fingerprint"] = ""
        _DOCUMENTS_CACHE["data"] = None

    return {
        "success": True,
        "source": source,
        "checked_count": len(folder_candidates),
        "moved_count": len(moved_parts),
        "moved_parts": moved_parts,
        "remaining_count": len(remaining_parts),
        "remaining_parts": remaining_parts
    }


@app.post("/api/part/duplicate")
async def api_duplicate_part(req: DuplicatePartRequest):
    """
    Duplicate an existing part document, sketches, and metadata to a new part number.
    """
    try:
        res = duplicate_part(
            source_part_or_folder=req.source_part,
            target_part_number=req.target_part,
            target_status=req.target_status or "belum",
            rename_files=True if req.rename_files is None else req.rename_files
        )
        # Invalidate document cache
        _DOCUMENTS_CACHE["fingerprint"] = ""
        _DOCUMENTS_CACHE["data"] = None
        return res
    except FileExistsError as fe:
        raise HTTPException(status_code=409, detail=str(fe))
    except FileNotFoundError as fnf:
        raise HTTPException(status_code=404, detail=str(fnf))
    except ValueError as ve:
        raise HTTPException(status_code=400, detail=str(ve))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Gagal menduplikasi part: {str(e)}")


@app.post("/api/server-duplicate")
async def api_server_duplicate(req: ServerDuplicateRequest):
    """
    Duplicate checksheet master directly from FactoryHub server to a new part.
    Scrapes source part data & images, saves local Excel + sketches, and populates new checksheet on FactoryHub.
    """
    try:
        res = await duplicate_server_to_server(
            source_part=req.source_part,
            target_part=req.target_part,
            submit=req.submit or False,
            headless=req.headless or False,
            browser_channel=req.browser_channel or "chromium",
            target_status=req.target_status or "belum"
        )
        # Invalidate document cache
        _DOCUMENTS_CACHE["fingerprint"] = ""
        _DOCUMENTS_CACHE["data"] = None
        return res
    except FileNotFoundError as fnf:
        raise HTTPException(status_code=404, detail=str(fnf))
    except ValueError as ve:
        raise HTTPException(status_code=400, detail=str(ve))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Gagal menduplikasi dari server: {str(e)}")


@app.get("/api/media/{status}/{folder}/{subpath:path}")
def get_media_file(status: str, folder: str, subpath: str):
    """Serve images stored in documents folder or extracted_images with robust fallback."""
    # 1. Direct location in documents
    target_path = os.path.join("documents", status, folder, subpath)
    if os.path.isfile(target_path):
        return FileResponse(target_path)

    # 2. Check all categories in documents
    for cat in ["belum", "tidak_ada_part", "done"]:
        p = os.path.join("documents", cat, folder, subpath)
        if os.path.isfile(p):
            return FileResponse(p)

    # 3. Check extracted_images by folder name
    p_ext = os.path.join("extracted_images", folder, subpath)
    if os.path.isfile(p_ext):
        return FileResponse(p_ext)

    # 4. Check extracted_images by searching all subdirectories
    if os.path.isdir("extracted_images"):
        # Check direct subpath
        p_base = os.path.join("extracted_images", subpath)
        if os.path.isfile(p_base):
            return FileResponse(p_base)

        base_fn = os.path.basename(subpath)
        for d in os.listdir("extracted_images"):
            sub_d = os.path.join("extracted_images", d)
            if os.path.isdir(sub_d):
                p_cand = os.path.join(sub_d, base_fn)
                if os.path.isfile(p_cand):
                    return FileResponse(p_cand)

    raise HTTPException(status_code=404, detail="File gambar tidak ditemukan")


@app.post("/api/search")
async def search_parts(req: SearchRequest):
    """Batch search part numbers against FactoryHub."""
    global CACHED_MASTER_OPTIONS

    raw_query = req.query.strip()
    if not raw_query:
        raise HTTPException(status_code=400, detail="Query pencarian tidak boleh kosong")

    parts_list = parse_comma_separated_parts([raw_query])
    if not parts_list:
        raise HTTPException(status_code=400, detail="Tidak ada nomor part yang valid")

    if CACHED_MASTER_OPTIONS is None:
        cat_data = load_catalog()
        cat_parts = cat_data.get("parts", [])
        if cat_parts:
            reg = []
            proj = []
            for cp in cat_parts:
                c_item = {
                    "value": cp.get("value") or cp.get("part_number", ""),
                    "text": f"{cp.get('part_number', '')} - {cp.get('part_name', '')}".strip(" -"),
                    "dataNum": cp.get("part_number", "")
                }
                if cp.get("category") == "NEW PROJECT":
                    proj.append(c_item)
                else:
                    reg.append(c_item)
            CACHED_MASTER_OPTIONS = {"regular": reg, "project": proj}
        else:
            CACHED_MASTER_OPTIONS = await fetch_master_options()

    local_map = build_local_parts_map()
    cat_data = load_catalog()
    cat_parts = cat_data.get("parts", [])
    results = []

    for part in parts_list:
        match_res = match_part(part, CACHED_MASTER_OPTIONS, local_parts_map=local_map, catalog_parts=cat_parts)
        results.append(match_res)

        logger.log_search(
            search_query=raw_query,
            part_number=match_res["part_number"],
            fh_status=match_res["status"],
            category=match_res["category"],
            template_id="-",
            local_doc=match_res.get("local_doc", "-"),
            notes=match_res.get("details", "")
        )

    total_ada = sum(1 for r in results if r["status"] == "ADA")
    total_tidak = sum(1 for r in results if r["status"] != "ADA")
    missing_parts = [r["part_number"] for r in results if r["status"] != "ADA"]

    return {
        "query": raw_query,
        "total": len(results),
        "ada_count": total_ada,
        "tidak_ada_count": total_tidak,
        "missing_parts": missing_parts,
        "results": results
    }


@app.post("/api/run")
async def trigger_run(req: RunRequest):
    """
    Run checksheet automation for a specific part.
    Automatically moves folder to 'done' upon success or 'tidak_ada_part' if part is missing on FactoryHub!
    """
    scan_val = None
    if req.scan_mode == "scan":
        scan_val = True
    elif req.scan_mode == "folder":
        scan_val = False

    # Resolve folder name and source status
    try:
        resolved = resolve_part_document(req.part)
        src_folder = os.path.basename(resolved["folder_path"])
        src_status = resolved.get("status", "belum")
    except Exception:
        src_folder = req.part
        src_status = "belum"

    try:
        res = await run_automation(
            part_or_excel=req.part,
            headless=req.headless,
            submit=req.submit,
            doc_number=req.doc_number,
            scan_images=scan_val,
            browser_channel=req.browser_channel
        )

        moved_to = None
        # Auto-move based on result status
        if res and res.get("status") == "part_not_registered":
            if src_status != "tidak_ada_part":
                src_path = os.path.join("documents", src_status, src_folder)
                dest_dir = os.path.join("documents", "tidak_ada_part")
                if os.path.isdir(src_path):
                    os.makedirs(dest_dir, exist_ok=True)
                    dest_path = os.path.join(dest_dir, src_folder)
                    if not os.path.exists(dest_path):
                        shutil.move(src_path, dest_path)
                        moved_to = "tidak_ada_part"
        elif res and res.get("status") in ["submitted", "prepared"]:
            if src_status != "done":
                src_path = os.path.join("documents", src_status, src_folder)
                dest_dir = os.path.join("documents", "done")
                if os.path.isdir(src_path):
                    os.makedirs(dest_dir, exist_ok=True)
                    dest_path = os.path.join(dest_dir, src_folder)
                    if not os.path.exists(dest_path):
                        shutil.move(src_path, dest_path)
                        moved_to = "done"

        return {
            "success": True,
            "part": req.part,
            "moved_to": moved_to,
            "result": res
        }
    except Exception as e:
        logger.log_execution(
            part_number=req.part,
            doc_file=req.part,
            file_type="unknown",
            scan_mode=req.scan_mode or "auto",
            result_action="ERROR",
            points_count=0,
            images_count=0,
            diff_summary=str(e),
            notes=f"Execution error: {str(e)}"
        )
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/diff/compare")
async def compare_diff(req: DiffRequest):
    """
    On-demand Diff Comparison:
    Compares a local checksheet document against FactoryHub's current template or recent log record.
    Returns full comparison rows for tabular display.
    """
    try:
        resolved = resolve_part_document(req.part)
    except Exception as e:
        raise HTTPException(status_code=404, detail=f"Part '{req.part}' tidak ditemukan di documents/: {e}")

    part_no = resolved["part_number"]
    doc_path = resolved["file_path"]
    new_items = extract_inspection_points(doc_path)
    new_meta = resolved["metadata"]

    # 1. Check if we have recent diff details from execution logs
    recent_logs = logger.get_recent_execution_logs(limit=50)
    matched_log = next((l for l in recent_logs if l.get("part_number") == part_no and l.get("diff_details")), None)

    if matched_log and matched_log["diff_details"].get("comparison_rows"):
        cached_diff = matched_log["diff_details"]
        if cached_diff.get("new_count") == len(new_items):
            return {
                "part_number": part_no,
                "document_file": os.path.basename(doc_path),
                "diff": cached_diff
            }
        else:
            # Recompute diff with freshly extracted items
            old_rows = cached_diff.get("comparison_rows", [])
            old_items = []
            for r in old_rows:
                if r.get("old_standard") and r.get("old_standard") != "-":
                    old_items.append({
                        "item_no": r.get("item_no", ""),
                        "inspection_item": r.get("inspection_item", ""),
                        "standard": r.get("old_standard", ""),
                        "method": r.get("old_method", "")
                    })
            if old_items:
                old_meta = {
                    "doc_number": cached_diff.get("meta_diff", {}).get("doc_number", {}).get("old", ""),
                    "description": cached_diff.get("meta_diff", {}).get("description", {}).get("old", "")
                }
                recomputed = compute_template_diff(old_meta, old_items, new_meta, new_items)
                return {
                    "part_number": part_no,
                    "document_file": os.path.basename(doc_path),
                    "diff": recomputed
                }

    # 2. Check FactoryHub live in headless mode if existing template exists
    try:
        from playwright.async_api import async_playwright
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            page = await browser.new_page()
            await login_factoryhub(page)
            existing = await find_existing_template(page, part_no)
            if existing:
                await page.goto(existing["editUrl"], wait_until="networkidle")
                old_template_data = await page.evaluate(r"""() => {
                    const docInp = document.querySelector('input[name="doc_number"]');
                    const descInp = document.querySelector('input[name="description"]');
                    const tbody = document.getElementById('inspection-tbody');

                    const oldItems = [];
                    if (tbody) {
                        const trs = tbody.querySelectorAll('tr.inspection-row, tr');
                        trs.forEach((tr, index) => {
                            const getVal = (sel) => {
                                const el = tr.querySelector(sel);
                                return el ? el.value.trim() : '';
                            };
                            const itemNo = getVal('input[name*="[item_no]"]') || (index + 1).toString();
                            const itemDesc = getVal('input[name*="[inspection_item]"]');
                            const std = getVal('input[name*="[standard]"]');
                            const method = getVal('input[name*="[method]"], input[name*="[instrument_tools]"]') ||
                                           (tr.cells && tr.cells[5] && tr.cells[5].querySelector('input') ? tr.cells[5].querySelector('input').value.trim() : '');
                            const master = getVal('input[name*="[master_data]"]') ||
                                           (tr.cells && tr.cells[6] && tr.cells[6].querySelector('input') ? tr.cells[6].querySelector('input').value.trim() : '');

                            if (itemDesc || std) {
                                oldItems.push({
                                    item_no: itemNo,
                                    inspection_item: itemDesc,
                                    standard: std,
                                    method: method,
                                    master_data: master
                                });
                            }
                        });
                    }

                    return {
                        doc_number: docInp ? docInp.value.trim() : '',
                        description: descInp ? descInp.value.trim() : '',
                        items: oldItems
                    };
                }""")
                await browser.close()
                diff_data = compute_template_diff(
                    old_meta=old_template_data,
                    old_items=old_template_data.get("items", []),
                    new_meta=new_meta,
                    new_items=new_items
                )
                return {
                    "part_number": part_no,
                    "document_file": os.path.basename(doc_path),
                    "diff": diff_data
                }
            await browser.close()
    except Exception as e:
        print(f"[!] Warning: Live diff check failed: {e}")

    # 3. Fallback: If no template on FactoryHub, represent all items as ADDED
    added_rows = []
    for idx, it in enumerate(new_items):
        added_rows.append({
            "status": "ADDED",
            "item_no": it.get("item_no") or str(idx + 1),
            "inspection_item": it.get("inspection_item"),
            "old_standard": "-",
            "new_standard": it.get("standard") or "-",
            "old_method": "-",
            "new_method": it.get("method") or "-",
            "changes": ["Titik baru"]
        })

    mock_diff = {
        "summary": f"+{len(new_items)} titik baru (Template belum pernah dibuat di database)",
        "meta_diff": {},
        "added": new_items,
        "removed": [],
        "modified": [],
        "unchanged": [],
        "unchanged_count": 0,
        "old_count": 0,
        "new_count": len(new_items),
        "comparison_rows": added_rows
    }

    return {
        "part_number": part_no,
        "document_file": os.path.basename(doc_path),
        "diff": mock_diff
    }


@app.get("/api/logs/excel")
def get_excel_log_data():
    """
    Read both sheets of logs/history.xlsx into JSON so the user can inspect
    Execution History and Search History directly on the web without downloading.
    """
    excel_path = logger.EXCEL_LOG_PATH
    if not os.path.isfile(excel_path):
        return {
            "execution_history": [],
            "search_history": []
        }

    try:
        wb = openpyxl.load_workbook(excel_path, data_only=True)
        exec_rows = []
        if "Execution History" in wb.sheetnames:
            ws = wb["Execution History"]
            headers = [str(ws.cell(1, c).value or "") for c in range(1, ws.max_column + 1)]
            for r in range(2, ws.max_row + 1):
                vals = [str(ws.cell(r, c).value or "").strip() for c in range(1, len(headers) + 1)]
                if any(vals):
                    exec_rows.append(dict(zip(headers, vals)))

        search_rows = []
        if "Search History" in wb.sheetnames:
            ws = wb["Search History"]
            headers = [str(ws.cell(1, c).value or "") for c in range(1, ws.max_column + 1)]
            for r in range(2, ws.max_row + 1):
                vals = [str(ws.cell(r, c).value or "").strip() for c in range(1, len(headers) + 1)]
                if any(vals):
                    search_rows.append(dict(zip(headers, vals)))

        # Newest first
        exec_rows.reverse()
        search_rows.reverse()

        return {
            "execution_history": exec_rows,
            "search_history": search_rows
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Gagal membaca Excel log: {e}")


@app.get("/api/logs")
def get_logs(limit: int = Query(50, ge=1, le=500)):
    """Retrieve execution logs and search log summary."""
    exec_logs = logger.get_recent_execution_logs(limit=limit)
    excel_path = logger.EXCEL_LOG_PATH
    has_excel = os.path.isfile(excel_path)

    return {
        "has_excel_log": has_excel,
        "excel_download_url": "/api/download/history" if has_excel else None,
        "execution_logs": exec_logs
    }


@app.get("/api/download/history")
def download_excel_log():
    """Download the logs/history.xlsx workbook."""
    if not os.path.isfile(logger.EXCEL_LOG_PATH):
        raise HTTPException(status_code=404, detail="File logs/history.xlsx belum dibuat.")
    return FileResponse(
        logger.EXCEL_LOG_PATH,
        filename="Summit_Checksheet_History.xlsx",
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )


# ==============================================================================
# IMAGE COMPRESSION & WEBP OPTIMIZATION TOOL ENDPOINTS
# ==============================================================================
@app.get("/api/tools/image-stats")
def get_tools_image_stats():
    """Returns total counts and sizes of non-webp vs webp images across the workspace."""
    try:
        return get_image_stats(["documents", "extracted_images"])
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/tools/compress-webp")
def run_compress_webp_api(req: CompressImagesRequest):
    """
    Converts PNG/JPG images in the selected target directories to compressed WebP.
    Saves disk space and speeds up dashboard load times & FactoryHub image uploads.
    """
    target_dirs = []
    if req.target == "documents":
        target_dirs = ["documents"]
    elif req.target == "extracted_images":
        target_dirs = ["extracted_images"]
    else:
        target_dirs = ["documents", "extracted_images"]

    try:
        result = convert_images_to_webp(
            target_dirs=target_dirs,
            quality=req.quality or 82,
            max_dimension=req.max_dimension or 1920,
            delete_original=req.delete_original if req.delete_original is not None else True,
            dry_run=False
        )
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


class CreateFolderRequest(BaseModel):
    folder_name: str
    status: str = "belum"


class CatalogFolderRequest(BaseModel):
    part_number: str
    status: str = "belum"


class OpenFinderRequest(BaseModel):
    folder_name: str
    status: Optional[str] = None


@app.post("/api/documents/create-folder")
def create_folder_endpoint(req: CreateFolderRequest):
    """Create a new part folder in 'belum', 'tidak_ada_part', or 'done', auto-generating info.json snippet if part exists in catalog."""
    clean_name = re.sub(r'[\\/:*?"<>|]', '_', req.folder_name.strip())
    if not clean_name:
        raise HTTPException(status_code=400, detail="Nama folder tidak boleh kosong")

    status = req.status.strip().lower()
    if status not in ["belum", "tidak_ada_part", "done"]:
        status = "belum"

    target_dir = os.path.join("documents", status, clean_name)
    if os.path.exists(target_dir):
        raise HTTPException(status_code=400, detail=f"Folder '{clean_name}' sudah ada di kategori '{status}'")

    os.makedirs(target_dir, exist_ok=True)

    # Auto-generate info.json snippet if in catalog
    snippet_path = None
    snippet_meta = None
    try:
        import json as pyjson
        clean_target = clean_part_code(clean_name)
        cat = load_catalog()
        part_info = next((p for p in cat.get("parts", []) if (p.get("clean_number") or clean_part_code(p.get("part_number", ""))) == clean_target), None)
        if part_info:
            info_file = os.path.join(target_dir, "info.json")
            snippet_meta = {
                "part_number": part_info.get("part_number", clean_name),
                "part_name": part_info.get("part_name", ""),
                "category": part_info.get("category", "REGULAR"),
                "factoryhub_value": part_info.get("value", ""),
                "has_template_in_factoryhub": part_info.get("has_template", False),
                "created_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
                "notes": "Dibuat otomatis dari Katalog Master FactoryHub",
                "template_details": part_info.get("template_info")
            }
            with open(info_file, "w", encoding="utf-8") as f:
                pyjson.dump(snippet_meta, f, indent=2, ensure_ascii=False)
            snippet_path = info_file
    except Exception:
        pass

    clear_document_caches()
    _DOCUMENTS_CACHE["fingerprint"] = ""
    _DOCUMENTS_CACHE["data"] = None

    return {
        "success": True,
        "folder_name": clean_name,
        "status": status,
        "folder_path": target_dir,
        "snippet_path": snippet_path,
        "metadata": snippet_meta,
        "message": f"Folder '{clean_name}' berhasil dibuat di kategori '{status}'"
    }


@app.post("/api/documents/upload")
async def upload_documents(
    files: List[UploadFile] = File(...),
    status: str = Form("belum"),
    folder_name: Optional[str] = Form(None),
    target_folder: Optional[str] = Form(None)
):
    """Upload documents (.xlsx, .pdf) or images, auto-detecting part number and creating folder."""
    if not files:
        raise HTTPException(status_code=400, detail="Tidak ada file yang diunggah")

    target_folder = folder_name or target_folder

    status = status.strip().lower()
    if status not in ["belum", "tidak_ada_part", "done"]:
        status = "belum"

    temp_dir = os.path.join("extracted_images", "_temp_upload")
    os.makedirs(temp_dir, exist_ok=True)

    saved_temp_files = []
    doc_file_temp = None
    doc_orig_name = None

    for uf in files:
        orig_fn = uf.filename
        clean_fn = os.path.basename(orig_fn)
        tmp_path = os.path.join(temp_dir, clean_fn)
        with open(tmp_path, "wb") as buffer:
            shutil.copyfileobj(uf.file, buffer)
        saved_temp_files.append((tmp_path, clean_fn))

        if clean_fn.lower().endswith((".xlsx", ".xls", ".pdf")) and not doc_file_temp:
            doc_file_temp = tmp_path
            doc_orig_name = clean_fn

    detected_part_no = ""
    part_meta = {}
    if target_folder and target_folder.strip():
        final_folder_name = re.sub(r'[\\/:*?"<>|]', '_', target_folder.strip())
        dest_folder = None
        for s in [status, "belum", "tidak_ada_part", "done"]:
            cand = os.path.join("documents", s, final_folder_name)
            if os.path.isdir(cand):
                dest_folder = cand
                status = s
                break
        if not dest_folder:
            dest_folder = os.path.join("documents", status, final_folder_name)
    elif doc_file_temp:
        try:
            part_meta = extract_metadata(doc_file_temp)
            detected_part_no = part_meta.get("part_number", "").strip()
        except Exception:
            pass

        if not detected_part_no:
            tokens = re.split(r"[^0-9A-Za-z\-]+", doc_orig_name)
            for t in tokens:
                if any(c.isdigit() for c in t) and len(t) >= 6 and not t.lower().startswith("form"):
                    detected_part_no = t.upper()
                    break

        if detected_part_no:
            final_folder_name = detected_part_no
        else:
            base_root, _ = os.path.splitext(doc_orig_name)
            final_folder_name = re.sub(r'[\\/:*?"<>|]', '_', base_root.strip())
        dest_folder = os.path.join("documents", status, final_folder_name)
    else:
        first_fn = saved_temp_files[0][1]
        base_root, _ = os.path.splitext(first_fn)
        final_folder_name = re.sub(r'[\\/:*?"<>|]', '_', base_root.strip())
        dest_folder = os.path.join("documents", status, final_folder_name)

    os.makedirs(dest_folder, exist_ok=True)

    saved_dest_files = []
    for tmp_path, clean_fn in saved_temp_files:
        base_fn, ext = os.path.splitext(clean_fn)
        target_name = clean_fn
        counter = 1
        while os.path.exists(os.path.join(dest_folder, target_name)):
            target_name = f"{base_fn}_{counter}{ext}"
            counter += 1

        dest_path = os.path.join(dest_folder, target_name)
        shutil.move(tmp_path, dest_path)
        saved_dest_files.append(target_name)

    clear_document_caches()
    _DOCUMENTS_CACHE["fingerprint"] = ""
    _DOCUMENTS_CACHE["data"] = None

    return {
        "success": True,
        "folder_name": final_folder_name,
        "status": status,
        "part_number": detected_part_no or final_folder_name,
        "metadata": part_meta,
        "saved_files": saved_dest_files,
        "message": f"Berhasil mengunggah {len(saved_dest_files)} file ke folder '{final_folder_name}'"
    }


@app.post("/api/documents/open-finder")
def open_finder_endpoint(req: OpenFinderRequest):
    """Open a document folder in macOS Finder."""
    target_path = None
    if req.status:
        cand = os.path.join("documents", req.status, req.folder_name)
        if os.path.isdir(cand):
            target_path = os.path.abspath(cand)

    if not target_path:
        parts = list_available_parts("documents")
        p = next((x for x in parts if x["folder_name"] == req.folder_name or x["part_number"] == req.folder_name), None)
        if p:
            target_path = os.path.abspath(p["folder_path"])

    if not target_path or not os.path.isdir(target_path):
        raise HTTPException(status_code=404, detail="Folder tidak ditemukan di disk")

    try:
        subprocess.run(["open", target_path], check=True)
        return {"success": True, "path": target_path, "message": "Folder dibuka di Finder"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Gagal membuka Finder: {e}")


@app.get("/api/documents/{status}/{folder}/export")
def export_document_points(status: str, folder: str, format: str = Query("json")):
    """Export clean inspection points in JSON or CSV format."""
    try:
        resolved = resolve_part_document(folder)
        items = extract_inspection_points(resolved["file_path"])
    except Exception as e:
        raise HTTPException(status_code=404, detail=f"Gagal mengekstrak data: {e}")

    part_no = resolved.get("part_number", folder)
    if format.lower() == "csv":
        import io, csv
        output = io.StringIO()
        writer = csv.writer(output)
        writer.writerow(["No", "Balloon", "Inspection Item", "Standard / Tolerance", "Method / Tool", "Master Data"])
        for idx, it in enumerate(items, 1):
            writer.writerow([
                idx,
                it.get("item_no", ""),
                it.get("inspection_item", ""),
                it.get("standard", ""),
                it.get("method", ""),
                it.get("master_data", "")
            ])
        output.seek(0)
        return Response(
            content=output.getvalue(),
            media_type="text/csv",
            headers={"Content-Disposition": f'attachment; filename="checksheet_{part_no}.csv"'}
        )

    return {
        "part_number": part_no,
        "folder_name": folder,
        "total_points": len(items),
        "items": items
    }


# ==========================================
# FACTORYHUB CATALOG & AUTOCOMPLETE ENDPOINTS
# ==========================================

@app.get("/api/catalog/search")
def api_catalog_search(
    q: Optional[str] = Query(None, description="Query part number or part name"),
    query: Optional[str] = Query(None, description="Query part number or part name alias"),
    category: Optional[str] = Query(None, description="REGULAR or NEW PROJECT"),
    limit: int = Query(30, description="Max results"),
    gap_only: bool = Query(False, description="Filter only parts with no local doc")
):
    """Instant in-memory autocomplete & search against FactoryHub master catalog."""
    search_str = (q or query or "").strip()
    results = search_catalog(query=search_str, category=category, limit=limit, only_gap=gap_only)
    return {"results": results, "total": len(results)}


@app.get("/api/catalog/stats")
def api_catalog_stats():
    """Get catalog coverage, master counts, and checksheet gap radar."""
    return get_catalog_stats()


@app.post("/api/catalog/create-folder")
def api_catalog_create_folder(req: CatalogFolderRequest):
    """1-Click workspace folder generation with official info.json metadata snippet."""
    try:
        res = create_folder_from_catalog(req.part_number, req.status)
        _DOCUMENTS_CACHE["fingerprint"] = ""
        _DOCUMENTS_CACHE["data"] = None
        return res
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.post("/api/catalog/sync")
async def api_catalog_sync():
    """Trigger background synchronization of FactoryHub catalog."""
    asyncio.create_task(sync_factoryhub_catalog())
    return {"success": True, "message": "Sinkronisasi katalog FactoryHub dimulai di background"}


# Mount static assets
app.mount("/", StaticFiles(directory="static", html=True), name="static")
