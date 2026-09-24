"""
FastAPI Server Launcher for Summit FactoryHub Checksheet Automation.
Run this script to start the web dashboard for the team:
    python run_server.py
"""
import os
import sys
import asyncio
import uvicorn

# On Windows, Playwright requires ProactorEventLoop and cannot run with uvicorn reload=True.
if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())

# Ensure project root is in sys.path
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

if __name__ == "__main__":
    port = int(os.getenv("PORT", 8000))
    host = os.getenv("HOST", "0.0.0.0")
    
    # Reload causes NotImplementedError with Playwright subprocess on Windows
    is_windows = sys.platform == "win32"
    default_reload = "false" if is_windows else "true"
    reload_enabled = os.getenv("RELOAD", default_reload).lower() in ("true", "1")
    
    print(f"[*] Starting Summit FactoryHub Checksheet Server on http://{host}:{port} (reload={reload_enabled})")
    uvicorn.run("server.main:app", host=host, port=port, reload=reload_enabled)
