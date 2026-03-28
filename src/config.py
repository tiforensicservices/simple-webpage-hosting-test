"""config.py — Centralized environment configuration helpers.

This module loads environment variables from a `.env` file (for local
development), canonicalizes common secret names (e.g. `API_Key` →
`API_KEY`) and exposes a small `Config` dataclass plus helper accessors.

Usage:
    from src.config import get_config
    cfg = get_config()
    api_key = cfg.api_key

Notes:
  - This module does NOT print or log secrets.
  - It prefers `API_KEY` but will canonicalize `API_Key` if present.
  - For production, prefer platform secrets (env vars, secrets manager).
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Optional

from dotenv import load_dotenv

# Load .env (local dev). Do not override real environment variables unless
# they are empty — keep behavior consistent with other scripts in the repo.
load_dotenv(override=False)


# Canonicalize non-standard names to a standard `API_KEY` env var.
# If the user accidentally used `API_Key` (mixed case), promote it to
# `API_KEY` but do not delete the original entry.
if "API_Key" in os.environ and "API_KEY" not in os.environ:
    os.environ["API_KEY"] = os.environ["API_Key"]


def _get_api_key() -> Optional[str]:
    """Return the configured API key or None if missing."""
    return os.environ.get("API_KEY")


@dataclass(frozen=True)
class Config:
    api_key: Optional[str]
    aws_region: str
    s3_bucket: Optional[str]
    s3_raw_prefix: str
    s3_processed_prefix: str
    s3_impressions_prefix: str
    s3_thumbnails_prefix: str
    s3_crime_scene_prefix: str
    s3_user_shoes_prefix: str


def get_config() -> Config:
    """Build and return the `Config` object from environment variables."""
    return Config(
        api_key=_get_api_key(),
        aws_region=os.getenv("AWS_DEFAULT_REGION", "us-east-1"),
        s3_bucket=os.getenv("S3_BUCKET_NAME"),
        s3_raw_prefix=os.getenv("S3_RAW_PREFIX", "raw/"),
        s3_processed_prefix=os.getenv("S3_PROCESSED_PREFIX", "processed/"),
        s3_impressions_prefix=os.getenv("S3_IMPRESSIONS_PREFIX", "impressions/"),
        s3_thumbnails_prefix=os.getenv("S3_THUMBNAILS_PREFIX", "thumbnails/"),
        s3_crime_scene_prefix=os.getenv("S3_CRIME_SCENE_PREFIX", "crime-scene/"),
        s3_user_shoes_prefix=os.getenv("S3_USER_SHOES_PREFIX", "user-shoes/"),
    )


__all__ = ["get_config", "Config"]
