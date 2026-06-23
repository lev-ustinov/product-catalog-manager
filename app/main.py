"""
Product Catalog Manager — main application entry point.
"""

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Depends, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse

from database import engine, get_db
from routers import category, product, enums, params, xo
from routers import users, dashboard, export, audit as audit_router
from auth import router as auth_router, verify_token
import models

logger = logging.getLogger(__name__)


# ── Suppress /health from access log (healthcheck noise) ─────────────────────

class _SuppressHealthcheck(logging.Filter):
    """Drop uvicorn access-log records for GET /health."""
    def filter(self, record: logging.LogRecord) -> bool:
        msg = record.getMessage()
        return "GET /health" not in msg


logging.getLogger("uvicorn.access").addFilter(_SuppressHealthcheck())


# ── Startup ───────────────────────────────────────────────────────────────────

@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    On startup: create any tables that don't exist yet (idempotent).
    Covers app_user and audit_log which are NOT in the legacy init.sql.
    Running 'alembic upgrade head' is still recommended for production
    and is done automatically by entrypoint.sh inside Docker.
    """
    try:
        models.Base.metadata.create_all(bind=engine)
        logger.info("Database tables verified / created.")
    except Exception as exc:
        logger.error("create_all failed: %s — check DATABASE_URL in .env", exc)
    yield


# ── Application ───────────────────────────────────────────────────────────────

app = FastAPI(
    title="Product Catalog Manager API",
    version="3.0.0",
    description=(
        "REST API for managing a hierarchical product catalog with "
        "configurable parameters, business operations (XO), analytics, "
        "and full audit trail. "
        "Authenticate via POST /auth/login to receive a JWT token."
    ),
    contact={"name": "Product Catalog Manager"},
    license_info={"name": "MIT"},
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Routers ───────────────────────────────────────────────────────────────────
app.include_router(auth_router)
app.include_router(category.router)
app.include_router(product.router)
app.include_router(enums.router)
app.include_router(params.router)
app.include_router(xo.router)
app.include_router(users.router)
app.include_router(dashboard.router)
app.include_router(export.router)
app.include_router(audit_router.router)


# ── Utility endpoints ─────────────────────────────────────────────────────────

@app.get(
    "/health",
    tags=["ops"],
    summary="Healthcheck",
    description="Used by Docker / load-balancers. Returns 200 if the server is up. Not logged.",
    include_in_schema=False,   # hide from Swagger — noise
)
def health():
    return {"status": "ok"}


@app.get("/", tags=["root"], summary="API info")
def root():
    return {
        "service": "Product Catalog Manager API",
        "version": "3.0.0",
        "docs": "/docs",
        "ui": "/ui",
        "status": "running",
    }


@app.get("/api/me", tags=["auth"], summary="Current user info")
def get_current_user(role: str = Depends(verify_token)):
    return {"role": role}


@app.get("/ui", tags=["frontend"], summary="Serve SPA frontend")
async def get_ui():
    return FileResponse("index.html")
