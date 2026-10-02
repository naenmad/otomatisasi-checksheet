"""
version.py - Version and Build metadata for Otomatisasi Checksheet.
"""
import os
import subprocess
import time

VERSION = "1.5.0"
APP_NAME = "Summit Automation Engine"
SERVER_BOOT_TIME = int(time.time())


_cached_commit = None
_cached_date = None


def get_git_commit() -> str:
    """Return short git commit hash or 'release'."""
    global _cached_commit
    if _cached_commit is not None:
        return _cached_commit
    try:
        repo_dir = os.path.dirname(os.path.abspath(__file__))
        commit = subprocess.check_output(
            ["git", "rev-parse", "--short", "HEAD"],
            cwd=repo_dir,
            stderr=subprocess.DEVNULL,
            timeout=2
        ).decode("utf-8", errors="ignore").strip()
        if commit:
            _cached_commit = commit
            return _cached_commit
    except Exception:
        pass
    _cached_commit = "release"
    return _cached_commit


def get_git_date() -> str:
    """Return latest commit date."""
    global _cached_date
    if _cached_date is not None:
        return _cached_date
    try:
        repo_dir = os.path.dirname(os.path.abspath(__file__))
        date = subprocess.check_output(
            ["git", "log", "-1", "--format=%cd", "--date=short"],
            cwd=repo_dir,
            stderr=subprocess.DEVNULL,
            timeout=2
        ).decode("utf-8", errors="ignore").strip()
        if date:
            _cached_date = date
            return _cached_date
    except Exception:
        pass
    _cached_date = ""
    return _cached_date


def get_version_banner() -> str:
    """Return formatted version banner for logs, e.g. 'v1.5.0 (git: 8cc350b | 2026-09-29)'."""
    commit = get_git_commit()
    date = get_git_date()
    if date:
        return f"v{VERSION} (git: {commit} | {date})"
    return f"v{VERSION} (git: {commit})"


def get_full_banner() -> str:
    """Return full banner including app name."""
    return f"{APP_NAME} {get_version_banner()}"
