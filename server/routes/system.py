"""
System maintenance, Git version control, and auto-update API router.
"""
import os
import subprocess
from datetime import datetime
from fastapi import APIRouter, HTTPException

router = APIRouter(prefix="/api/system", tags=["System"])


import time
_last_update_check: dict = {
    "data": None,
    "timestamp": 0.0
}
UPDATE_CHECK_TTL = 300.0  # Cache git update status for 5 minutes


def run_git_cmd(args: list, timeout: int = 5) -> str:
    """Run git command in project root with sensible timeout."""
    cwd = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    result = subprocess.run(
        ["git"] + args,
        cwd=cwd,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        timeout=timeout
    )
    if result.returncode != 0:
        err = result.stderr.strip() or result.stdout.strip()
        raise RuntimeError(f"Git command failed ({' '.join(args)}): {err}")
    return result.stdout.strip()


@router.get("/version")
def get_system_version():
    """Return application version, git commit, and banner."""
    from core.version import VERSION, APP_NAME, SERVER_BOOT_TIME, get_git_commit, get_git_date, get_full_banner
    return {
        "app_name": APP_NAME,
        "version": VERSION,
        "commit": get_git_commit(),
        "date": get_git_date(),
        "boot_time": SERVER_BOOT_TIME,
        "banner": get_full_banner()
    }


@router.get("/update-status")
def get_update_status(force: bool = False):
    """Check if remote origin/main has newer commits (cached 5 min to avoid lag)."""
    now = time.time()
    if not force and _last_update_check["data"] is not None and (now - _last_update_check["timestamp"] < UPDATE_CHECK_TTL):
        return _last_update_check["data"]

    try:
        current_commit = run_git_cmd(["rev-parse", "--short", "HEAD"])
        current_branch = run_git_cmd(["rev-parse", "--abbrev-ref", "HEAD"])
        
        # Fetch remote silently with fast 4s timeout
        try:
            run_git_cmd(["fetch", "origin", "main"], timeout=4)
        except Exception as e:
            res = {
                "has_update": False,
                "current_commit": current_commit,
                "current_branch": current_branch,
                "remote_commit": current_commit,
                "behind_count": 0,
                "commits_behind": [],
                "error": f"Tidak dapat terhubung ke remote: {str(e)}",
                "checked_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            }
            _last_update_check["data"] = res
            _last_update_check["timestamp"] = now
            return res

        remote_commit = run_git_cmd(["rev-parse", "--short", "origin/main"])
        count_str = run_git_cmd(["rev-list", "--count", "HEAD..origin/main"])
        behind_count = int(count_str) if count_str.isdigit() else 0

        commits_behind = []
        if behind_count > 0:
            log_output = run_git_cmd(["log", "-n", "10", "--oneline", "HEAD..origin/main"])
            commits_behind = [line.strip() for line in log_output.split("\n") if line.strip()]

        from core.version import VERSION, get_full_banner
        res = {
            "version": VERSION,
            "banner": get_full_banner(),
            "has_update": behind_count > 0,
            "current_commit": current_commit,
            "current_branch": current_branch,
            "remote_commit": remote_commit,
            "behind_count": behind_count,
            "commits_behind": commits_behind,
            "checked_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        }
        _last_update_check["data"] = res
        _last_update_check["timestamp"] = now
        return res
    except Exception as e:
        return {
            "has_update": False,
            "error": str(e),
            "checked_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        }


@router.post("/update")
def execute_system_update():
    """Pull latest code from origin/main, auto-stashing any dirty local changes to prevent merge aborts."""
    try:
        # Check if working directory is dirty (e.g. CRLF line endings on Windows or accidental edits)
        try:
            status_output = run_git_cmd(["status", "--porcelain"])
            if status_output:
                run_git_cmd(["stash", "push", "-m", f"auto-stash-{datetime.now().strftime('%Y%m%d%H%M%S')}"])
        except Exception:
            pass

        output = run_git_cmd(["pull", "origin", "main"])
        new_commit = run_git_cmd(["rev-parse", "--short", "HEAD"])
        return {
            "status": "success",
            "message": "Aplikasi berhasil diperbarui ke versi terbaru!",
            "new_commit": new_commit,
            "output": output
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Gagal melakukan update git pull: {str(e)}")


@router.get("/sync-categories/progress")
def get_sync_categories_progress():
    """Returns live progress for FactoryHub category sync process."""
    import glob
    import re

    candidates = sorted(
        glob.glob("/Users/mac/.gemini/antigravity-ide/brain/*/.system_generated/tasks/task-*.log"),
        key=os.path.getmtime,
        reverse=True
    )
    target_file = None
    for f in candidates:
        try:
            with open(f, "r", errors="ignore") as fp:
                content_sample = fp.read(400)
                if "FactoryHub" in content_sample and "kategori" in content_sample:
                    target_file = f
                    break
        except Exception:
            continue

    if not target_file:
        return {"active": False, "message": "Tidak ada proses sinkronisasi aktif."}

    try:
        with open(target_file, "r", errors="ignore") as fp:
            lines = fp.readlines()

        current = 0
        total = 475
        current_part = "-"
        updated = 0
        skipped = 0
        failed = 0
        is_finished = False

        for line in lines:
            if "Berhasil diupdate di FactoryHub!" in line:
                updated += 1
            elif "[OK]" in line:
                skipped += 1
            elif "[ERROR]" in line or "[FAIL]" in line:
                failed += 1
            elif "RINGKASAN SINKRONISASI KATEGORI FACTORYHUB" in line:
                is_finished = True

            m = re.search(r'\[(\d+)/(\d+)\]\s*\[(.*?)\]\s*(.*?):', line)
            if m:
                current = int(m.group(1))
                total = int(m.group(2))
                current_part = m.group(4).strip()

        percent = round((current / total * 100), 1) if total > 0 else 0

        return {
            "active": not is_finished,
            "is_finished": is_finished,
            "current": current,
            "total": total,
            "percent": percent,
            "current_part": current_part,
            "updated": updated,
            "skipped": skipped,
            "failed": failed,
            "recent_logs": [l.strip() for l in lines[-12:] if l.strip()]
        }
    except Exception as e:
        return {"active": False, "error": str(e)}

