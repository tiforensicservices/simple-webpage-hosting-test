"""src/api/routes — FastAPI route blueprints for Gaitway API.

Each sub-module exposes an ``APIRouter`` that is registered on the main app
in ``src.api.main``.

Routers:
  shoes          — shoe catalog (read + admin write)
  crime_scene    — forensic crime scene search pipeline
  upload         — S3 image upload helpers
  admin          — admin-only stats and scraper control
  stripe_billing — Stripe checkout, portal, and webhook handler
"""

from .admin import router as admin_router
from .crime_scene import router as crime_scene_router
from .shoes import router as shoes_router
from .stripe_billing import router as stripe_router
from .upload import router as upload_router

__all__ = [
    "shoes_router",
    "crime_scene_router",
    "upload_router",
    "admin_router",
    "stripe_router",
]
