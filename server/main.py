"""
Main FastAPI server entrypoint.
"""
import sys
import asyncio

# Playwright subprocess on Windows requires ProactorEventLoop
if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())
import os
# Ensure project root and core/ are in sys.path
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CORE_DIR = os.path.join(BASE_DIR, "core")
for p in (BASE_DIR, CORE_DIR):
    if p not in sys.path:
        sys.path.insert(0, p)

from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, ORJSONResponse

from database.connection import init_db
from server.routes.checksheets import router as checksheets_router
from server.routes.upload import router as upload_router
from server.routes.automation import router as automation_router
from server.routes.export import router as export_router
from server.routes.auth import router as auth_router
from server.routes.users import router as users_router
from server.routes.catalog import router as catalog_router
from server.routes.system import router as system_router
from server.routes.tools import router as tools_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Initialize database tables on startup
    await init_db()
    os.makedirs("storage/uploads", exist_ok=True)
    os.makedirs("storage/images", exist_ok=True)
    os.makedirs("extracted_images", exist_ok=True)
    os.makedirs("static", exist_ok=True)
    # Warmup checksheets cache in background on startup (< 0ms blocking)
    try:
        from server.routes.checksheets import warmup_checksheets_cache
        asyncio.create_task(warmup_checksheets_cache())
    except Exception:
        pass
    yield


app = FastAPI(
    title="Summit FactoryHub Checksheet Automation",
    description="Sistem Kolaborasi Otomasi Checksheet Tim (Zul, Iqbal, Rama, Yogi)",
    version="2.0.0",
    default_response_class=ORJSONResponse,
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

# Enable GZip compression for ultra-fast payload delivery (HTML, JSON, static assets)
app.add_middleware(GZipMiddleware, minimum_size=1000)

# Include API Routers
app.include_router(auth_router)
app.include_router(users_router)
app.include_router(checksheets_router)
app.include_router(catalog_router)
app.include_router(upload_router)
app.include_router(automation_router)
app.include_router(export_router)
app.include_router(system_router)
app.include_router(tools_router)

class NoCacheStaticFiles(StaticFiles):
    """StaticFiles subclass that enforces Cache-Control: no-cache on all served assets."""
    async def get_response(self, path: str, scope):
        response = await super().get_response(path, scope)
        response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
        response.headers["Pragma"] = "no-cache"
        response.headers["Expires"] = "0"
        return response


# Mount media & static files
if os.path.exists("storage/images"):
    app.mount("/media/images", StaticFiles(directory="storage/images"), name="images")

if os.path.exists("extracted_images"):
    app.mount("/media/extracted", StaticFiles(directory="extracted_images"), name="extracted")

if os.path.exists("static"):
    app.mount("/static", NoCacheStaticFiles(directory="static"), name="static")


@app.middleware("http")
async def add_cache_busting_headers(request, call_next):
    response = await call_next(request)
    path = request.url.path
    if path == "/" or path.startswith("/static") or path.endswith((".html", ".js", ".css")):
        response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
        response.headers["Pragma"] = "no-cache"
        response.headers["Expires"] = "0"
    return response


@app.get("/")
async def root():
    index_file = "static/index.html"
    if os.path.exists(index_file):
        return FileResponse(index_file, headers={"Cache-Control": "no-cache, no-store, must-revalidate", "Pragma": "no-cache", "Expires": "0"})
    return {
        "app": "Summit FactoryHub Checksheet Automation API",
        "version": "2.0.0",
        "docs_url": "/docs",
        "status": "online"
    }


@app.get("/{page:path}")
async def serve_spa(page: str):
    static_file_path = os.path.join("static", page)
    if os.path.isfile(static_file_path):
        media_type = None
        if page.endswith(".webmanifest") or page.endswith(".json"):
            media_type = "application/manifest+json"
        elif page.endswith(".js"):
            media_type = "application/javascript"
        elif page.endswith(".css"):
            media_type = "text/css"
        elif page.endswith(".svg"):
            media_type = "image/svg+xml"
        elif page.endswith(".png"):
            media_type = "image/png"
        elif page.endswith(".ico"):
            media_type = "image/x-icon"
        return FileResponse(static_file_path, media_type=media_type)

    if page.startswith(("api/", "docs", "redoc", "openapi.json", "media/", "static/")):
        return {"detail": "Not Found", "status": 404}
    index_file = "static/index.html"
    if os.path.exists(index_file):
        return FileResponse(index_file, headers={"Cache-Control": "no-cache, no-store, must-revalidate", "Pragma": "no-cache", "Expires": "0"})
    return {"detail": "SPA index file not found", "status": 404}


if __name__ == "__main__":
    import uvicorn
    is_windows = sys.platform == "win32"
    default_reload = "false" if is_windows else "true"
    reload_enabled = os.getenv("RELOAD", default_reload).lower() in ("true", "1")
    uvicorn.run("server.main:app", host="0.0.0.0", port=8000, reload=reload_enabled)
