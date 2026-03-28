"""src/api/routes/upload.py — Image upload endpoints.

Provides S3 pre-signed URL generation and direct upload helpers for:
  - Shoe catalog images (retailer product photos)
  - Crime scene footwear impression images

Endpoints
---------
POST /api/v1/upload/presign-shoe        get a pre-signed PUT URL for a shoe image
POST /api/v1/upload/presign-crime-scene get a pre-signed PUT URL for a crime scene image
POST /api/v1/upload/shoe-image          direct upload (multipart form) of a shoe image

Notes
-----
Pre-signed URLs are the preferred pattern: the client uploads directly to S3,
bypassing the API server.  Direct upload is provided for server-side use
(e.g. the scraper uploading via API).

Authentication: full Cognito JWT + subscription check added in Phase 6.
"""

from __future__ import annotations

import logging
import os
import uuid
from typing import Optional

import boto3
from botocore.exceptions import BotoCoreError, ClientError
from fastapi import APIRouter, HTTPException, UploadFile, status
from pydantic import BaseModel

from src.config import get_config

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/api/v1/upload",
    tags=["upload"],
)

# Pre-signed URL TTL (1 hour)
_PRESIGN_EXPIRY = 3600


# ─────────────────────────────────────────────────────────────
# Response / Request Models
# ─────────────────────────────────────────────────────────────


class PresignRequest(BaseModel):
    """Request body for generating a pre-signed upload URL."""

    filename: str
    content_type: str = "image/jpeg"
    shoe_id: Optional[int] = None
    image_type: str = "unknown"  # upper | sole | unknown


class PresignResponse(BaseModel):
    """Response containing a pre-signed S3 PUT URL."""

    upload_url: str
    s3_key: str
    expires_in_seconds: int = _PRESIGN_EXPIRY
    bucket: str


class DirectUploadResponse(BaseModel):
    """Response after a successful direct image upload."""

    s3_key: str
    bucket: str
    content_type: str
    size_bytes: int


# ─────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────


def _get_s3_client():
    """Return a configured boto3 S3 client."""
    cfg = get_config()
    return boto3.client(
        "s3",
        region_name=cfg.aws_region,
    )


def _build_shoe_s3_key(filename: str, shoe_id: Optional[int], image_type: str) -> str:
    """Build an S3 key for a shoe image under the raw/ prefix."""
    cfg = get_config()
    prefix = cfg.s3_raw_prefix.rstrip("/")
    uid = uuid.uuid4().hex
    ext = os.path.splitext(filename)[-1].lower() or ".jpg"
    if shoe_id:
        return f"{prefix}/shoes/{shoe_id}/{image_type}/{uid}{ext}"
    return f"{prefix}/shoes/unknown/{image_type}/{uid}{ext}"


def _build_crime_scene_s3_key(filename: str) -> str:
    """Build an S3 key for a crime scene image under the crime-scene/ prefix."""
    cfg = get_config()
    prefix = cfg.s3_crime_scene_prefix.rstrip("/")
    uid = uuid.uuid4().hex
    ext = os.path.splitext(filename)[-1].lower() or ".jpg"
    return f"{prefix}/{uid}{ext}"


# ─────────────────────────────────────────────────────────────
# Endpoints
# ─────────────────────────────────────────────────────────────


@router.post("/presign-shoe", response_model=PresignResponse)
async def presign_shoe_upload(body: PresignRequest):
    """Generate a pre-signed S3 PUT URL for uploading a shoe image.

    The client uses this URL to upload the image directly to S3 (bypassing
    the API server).  After the upload completes, the client should call
    the shoe images endpoint to persist the S3 key in the database.

    Args:
        body: Filename, content type, optional shoe_id, image type.

    Returns:
        PresignResponse with upload_url and s3_key.

    Raises:
        HTTPException 503: if S3 is unreachable or misconfigured.
    """
    cfg = get_config()
    if not cfg.s3_bucket:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="S3 bucket not configured",
        )

    s3_key = _build_shoe_s3_key(body.filename, body.shoe_id, body.image_type)

    try:
        s3 = _get_s3_client()
        upload_url = s3.generate_presigned_url(
            "put_object",
            Params={
                "Bucket": cfg.s3_bucket,
                "Key": s3_key,
                "ContentType": body.content_type,
            },
            ExpiresIn=_PRESIGN_EXPIRY,
        )
    except (BotoCoreError, ClientError) as exc:
        logger.error("S3 presign failed: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Could not generate upload URL — S3 error",
        ) from exc

    logger.info("presign_shoe_upload s3_key=%s", s3_key)
    return PresignResponse(
        upload_url=upload_url,
        s3_key=s3_key,
        bucket=cfg.s3_bucket,
    )


@router.post("/presign-crime-scene", response_model=PresignResponse)
async def presign_crime_scene_upload(body: PresignRequest):
    """Generate a pre-signed S3 PUT URL for uploading a crime scene impression.

    Args:
        body: Filename and content type.

    Returns:
        PresignResponse with upload_url and s3_key.

    Raises:
        HTTPException 503: if S3 is unreachable or misconfigured.
    """
    cfg = get_config()
    if not cfg.s3_bucket:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="S3 bucket not configured",
        )

    s3_key = _build_crime_scene_s3_key(body.filename)

    try:
        s3 = _get_s3_client()
        upload_url = s3.generate_presigned_url(
            "put_object",
            Params={
                "Bucket": cfg.s3_bucket,
                "Key": s3_key,
                "ContentType": body.content_type,
            },
            ExpiresIn=_PRESIGN_EXPIRY,
        )
    except (BotoCoreError, ClientError) as exc:
        logger.error("S3 presign (crime scene) failed: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Could not generate upload URL — S3 error",
        ) from exc

    logger.info("presign_crime_scene_upload s3_key=%s", s3_key)
    return PresignResponse(
        upload_url=upload_url,
        s3_key=s3_key,
        bucket=cfg.s3_bucket,
    )


@router.post("/shoe-image", response_model=DirectUploadResponse)
async def upload_shoe_image(
    file: UploadFile,
    shoe_id: Optional[int] = None,
    image_type: str = "unknown",
):
    """Directly upload a shoe image (multipart form) — server-side upload path.

    Used by the scraper framework and admin tools.  The file is streamed
    directly to S3 without being saved to disk.

    Args:
        file:       Uploaded image file.
        shoe_id:    Optional shoe ID to associate with.
        image_type: Image type (upper | sole | unknown).

    Returns:
        DirectUploadResponse with s3_key, bucket, and size.

    Raises:
        HTTPException 400: if file is not a valid image.
        HTTPException 503: if S3 is unreachable or misconfigured.
    """
    cfg = get_config()
    if not cfg.s3_bucket:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="S3 bucket not configured",
        )

    if not file.content_type or not file.content_type.startswith("image/"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"File must be an image; got {file.content_type!r}",
        )

    s3_key = _build_shoe_s3_key(file.filename or "upload.jpg", shoe_id, image_type)

    try:
        content = await file.read()
        s3 = _get_s3_client()
        s3.put_object(
            Bucket=cfg.s3_bucket,
            Key=s3_key,
            Body=content,
            ContentType=file.content_type,
        )
    except (BotoCoreError, ClientError) as exc:
        logger.error("S3 put_object failed: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="S3 upload failed",
        ) from exc

    logger.info("upload_shoe_image s3_key=%s size=%d", s3_key, len(content))
    return DirectUploadResponse(
        s3_key=s3_key,
        bucket=cfg.s3_bucket,
        content_type=file.content_type,
        size_bytes=len(content),
    )
