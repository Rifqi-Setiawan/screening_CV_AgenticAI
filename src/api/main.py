"""FastAPI entry point for the TIG recruitment workflow."""

from __future__ import annotations

import contextlib
from collections.abc import AsyncGenerator
from pathlib import Path

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from src.api.middleware.tig_body_limit import TigBodyLimit
from src.api.routes import applicant, auth, health, jobs, metrics, tig
from src.infrastructure.config import settings
from src.infrastructure.database import close_db_pool, get_db_pool


@contextlib.asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    if settings.APP_ENV == "test":
        yield
        return
    await get_db_pool()
    try:
        yield
    finally:
        await close_db_pool()


app = FastAPI(title="Rekrutmen TIG", version="1.0.0", lifespan=lifespan)

app.add_middleware(TigBodyLimit)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "PATCH", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type"],
)

app.include_router(health.router)
app.include_router(auth.router)
app.include_router(applicant.router)
app.include_router(jobs.router)
app.include_router(metrics.router)
app.include_router(tig.router)

frontend_dist = Path(__file__).resolve().parents[2] / "frontend" / "dist"
if (frontend_dist / "assets").is_dir():
    app.mount("/assets", StaticFiles(directory=frontend_dist / "assets"), name="assets")


@app.get("/favicon.svg", include_in_schema=False)
async def favicon():
    if not (frontend_dist / "favicon.svg").is_file():
        raise HTTPException(404)
    return FileResponse(frontend_dist / "favicon.svg")


@app.get("/", include_in_schema=False)
async def root(request: Request):
    if "text/html" in request.headers.get("accept", ""):
        return await app_ui()
    return {"service": "Rekrutmen TIG", "status": "ONLINE", "documentation": "/docs"}


@app.get("/apply/{job_id}", include_in_schema=False)
async def applicant_ui(job_id: str):
    return await app_ui()


@app.get("/pelamar", include_in_schema=False)
async def applicant_portal_ui():
    return await app_ui()


@app.get("/app", include_in_schema=False)
async def app_ui():
    if not (frontend_dist / "index.html").is_file():
        raise HTTPException(503, "Frontend TIG belum dibangun.")
    return FileResponse(frontend_dist / "index.html")
