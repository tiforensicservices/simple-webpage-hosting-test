"""
connection.py — Database connection management for Gaitway.

Provides:
  - get_engine()         — SQLAlchemy engine (lazy singleton)
  - get_session_factory() — sessionmaker (lazy singleton)
  - get_db()             — context manager yielding a Session
  - ping_db()            — connectivity health-check

Configuration is read from .env (or environment variables):
  DB_HOST, DB_PORT, DB_NAME, DB_USER, DB_PASSWORD
  DB_ECHO — set to "true" to log all SQL queries (dev only)
"""

from __future__ import annotations

import logging
import os
from contextlib import contextmanager
from typing import Generator

from dotenv import load_dotenv
from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

load_dotenv(override=True)

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Module-level singletons (created lazily on first use)
# ---------------------------------------------------------------------------

_engine: Engine | None = None
_session_factory: sessionmaker | None = None


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def get_database_url() -> str:
    """Build the PostgreSQL connection URL from environment variables.

    Returns:
        psycopg2 connection URL string.
    """
    host = os.getenv("DB_HOST", "localhost")
    port = os.getenv("DB_PORT", "5432")
    name = os.getenv("DB_NAME", "gaitway")
    user = os.getenv("DB_USER", "gaitway")
    password = os.getenv("DB_PASSWORD", "gaitway_local")
    return f"postgresql+psycopg2://{user}:{password}@{host}:{port}/{name}"


def get_engine() -> Engine:
    """Return the SQLAlchemy engine, creating it on first call.

    Connection pool settings:
      pool_size=5    — keep 5 persistent connections ready
      max_overflow=10 — allow 10 extra connections under load
      pool_pre_ping  — validate connection health before use

    Returns:
        Configured SQLAlchemy Engine.
    """
    global _engine
    if _engine is None:
        db_url = get_database_url()
        _engine = create_engine(
            db_url,
            pool_size=5,
            max_overflow=10,
            pool_pre_ping=True,
            echo=os.getenv("DB_ECHO", "false").lower() == "true",
        )
        # Log without exposing the password
        safe_url = db_url.split("@")[-1]
        logger.info("✅ Database engine created: ...@%s", safe_url)
    return _engine


def get_session_factory() -> sessionmaker:
    """Return the sessionmaker, creating it on first call.

    Returns:
        Configured sessionmaker bound to the engine.
    """
    global _session_factory
    if _session_factory is None:
        _session_factory = sessionmaker(
            bind=get_engine(),
            autocommit=False,
            autoflush=False,
        )
    return _session_factory


@contextmanager
def get_db() -> Generator[Session, None, None]:
    """Context manager that yields a database session.

    Commits on clean exit; rolls back on any exception; always closes.

    Usage::

        with get_db() as db:
            shoes = db.query(Shoe).all()

    Yields:
        SQLAlchemy Session.
    """
    factory = get_session_factory()
    session: Session = factory()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def ping_db() -> bool:
    """Test database connectivity with a lightweight query.

    Returns:
        True if the database is reachable; False otherwise.
    """
    try:
        engine = get_engine()
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        logger.info("✅ Database connection verified")
        return True
    except Exception as exc:  # noqa: BLE001
        logger.error("❌ Database connection failed: %s", exc)
        return False
