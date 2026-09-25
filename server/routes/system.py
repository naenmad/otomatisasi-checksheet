"""
System maintenance, Git version control, and auto-update API router.
"""
import os
import subprocess
from datetime import datetime
from fastapi import APIRouter, HTTPException

router = APIRouter(prefix="/api/system", tags=["System"])


def run_git_cmd(args: list) -> str:
    """Run git command in project root."""
    cwd = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    result = subprocess.run(
        ["git"] + args,
        cwd=cwd,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        timeout=15
    )
    if result.returncode != 0:
        err = result.stderr.strip() or result.stdout.strip()
        raise RuntimeError(f"Git command failed ({' '.join(args)}): {err}")
    return result.stdout.strip()


@router.get("/update-status")
def get_update_status():
    """Check if remote origin/main has newer commits."""
    try:
        current_commit = run_git_cmd(["rev-parse", "--short", "HEAD"])
        current_branch = run_git_cmd(["rev-parse", "--abbrev-ref", "HEAD"])
        
        # Fetch remote silently
        try:
            run_git_cmd(["fetch", "origin", "main"])
        except Exception as e:
            # Network offline or git credential issue
            return {
                "has_update": False,
                "current_commit": current_commit,
                "current_branch": current_branch,
                "remote_commit": current_commit,
                "behind_count": 0,
                "commits_behind": [],
                "error": f"Tidak dapat terhubung ke remote: {str(e)}",
                "checked_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            }

        remote_commit = run_git_cmd(["rev-parse", "--short", "origin/main"])
        count_str = run_git_cmd(["rev-list", "--count", "HEAD..origin/main"])
        behind_count = int(count_str) if count_str.isdigit() else 0

        commits_behind = []
        if behind_count > 0:
            log_output = run_git_cmd(["log", "-n", "10", "--oneline", "HEAD..origin/main"])
            commits_behind = [line.strip() for line in log_output.split("\n") if line.strip()]

        return {
            "has_update": behind_count > 0,
            "current_commit": current_commit,
            "current_branch": current_branch,
            "remote_commit": remote_commit,
            "behind_count": behind_count,
            "commits_behind": commits_behind,
            "checked_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        }
    except Exception as e:
        return {
            "has_update": False,
            "error": str(e),
            "checked_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        }


@router.post("/update")
def execute_system_update():
    """Pull latest code from origin/main."""
    try:
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
