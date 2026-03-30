"""src/api/routes/admin.py — Admin-only endpoints.

Provides administrative controls for the Gaitway system:
  - System statistics (shoe count, image count, user count, storage usage)
  - User management (list users, toggle active status)
  - Scraper control (trigger crawl jobs)
  - Alembic migration status

All endpoints require admin-level authentication (Phase 6 Cognito integration).

Endpoints
---------
GET  /api/v1/admin/stats                system-wide statistics
GET  /api/v1/admin/users                list all users (paginated)
GET  /api/v1/admin/db-status            Alembic migration status
POST /api/v1/admin/scraper/trigger      trigger a scrape job
GET  /api/v1/admin/scraper/sites        list configured scraper sites
"""

from __future__ import annotations

import logging
import os
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException, Query, status
from pydantic import BaseModel, ConfigDict

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/api/v1/admin",
    tags=["admin"],
)


# ─────────────────────────────────────────────────────────────
# Response / Request Models
# ─────────────────────────────────────────────────────────────


class SystemStatsResponse(BaseModel):
    """System-wide statistics for the admin dashboard."""

    total_shoes: int = 0
    total_shoe_images: int = 0
    total_users: int = 0
    total_workspaces: int = 0
    total_crime_scene_queries: int = 0
    active_subscriptions: int = 0
    scraper_sites_configured: int = 0
    db_connected: bool = False
    s3_bucket: Optional[str] = None


class UserSummary(BaseModel):
    """Summary of a user record for the admin user list."""

    id: int
    email: str
    cognito_sub: Optional[str] = None
    is_active: bool
    subscription_status: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)


class UserListResponse(BaseModel):
    """Paginated list of users."""

    items: List[UserSummary]
    total: int
    page: int
    page_size: int


class ScraperTriggerRequest(BaseModel):
    """Request body for triggering a scrape job."""

    site: str  # e.g. "zappos", "amazon", "dsw"
    max_pages: Optional[int] = None
    category: Optional[str] = None
    dry_run: bool = False  # if True, scrape but don't persist to DB


class ScraperTriggerResponse(BaseModel):
    """Response after triggering a scrape job."""

    job_id: str
    site: str
    status: str
    message: str


class DbStatusResponse(BaseModel):
    """Alembic migration status."""

    current_revision: Optional[str]
    head_revision: Optional[str]
    is_up_to_date: bool
    pending_migrations: List[str]


class ScraperSiteInfo(BaseModel):
    """Information about a configured scraper site."""

    site: str
    enabled: bool
    base_url: str
    rate_limit_per_second: float
    max_pages: int
    categories: List[str]


# ─────────────────────────────────────────────────────────────
# Endpoints
# ─────────────────────────────────────────────────────────────


@router.get("/stats", response_model=SystemStatsResponse)
async def get_stats():
    """Return system-wide statistics for the admin dashboard.

    Includes shoe/image counts, user/subscription counts, and
    infrastructure health indicators.

    .. note::
        Live DB queries wired in Phase 6.  Returns placeholder
        counts in Phase 1.
    """
    from src.config import get_config
    from src.db.connection import ping_db

    cfg = get_config()
    db_ok = False
    try:
        db_ok = ping_db()
    except Exception:  # noqa: BLE001
        pass

    # TODO (Phase 6): replace with live DB aggregate queries
    return SystemStatsResponse(
        total_shoes=0,
        total_shoe_images=0,
        total_users=0,
        total_workspaces=0,
        total_crime_scene_queries=0,
        active_subscriptions=0,
        scraper_sites_configured=1,  # Zappos is Phase 0.5
        db_connected=db_ok,
        s3_bucket=cfg.s3_bucket,
    )


@router.get("/users", response_model=UserListResponse)
async def list_users(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    active_only: bool = Query(False),
):
    """Return a paginated list of all Gaitway users (admin only).

    .. note::
        Live DB queries wired in Phase 6.
    """
    # TODO (Phase 6): live DB query
    logger.info("list_users page=%d active_only=%s", page, active_only)
    return UserListResponse(items=[], total=0, page=page, page_size=page_size)


@router.get("/db-status", response_model=DbStatusResponse)
async def get_db_status():
    """Return Alembic migration status.

    Checks the current database revision against the head revision
    to determine if any migrations are pending.

    Raises:
        HTTPException 503: if the database is unreachable.
    """
    try:
        from alembic.config import Config as AlembicConfig
        from alembic.runtime.migration import MigrationContext
        from alembic.script import ScriptDirectory
        from src.db.connection import get_engine

        cfg = AlembicConfig("alembic.ini")
        script = ScriptDirectory.from_config(cfg)
        engine = get_engine()

        with engine.connect() as conn:
            ctx = MigrationContext.configure(conn)
            current_rev = ctx.get_current_revision()

        head_rev = script.get_current_head()
        all_revisions = [s.revision for s in script.walk_revisions()]
        # Revisions after current
        pending: List[str] = []
        if current_rev != head_rev:
            for rev in reversed(all_revisions):
                if rev == current_rev:
                    break
                pending.append(rev)

        return DbStatusResponse(
            current_revision=current_rev,
            head_revision=head_rev,
            is_up_to_date=(current_rev == head_rev),
            pending_migrations=pending,
        )
    except Exception as exc:  # noqa: BLE001
        logger.error("db-status check failed: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Database status check failed: {exc}",
        ) from exc


@router.post("/scraper/trigger", response_model=ScraperTriggerResponse)
async def trigger_scraper(body: ScraperTriggerRequest):
    """Trigger a scrape job for a specific retailer site.

    In production this enqueues an EventBridge / SQS task.  In Phase 1
    it validates the site name and returns a placeholder job ID.

    Args:
        body: Site name, optional category/page limits, dry_run flag.

    Returns:
        ScraperTriggerResponse with job_id and status.

    Raises:
        HTTPException 400: if the site name is not configured.
    """
    supported_sites = ["zappos"]  # TODO: expand as more scrapers are added

    if body.site.lower() not in supported_sites:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                f"Site {body.site!r} not supported. "
                f"Supported sites: {supported_sites}"
            ),
        )

    import uuid

    job_id = uuid.uuid4().hex
    logger.info(
        "trigger_scraper site=%s max_pages=%s dry_run=%s job_id=%s",
        body.site,
        body.max_pages,
        body.dry_run,
        job_id,
    )

    # TODO (Phase 3): enqueue actual scraper job via EventBridge/SQS
    return ScraperTriggerResponse(
        job_id=job_id,
        site=body.site,
        status="queued",
        message=(
            f"Scrape job queued for {body.site!r} "
            f"(dry_run={body.dry_run}). "
            "Full EventBridge integration in Phase 3."
        ),
    )


@router.get("/scraper/sites", response_model=List[ScraperSiteInfo])
async def list_scraper_sites():
    """Return the list of configured scraper sites from config/scrapers.yaml.

    Returns:
        List of ScraperSiteInfo with site config details.
    """
    import yaml

    config_path = os.path.join(
        os.path.dirname(__file__), "..", "..", "..", "config", "scrapers.yaml"
    )
    config_path = os.path.abspath(config_path)

    try:
        with open(config_path) as f:
            raw = yaml.safe_load(f)
    except FileNotFoundError:
        logger.warning("config/scrapers.yaml not found at %s", config_path)
        return []
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to load scrapers.yaml: {exc}",
        ) from exc

    sites: List[ScraperSiteInfo] = []
    for site_name, site_cfg in raw.get("scrapers", {}).items():
        sites.append(
            ScraperSiteInfo(
                site=site_name,
                enabled=site_cfg.get("enabled", False),
                base_url=site_cfg.get("base_url", ""),
                rate_limit_per_second=site_cfg.get("rate_limit_per_second", 1.0),
                max_pages=site_cfg.get("max_pages", 10),
                categories=site_cfg.get("categories", []),
            )
        )
    return sites
