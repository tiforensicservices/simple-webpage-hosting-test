"""src/api/routes/shoes.py — Shoe catalog endpoints.

Provides read access to the scraped shoe database and admin write
operations (create / delete).  These endpoints are the primary data
layer for the React frontend's shoe-browser component.

Endpoints
---------
GET  /api/v1/shoes                     list shoes (paginated, filterable)
GET  /api/v1/shoes/{shoe_id}           get a single shoe by ID
GET  /api/v1/shoes/{shoe_id}/images    list images for a shoe
POST /api/v1/shoes                     create a shoe record (admin)
DELETE /api/v1/shoes/{shoe_id}         delete a shoe record (admin)

Authentication: API key required (full Cognito JWT auth added in Phase 6).
"""

from __future__ import annotations

import logging
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/api/v1/shoes",
    tags=["shoes"],
)


# ─────────────────────────────────────────────────────────────
# Response / Request Models
# ─────────────────────────────────────────────────────────────


class ShoeImageResponse(BaseModel):
    """Slim image record returned nested inside ShoeResponse."""

    id: int
    image_type: str
    s3_raw_key: Optional[str] = None
    s3_thumbnail_key: Optional[str] = None
    s3_impression_key: Optional[str] = None
    phash: Optional[str] = None
    width: Optional[int] = None
    height: Optional[int] = None

    class Config:
        from_attributes = True


class ShoeResponse(BaseModel):
    """Full shoe record response."""

    id: int
    external_site: str
    external_id: str
    brand: str
    model_name: str
    category: Optional[str] = None
    gender: Optional[str] = None
    colorway: Optional[str] = None
    price: Optional[float] = None
    description: Optional[str] = None
    product_url: Optional[str] = None
    images: List[ShoeImageResponse] = []

    class Config:
        from_attributes = True


class ShoeListResponse(BaseModel):
    """Paginated list of shoes."""

    items: List[ShoeResponse]
    total: int
    page: int
    page_size: int
    pages: int


class ShoeCreateRequest(BaseModel):
    """Request body for creating a shoe record (admin only)."""

    external_site: str
    external_id: str
    brand: str
    model_name: str
    category: Optional[str] = None
    gender: Optional[str] = None
    colorway: Optional[str] = None
    price: Optional[float] = None
    description: Optional[str] = None
    product_url: Optional[str] = None


# ─────────────────────────────────────────────────────────────
# Endpoints
# ─────────────────────────────────────────────────────────────


@router.get("", response_model=ShoeListResponse)
async def list_shoes(
    page: int = Query(1, ge=1, description="Page number (1-based)"),
    page_size: int = Query(20, ge=1, le=100, description="Items per page"),
    brand: Optional[str] = Query(None, description="Filter by brand (case-insensitive)"),
    site: Optional[str] = Query(None, description="Filter by external_site (e.g. zappos)"),
    gender: Optional[str] = Query(None, description="Filter by gender"),
    category: Optional[str] = Query(None, description="Filter by category"),
):
    """Return a paginated, filterable list of shoes.

    Supports filtering by brand, retailer site, gender, and category.
    Results are ordered by newest first (created_at DESC).

    .. note::
        Database queries are wired in Phase 6 when the DB session
        dependency is fully integrated.  This endpoint returns a
        placeholder response in Phase 1.
    """
    # TODO (Phase 6): replace with live DB query via get_db()
    logger.info(
        "list_shoes page=%d page_size=%d brand=%s site=%s",
        page,
        page_size,
        brand,
        site,
    )
    return ShoeListResponse(
        items=[],
        total=0,
        page=page,
        page_size=page_size,
        pages=0,
    )


@router.get("/{shoe_id}", response_model=ShoeResponse)
async def get_shoe(shoe_id: int):
    """Return a single shoe record by ID.

    Raises:
        HTTPException 404: if no shoe with the given ID exists.
    """
    # TODO (Phase 6): replace with live DB query
    logger.info("get_shoe shoe_id=%d", shoe_id)
    raise HTTPException(
        status_code=status.HTTP_404_NOT_FOUND,
        detail=f"Shoe {shoe_id} not found",
    )


@router.get("/{shoe_id}/images", response_model=List[ShoeImageResponse])
async def list_shoe_images(shoe_id: int):
    """Return all images associated with a shoe.

    Raises:
        HTTPException 404: if no shoe with the given ID exists.
    """
    # TODO (Phase 6): replace with live DB query
    logger.info("list_shoe_images shoe_id=%d", shoe_id)
    raise HTTPException(
        status_code=status.HTTP_404_NOT_FOUND,
        detail=f"Shoe {shoe_id} not found",
    )


@router.post("", response_model=ShoeResponse, status_code=status.HTTP_201_CREATED)
async def create_shoe(body: ShoeCreateRequest):
    """Create a new shoe record (admin).

    Used by the scraper framework to persist new shoe products.  In the
    full system this endpoint requires an admin-level Cognito JWT.

    Raises:
        HTTPException 409: if a shoe with the same site + external_id already exists.
    """
    # TODO (Phase 6): insert into DB, check unique constraint
    logger.info(
        "create_shoe site=%s external_id=%s",
        body.external_site,
        body.external_id,
    )
    raise HTTPException(
        status_code=status.HTTP_501_NOT_IMPLEMENTED,
        detail="Database integration pending (Phase 6)",
    )


@router.delete("/{shoe_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_shoe(shoe_id: int):
    """Delete a shoe record and all associated images (admin).

    Raises:
        HTTPException 404: if no shoe with the given ID exists.
    """
    # TODO (Phase 6): soft-delete or hard-delete from DB
    logger.info("delete_shoe shoe_id=%d", shoe_id)
    raise HTTPException(
        status_code=status.HTTP_501_NOT_IMPLEMENTED,
        detail="Database integration pending (Phase 6)",
    )
