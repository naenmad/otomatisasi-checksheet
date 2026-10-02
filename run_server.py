"""
FastAPI Server Launcher for Summit FactoryHub Checksheet Automation.
Run this script to start the web dashboard for the team:
    python run_server.py
"""
import os
import sys
import asyncio
import uvicorn

# Ensure stdout and stderr handle UTF-8 cleanly without charmap codec errors on Windows
if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass
if hasattr(sys.stderr, "reconfigure"):
    try:
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

# On Windows, Playwright requires ProactorEventLoop and cannot run with uvicorn reload=True.
if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())

# Ensure project root and core/ are in sys.path
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
CORE_DIR = os.path.join(BASE_DIR, "core")
for p in (BASE_DIR, CORE_DIR):
    if p not in sys.path:
        sys.path.insert(0, p)

def ensure_port_available(port: int):
    """Clean up any leftover process listening on the target port before starting uvicorn."""
    try:
        import subprocess
        import time
        if sys.platform != "win32":
            output = subprocess.check_output(["lsof", "-ti", f":{port}"], stderr=subprocess.DEVNULL).decode().strip()
            current_pid = str(os.getpid())
            killed = False
            for pid_str in output.split():
                if pid_str and pid_str != current_pid:
                    try:
                        os.kill(int(pid_str), 9)
                        print(f"[*] Cleared previous process on port {port} (PID: {pid_str})")
                        killed = True
                    except OSError:
                        pass
            if killed:
                time.sleep(0.6)
    except Exception:
        pass

if __name__ == "__main__":
    port = int(os.getenv("PORT", 8000))
    host = os.getenv("HOST", "0.0.0.0")
    
    # Reload causes NotImplementedError with Playwright subprocess on Windows
    is_windows = sys.platform == "win32"
    default_reload = "false" if is_windows else "true"
    reload_enabled = os.getenv("RELOAD", default_reload).lower() in ("true", "1")
    
    ensure_port_available(port)
    print(f"[*] Starting Summit FactoryHub Checksheet Server on http://{host}:{port} (reload={reload_enabled})")
    uvicorn.run("server.main:app", host=host, port=port, reload=reload_enabled)
