"""src/api/middleware — FastAPI middleware for Gaitway API.

Middleware modules:
  auth — Cognito JWT verification + API key fallback (Phase 1 stub)

Full Cognito JWT middleware is wired in Phase 6.  In Phase 1 the
``get_current_user`` dependency returns a placeholder user dict when
no ``COGNITO_USER_POOL_ID`` is set, allowing development without AWS auth.
"""

from .auth import RequireAuth, get_current_user

__all__ = ["get_current_user", "RequireAuth"]
