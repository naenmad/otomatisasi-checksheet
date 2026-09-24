"""
Main FastAPI server entrypoint.
"""
import sys
import asyncio

# Playwright subprocess on Windows requires ProactorEventLoop
if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())
import os
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse

from database.connection import init_db
from server.routes.checksheets import router as checksheets_router
from server.routes.upload import router as upload_router
from server.routes.automation import router as automation_router
from server.routes.export import router as export_router
from server.routes.auth import router as auth_router
from server.routes.users import router as users_router
from server.routes.catalog import router as catalog_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Initialize database tables on startup
    await init_db()
    os.makedirs("storage/uploads", exist_ok=True)
    os.makedirs("storage/images", exist_ok=True)
    os.makedirs("extracted_images", exist_ok=True)
    os.makedirs("static", exist_ok=True)
    yield


app = FastAPI(
    title="Summit FactoryHub Checksheet Automation",
    description="Sistem Kolaborasi Otomasi Checksheet Tim (Zul, Iqbal, Rama, Yogi)",
    version="2.0.0",
    lifespan=lifespan
)

# Enable CORS for local dev / cross-origin
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include API Routers
app.include_router(auth_router)
app.include_router(users_router)
app.include_router(checksheets_router)
app.include_router(catalog_router)
app.include_router(upload_router)
app.include_router(automation_router)
app.include_router(export_router)

# Mount media & static files
if os.path.exists("storage/images"):
    app.mount("/media/images", StaticFiles(directory="storage/images"), name="images")

if os.path.exists("extracted_images"):
    app.mount("/media/extracted", StaticFiles(directory="extracted_images"), name="extracted")

if os.path.exists("static"):
    app.mount("/static", StaticFiles(directory="static"), name="static")


@app.get("/")
async def root():
    index_file = "static/index.html"
    if os.path.exists(index_file):
        return FileResponse(index_file)
    return {
        "app": "Summit FactoryHub Checksheet Automation API",
        "version": "2.0.0",
        "docs_url": "/docs",
        "status": "online"
    }


@app.get("/{page:path}")
async def serve_spa(page: str):
    if page.startswith(("api/", "docs", "redoc", "openapi.json", "media/", "static/")):
        return {"detail": "Not Found", "status": 404}
    index_file = "static/index.html"
    if os.path.exists(index_file):
        return FileResponse(index_file)
    return {"detail": "SPA index file not found", "status": 404}


if __name__ == "__main__":
    import uvicorn
    is_windows = sys.platform == "win32"
    default_reload = "false" if is_windows else "true"
    reload_enabled = os.getenv("RELOAD", default_reload).lower() in ("true", "1")
    uvicorn.run("server.main:app", host="0.0.0.0", port=8000, reload=reload_enabled)
