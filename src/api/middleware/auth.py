"""src/api/middleware/auth.py — Authentication middleware for Gaitway API.

Provides two authentication mechanisms:

Phase 1 (current):
  - API key check via ``X-API-Key`` header or ``API_KEY`` env var.
  - If no Cognito pool is configured, a "dev mode" placeholder user
    is returned so local development works without AWS.

Phase 6 (future):
  - Full AWS Cognito JWT verification (RS256).
  - Extracts ``sub`` claim as the Cognito user ID.
  - Verifies token expiry, audience, and issuer.
  - Fetches JWKS from Cognito User Pool endpoint (cached).

Usage (FastAPI dependency injection)::

    from src.api.middleware.auth import get_current_user

    @router.get("/protected")
    async def protected(user = Depends(get_current_user)):
        return {"cognito_sub": user["sub"]}

The ``RequireAuth`` class is a callable dependency shortcut that raises
HTTP 401 if the user is unauthenticated.

Environment Variables
---------------------
API_KEY                — simple shared secret for Phase 1 dev access
COGNITO_USER_POOL_ID   — enables full JWT verification (Phase 6)
COGNITO_APP_CLIENT_ID  — Cognito app client ID (Phase 6)
AWS_DEFAULT_REGION     — AWS region where the user pool lives
"""

from __future__ import annotations

import logging
import os
from typing import Any, Dict, Optional

from fastapi import Depends, HTTPException, Security, status
from fastapi.security import APIKeyHeader, HTTPAuthorizationCredentials, HTTPBearer

logger = logging.getLogger(__name__)

# ─────────────────────────────────────────────────────────────
# Security schemes
# ─────────────────────────────────────────────────────────────

_api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)
_bearer_scheme = HTTPBearer(auto_error=False)

# ─────────────────────────────────────────────────────────────
# Dev-mode placeholder user
# ─────────────────────────────────────────────────────────────

_DEV_USER: Dict[str, Any] = {
    "sub": "dev-user-00000000-0000-0000-0000-000000000000",
    "email": "dev@gaitway.local",
    "is_active": True,
    "groups": ["admins"],
    "auth_mode": "dev",
}


# ─────────────────────────────────────────────────────────────
# Phase 1 — API key verification
# ─────────────────────────────────────────────────────────────


def _verify_api_key(api_key: Optional[str]) -> bool:
    """Return True if api_key matches the configured API_KEY env var."""
    configured = os.getenv("API_KEY")
    if not configured:
        return False
    return api_key == configured


# ─────────────────────────────────────────────────────────────
# Phase 6 — Cognito JWT verification (stub)
# ─────────────────────────────────────────────────────────────


def _verify_cognito_jwt(token: str) -> Optional[Dict[str, Any]]:
    """Verify a Cognito JWT and return the decoded claims.

    TODO (Phase 6): implement full RS256 JWT verification:
      1. Fetch JWKS from:
         https://cognito-idp.{region}.amazonaws.com/{pool_id}/.well-known/jwks.json
      2. Match kid from JWT header to a JWKS public key.
      3. Verify signature, expiry, iss, and aud claims.
      4. Return decoded payload dict.

    Args:
        token: Raw Bearer JWT string from the Authorization header.

    Returns:
        Decoded JWT payload dict if valid; None otherwise.
    """
    pool_id = os.getenv("COGNITO_USER_POOL_ID")
    if not pool_id:
        return None

    # Stub — full implementation in Phase 6
    logger.debug("Cognito JWT verification not yet implemented (Phase 6)")
    return None


# ─────────────────────────────────────────────────────────────
# Main dependency
# ─────────────────────────────────────────────────────────────


async def get_current_user(
    api_key: Optional[str] = Security(_api_key_header),
    bearer: Optional[HTTPAuthorizationCredentials] = Security(_bearer_scheme),
) -> Dict[str, Any]:
    """FastAPI dependency that returns the authenticated user context.

    Resolution order:
      1. If Cognito is configured: verify the Bearer JWT.
      2. Else if API_KEY is configured: verify the X-API-Key header.
      3. Else (no auth configured): return the dev-mode placeholder user
         with a warning log (development only).

    Returns:
        Dict with at least ``sub`` (Cognito user ID), ``email``,
        ``is_active``, ``groups``, and ``auth_mode`` keys.

    Raises:
        HTTPException 401: if authentication fails in a configured environment.
    """
    cognito_pool = os.getenv("COGNITO_USER_POOL_ID")

    # ── Path 1: Cognito JWT (Phase 6) ────────────────────────────────────────
    if cognito_pool:
        token = bearer.credentials if bearer else None
        if not token:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Bearer token required",
                headers={"WWW-Authenticate": "Bearer"},
            )
        claims = _verify_cognito_jwt(token)
        if not claims:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid or expired token",
                headers={"WWW-Authenticate": "Bearer"},
            )
        return {
            "sub": claims.get("sub"),
            "email": claims.get("email"),
            "is_active": True,
            "groups": claims.get("cognito:groups", []),
            "auth_mode": "cognito",
        }

    # ── Path 2: API key (Phase 1) ─────────────────────────────────────────────
    configured_key = os.getenv("API_KEY")
    if configured_key:
        if not _verify_api_key(api_key):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid or missing API key (provide X-API-Key header)",
            )
        return {
            "sub": "api-key-user",
            "email": "api@gaitway.local",
            "is_active": True,
            "groups": ["api"],
            "auth_mode": "api_key",
            "api_key_prefix": (api_key or "")[:8] + "...",
        }

    # ── Path 3: Dev mode (no auth configured) ────────────────────────────────
    logger.warning(
        "⚠️  Auth running in DEV mode — no API_KEY or COGNITO_USER_POOL_ID set. "
        "All requests are unauthenticated. DO NOT use in production."
    )
    return _DEV_USER


# ─────────────────────────────────────────────────────────────
# Convenience dependency: require authentication
# ─────────────────────────────────────────────────────────────


class RequireAuth:
    """FastAPI dependency that requires a valid authenticated user.

    Unlike ``get_current_user`` (which falls back to dev mode),
    ``RequireAuth`` raises HTTP 401 in dev mode if ``strict=True``
    is passed.  Used for production-sensitive endpoints.

    Usage::

        @router.delete("/shoes/{id}")
        async def delete_shoe(auth=Depends(RequireAuth(strict=True))):
            ...
    """

    def __init__(self, strict: bool = False) -> None:
        self.strict = strict

    async def __call__(
        self,
        user: Dict[str, Any] = Depends(get_current_user),
    ) -> Dict[str, Any]:
        if self.strict and user.get("auth_mode") == "dev":
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail=(
                    "This endpoint requires authentication. "
                    "Configure API_KEY or COGNITO_USER_POOL_ID."
                ),
            )
        return user
