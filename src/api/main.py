"""src/api/main.py — FastAPI application for Gaitway Footwear Intelligence Database.

Registers all route blueprints and provides core infrastructure endpoints
(health, config-status, version, echo).

API Structure:
  GET  /                     root — endpoint navigation
  GET  /health               health check
  GET  /config-status        configuration readiness (no secrets exposed)
  GET  /version              API version info
  POST /echo                 echo endpoint (testing)

  GET/POST /api/v1/shoes/*         shoe catalog
  POST     /api/v1/crime-scene/*   forensic similarity search
  POST     /api/v1/upload/*        S3 image upload helpers
  GET/POST /api/v1/admin/*         admin stats, users, scraper control
  GET/POST /api/v1/billing/*       Stripe billing + webhook

Usage:
    uvicorn src.api.main:app --reload            # Development
    uvicorn src.api.main:app --host 0.0.0.0 \
      --port 8000 --workers 4                    # Production
"""

import logging
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from typing import Any, Dict, Optional

from fastapi import FastAPI, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from src.config import get_config

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# ─────────────────────────────────────────────────────────────
# FastAPI app
# ─────────────────────────────────────────────────────────────

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifespan context manager — replaces deprecated @app.on_event."""
    # ── Startup ──────────────────────────────────────────────────────────────
    cfg = get_config()
    if cfg.api_key:
        logger.info("✅ API key is configured")
    else:
        logger.warning(
            "⚠️  API_KEY is not configured — running in dev mode (no auth)"
        )
    if cfg.s3_bucket:
        logger.info(
            "✅ S3 bucket configured: %s (region: %s)", cfg.s3_bucket, cfg.aws_region
        )
    else:
        logger.warning("⚠️  S3_BUCKET_NAME is not configured — upload endpoints will fail")
    logger.info("🚀 Gaitway API v0.1.0 started — %d route prefixes registered", 5)
    yield
    # ── Shutdown (add cleanup here if needed) ────────────────────────────────
    logger.info("🛑 Gaitway API shutting down")


app = FastAPI(
    title="Gaitway Footwear Intelligence API",
    version="0.1.0",
    description=(
        "REST API for the Gaitway Footwear Intelligence Database. "
        "Enables forensic crime scene footwear impression search "
        "against a curated shoe catalog using pgvector cosine similarity."
    ),
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json",
    lifespan=lifespan,
)

# ── CORS (restrict in production via ALLOWED_ORIGINS env var) ─────────────────
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],   # TODO (Phase 6): restrict to frontend origin
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ─────────────────────────────────────────────────────────────
# Register route blueprints
# ─────────────────────────────────────────────────────────────

from src.api.routes import (  # noqa: E402
    admin_router,
    crime_scene_router,
    shoes_router,
    stripe_router,
    upload_router,
)

app.include_router(shoes_router)
app.include_router(crime_scene_router)
app.include_router(upload_router)
app.include_router(admin_router)
app.include_router(stripe_router)


# ─────────────────────────────────────────────────────────────
# Core Response Models
# ─────────────────────────────────────────────────────────────


class HealthCheckResponse(BaseModel):
    """Response model for health check endpoint."""

    status: str
    version: str
    api_configured: bool


class ConfigStatusResponse(BaseModel):
    """Response model for config status endpoint (no secrets exposed)."""

    api_key_configured: bool
    aws_region: str
    s3_bucket_configured: bool
    message: str


class ErrorResponse(BaseModel):
    """Standard error response."""

    error: str
    detail: Optional[str] = None


# ─────────────────────────────────────────────────────────────
# Core Endpoints
# ─────────────────────────────────────────────────────────────


@app.get("/health", response_model=HealthCheckResponse, tags=["core"])
async def health_check() -> HealthCheckResponse:
    """Health check endpoint.

    Returns a simple status indicator used by load balancers, Docker
    healthchecks, and uptime monitors.

    Returns:
        HealthCheckResponse with status='ok', API version, and
        a boolean indicating whether the API key is configured.
    """
    cfg = get_config()
    return HealthCheckResponse(
        status="ok",
        version="0.1.0",
        api_configured=bool(cfg.api_key),
    )


@app.get("/config-status", response_model=ConfigStatusResponse, tags=["core"])
async def config_status() -> ConfigStatusResponse:
    """Check configuration readiness without exposing secret values.

    Safe to expose publicly — only indicates whether config is present,
    not the actual values.

    Returns:
        ConfigStatusResponse indicating which parts of the config are set.
    """
    cfg = get_config()
    missing = []
    if not cfg.api_key:
        missing.append("API_KEY")
    if not cfg.s3_bucket:
        missing.append("S3_BUCKET_NAME")

    message = "All configured" if not missing else f"Missing: {', '.join(missing)}"

    return ConfigStatusResponse(
        api_key_configured=bool(cfg.api_key),
        aws_region=cfg.aws_region or "not set",
        s3_bucket_configured=bool(cfg.s3_bucket),
        message=message,
    )


@app.get("/version", tags=["core"])
async def get_version() -> Dict[str, str]:
    """Return API version information."""
    return {
        "version": "0.1.0",
        "name": "Gaitway Footwear Intelligence API",
        "phase": "Phase 1 — Backend Foundation",
    }


@app.post("/echo", tags=["core"])
async def echo(data: Dict[str, Any]) -> Dict[str, Any]:
    """Echo endpoint — reflect back a JSON payload (for testing).

    Args:
        data: Any JSON payload.

    Returns:
        The same data with a UTC timestamp and API version appended.
    """
    return {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "received": data,
        "api_version": "0.1.0",
    }


@app.get("/", tags=["core"])
async def root() -> Dict[str, Any]:
    """Root endpoint — quick navigation to key API sections."""
    return {
        "message": "Gaitway Footwear Intelligence API",
        "version": "0.1.0",
        "phase": "Phase 1 — Backend Foundation",
        "endpoints": {
            "health": "/health",
            "config_status": "/config-status",
            "version": "/version",
            "docs": "/docs",
            "openapi": "/openapi.json",
        },
        "api_routes": {
            "shoes": "/api/v1/shoes",
            "crime_scene": "/api/v1/crime-scene/search",
            "upload": "/api/v1/upload/presign-shoe",
            "admin_stats": "/api/v1/admin/stats",
            "billing_plans": "/api/v1/billing/plans",
        },
    }


# ─────────────────────────────────────────────────────────────
# Global Error Handlers
# ─────────────────────────────────────────────────────────────


@app.exception_handler(ValueError)
async def value_error_handler(request, exc):
    """Handle ValueError — return 400 Bad Request."""
    logger.error("ValueError at %s: %s", request.url, exc)
    return JSONResponse(
        status_code=status.HTTP_400_BAD_REQUEST,
        content={"error": "Invalid value", "detail": str(exc)},
    )


@app.exception_handler(Exception)
async def general_exception_handler(request, exc):
    """Handle all unhandled exceptions — return 500 Internal Server Error."""
    logger.error("Unhandled exception at %s: %s", request.url, exc, exc_info=True)
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={"error": "Internal server error", "detail": str(exc)},
    )


# ─────────────────────────────────────────────────────────────
# Dev server entry point
# ─────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import uvicorn

    cfg = get_config()
    logger.info(
        "🚀 Starting Gaitway API — API_KEY configured: %s | S3: %s",
        bool(cfg.api_key),
        cfg.s3_bucket or "NOT SET",
    )
    uvicorn.run("src.api.main:app", host="0.0.0.0", port=8000, reload=True)
