"""alembic/env.py — Alembic migration environment for Gaitway.

This module is invoked by Alembic when running migrations.  It:
  1. Loads the project .env file so DATABASE_URL variables are available.
  2. Imports all SQLAlchemy models so autogenerate can detect schema changes.
  3. Injects the live database URL from ``src.db.connection.get_database_url()``.
  4. Runs migrations in either offline (SQL script) or online (live DB) mode.

Usage::

    alembic upgrade head           # apply all migrations
    alembic downgrade -1           # roll back one revision
    alembic current                # show current revision
    alembic revision --autogenerate -m "add xyz column"
"""

from __future__ import annotations

import logging
from logging.config import fileConfig

from alembic import context
from sqlalchemy import engine_from_config, pool

# ── Load .env before importing project modules ───────────────────────────────
from dotenv import load_dotenv

load_dotenv(override=True)

# ── Import models so Alembic autogenerate can detect all tables ───────────────
# All model classes must be imported here (even if unused by name) so that
# Base.metadata is fully populated before autogenerate compares schemas.
from src.db.models import Base  # noqa: E402, F401
from src.db import models as _models  # noqa: F401 — registers all ORM classes
from src.db.connection import get_database_url  # noqa: E402

# ── Alembic Config object (gives access to alembic.ini values) ────────────────
config = context.config

# Inject the live database URL — overrides the placeholder in alembic.ini
config.set_main_option("sqlalchemy.url", get_database_url())

# ── Python logging (from alembic.ini [loggers] section) ──────────────────────
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

logger = logging.getLogger("alembic.env")

# ── Target metadata for autogenerate ─────────────────────────────────────────
target_metadata = Base.metadata


# ─────────────────────────────────────────────────────────────────────────────
# Migration runners
# ─────────────────────────────────────────────────────────────────────────────


def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode — generates SQL without a DB connection.

    This mode is useful for generating migration scripts to review before
    applying, or for databases you cannot connect to directly.

    Run with::

        alembic upgrade head --sql > migration.sql
    """
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        compare_type=True,
        include_schemas=True,
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Run migrations in 'online' mode — applies changes to a live database.

    This is the default mode when you run ``alembic upgrade head``.
    """
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            compare_type=True,
            include_schemas=True,
        )
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    logger.info("Running migrations in offline mode")
    run_migrations_offline()
else:
    logger.info("Running migrations in online mode")
    run_migrations_online()
