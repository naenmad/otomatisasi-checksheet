"""
FastAPI Server Launcher for Summit FactoryHub Checksheet Automation.
Run this script to start the web dashboard for the team:
    python run_server.py
"""
import os
import sys
import uvicorn

# Ensure project root is in sys.path
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

if __name__ == "__main__":
    port = int(os.getenv("PORT", 8000))
    host = os.getenv("HOST", "0.0.0.0")
    print(f"[*] Starting Summit FactoryHub Checksheet Server on http://{host}:{port}")
    uvicorn.run("server.main:app", host=host, port=port, reload=True)
