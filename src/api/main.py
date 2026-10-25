"""Main FastAPI application entry point for CV Screening & Ranking Platform."""

from __future__ import annotations

import contextlib
from collections.abc import AsyncGenerator
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from src.api.routes import auth, candidates, cvs, eligibility, health, jobs, metrics, requirements, screenings
from src.infrastructure.config import settings
from src.infrastructure.database import close_db_pool, get_db_pool
from src.infrastructure.logging import logger


@contextlib.asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    if settings.APP_ENV != "test":
        logger.info(f"Starting CV Screening Platform in {settings.APP_ENV} mode on port {settings.APP_PORT}...")
        await get_db_pool()
        yield
        logger.info("Shutting down CV Screening Platform...")
        await close_db_pool()
    else:
        yield


app = FastAPI(
    title="CV Screening & Ranking Platform API",
    version="1.0.0",
    description="High-precision rule-based & AI-assisted CV evaluation and ranking engine.",
    lifespan=lifespan,
)

# CORS configuration
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type"],
)

# Mount routes
app.include_router(health.router)
app.include_router(auth.router)
app.include_router(jobs.router)
app.include_router(cvs.router)
app.include_router(requirements.router)
app.include_router(requirements.preview_router)
app.include_router(screenings.router)
app.include_router(candidates.router)
app.include_router(eligibility.router)
app.include_router(metrics.router)

frontend_dist = Path("/srv/hermes-control/services/cv-screening/frontend/dist")
if frontend_dist.exists() and (frontend_dist / "assets").exists():
    app.mount("/assets", StaticFiles(directory=str(frontend_dist / "assets")), name="assets")

audit_files_dir = Path("/srv/hermes-control/services/cv-screening/data/audit_public")
if audit_files_dir.exists():
    app.mount("/audit-files", StaticFiles(directory=str(audit_files_dir)), name="audit-files")

    @app.get("/favicon.svg", include_in_schema=False)
    async def favicon():
        return FileResponse(frontend_dist / "favicon.svg")

    @app.get("/icons.svg", include_in_schema=False)
    async def icons():
        return FileResponse(frontend_dist / "icons.svg")


@app.get("/")
async def root(request: Request):
    accept = request.headers.get("accept", "")
    if "text/html" in accept and frontend_dist.exists() and (frontend_dist / "index.html").exists():
        return FileResponse(frontend_dist / "index.html")
    return {
        "service": "CV Screening & Ranking Platform API",
        "status": "ONLINE",
        "version": "1.0.0",
        "documentation": "/docs",
    }


@app.get("/app", include_in_schema=False)
async def app_ui():
    if frontend_dist.exists() and (frontend_dist / "index.html").exists():
        return FileResponse(frontend_dist / "index.html")
    return {"message": "Frontend not built yet"}
