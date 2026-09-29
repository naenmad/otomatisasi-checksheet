"""
version.py - Version and Build metadata for Otomatisasi Checksheet.
"""
import os
import subprocess

VERSION = "1.5.0"
APP_NAME = "Summit Automation Engine"


def get_git_commit() -> str:
    """Return short git commit hash or 'release'."""
    try:
        repo_dir = os.path.dirname(os.path.abspath(__file__))
        commit = subprocess.check_output(
            ["git", "rev-parse", "--short", "HEAD"],
            cwd=repo_dir,
            stderr=subprocess.DEVNULL,
            timeout=2
        ).decode("utf-8", errors="ignore").strip()
        if commit:
            return commit
    except Exception:
        pass
    return "release"


def get_git_date() -> str:
    """Return latest commit date."""
    try:
        repo_dir = os.path.dirname(os.path.abspath(__file__))
        date = subprocess.check_output(
            ["git", "log", "-1", "--format=%cd", "--date=short"],
            cwd=repo_dir,
            stderr=subprocess.DEVNULL,
            timeout=2
        ).decode("utf-8", errors="ignore").strip()
        if date:
            return date
    except Exception:
        pass
    return ""


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
