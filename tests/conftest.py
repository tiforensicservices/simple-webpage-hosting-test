"""tests/conftest.py — Shared pytest fixtures for the Gaitway test suite.

Provides:
  - ``test_db``     — SQLAlchemy session against an in-memory / test PostgreSQL DB
  - ``mock_s3``     — moto-mocked S3 environment (no real AWS calls)
  - ``test_client`` — FastAPI TestClient with mock S3 environment
  - ``sample_shoe`` — a persisted Shoe fixture for test isolation
  - ``env_vars``    — override environment variables for the test session

Usage in test files::

    def test_something(test_client, mock_s3, sample_shoe):
        ...

Notes
-----
- Database fixtures use SQLite in-memory by default (no Docker needed for unit tests).
  To run against a live PostgreSQL instance, set ``TEST_DATABASE_URL`` in the environment.
- S3 fixtures use moto to intercept boto3 calls — no real AWS credentials needed.
- The ``mock_s3`` fixture creates the bucket defined by ``S3_BUCKET_NAME`` env var
  (defaults to ``gaitway-footwear-test`` for test runs).
"""

from __future__ import annotations

import os
from typing import Generator
from unittest.mock import patch

import boto3
import pytest
from fastapi.testclient import TestClient
from moto import mock_aws
from sqlalchemy import create_engine, event
from sqlalchemy.orm import Session, sessionmaker

# ─────────────────────────────────────────────────────────────
# Environment overrides for test runs
# ─────────────────────────────────────────────────────────────

_TEST_ENV = {
    "AWS_DEFAULT_REGION": "us-east-2",
    "AWS_ACCESS_KEY_ID": "testing",
    "AWS_SECRET_ACCESS_KEY": "testing",
    "AWS_SECURITY_TOKEN": "testing",
    "AWS_SESSION_TOKEN": "testing",
    "S3_BUCKET_NAME": "gaitway-footwear-test",
    "S3_RAW_PREFIX": "raw/",
    "S3_PROCESSED_PREFIX": "processed/",
    "S3_IMPRESSIONS_PREFIX": "impressions/",
    "S3_THUMBNAILS_PREFIX": "thumbnails/",
    "S3_CRIME_SCENE_PREFIX": "crime-scene/",
    "S3_USER_SHOES_PREFIX": "user-shoes/",
    "DB_HOST": "localhost",
    "DB_PORT": "5432",
    "DB_NAME": "gaitway_test",
    "DB_USER": "gaitway",
    "DB_PASSWORD": "gaitway_local",
    "API_KEY": "test-api-key-00000000",
    "STRIPE_SECRET_KEY": "",
    "STRIPE_WEBHOOK_SECRET": "",
    "STRIPE_PRICE_ID": "price_test_placeholder",
}


@pytest.fixture(scope="session", autouse=True)
def env_vars():
    """Override environment variables for the entire test session.

    Ensures tests never use real AWS credentials or production DB URLs.
    Restores original env vars after the test session.
    """
    original = {}
    for key, value in _TEST_ENV.items():
        original[key] = os.environ.get(key)
        os.environ[key] = value

    yield _TEST_ENV

    # Restore originals
    for key, orig_value in original.items():
        if orig_value is None:
            os.environ.pop(key, None)
        else:
            os.environ[key] = orig_value


# ─────────────────────────────────────────────────────────────
# S3 Mock Fixtures
# ─────────────────────────────────────────────────────────────


@pytest.fixture
def mock_s3():
    """Provide a moto-mocked S3 environment with the test bucket pre-created.

    All boto3 S3 calls inside the test are intercepted by moto.
    The bucket name comes from the ``S3_BUCKET_NAME`` env var
    (set to ``gaitway-footwear-test`` by the ``env_vars`` fixture).

    Yields:
        boto3 S3 client connected to the mock environment.
    """
    with mock_aws():
        region = os.environ.get("AWS_DEFAULT_REGION", "us-east-2")
        bucket = os.environ.get("S3_BUCKET_NAME", "gaitway-footwear-test")

        s3 = boto3.client(
            "s3",
            region_name=region,
            aws_access_key_id="testing",
            aws_secret_access_key="testing",
        )

        # Create the test bucket
        if region == "us-east-1":
            s3.create_bucket(Bucket=bucket)
        else:
            s3.create_bucket(
                Bucket=bucket,
                CreateBucketConfiguration={"LocationConstraint": region},
            )

        # Enable versioning (matches production setup)
        s3.put_bucket_versioning(
            Bucket=bucket,
            VersioningConfiguration={"Status": "Enabled"},
        )

        yield s3


# ─────────────────────────────────────────────────────────────
# Database Fixtures
# ─────────────────────────────────────────────────────────────


@pytest.fixture(scope="session")
def db_engine():
    """Create a SQLAlchemy engine for testing.

    Uses SQLite in-memory by default (no Docker needed for unit tests).
    Set ``TEST_DATABASE_URL`` to override with a real PostgreSQL URL for
    integration tests::

        TEST_DATABASE_URL=postgresql+psycopg2://gaitway:gaitway_local@localhost:5432/gaitway_test \\
        pytest tests/

    Yields:
        SQLAlchemy engine.
    """
    test_url = os.environ.get("TEST_DATABASE_URL")

    if test_url:
        # Use provided PostgreSQL URL (integration tests)
        engine = create_engine(test_url, pool_pre_ping=True)
    else:
        # SQLite in-memory — fast unit tests (no Docker needed)
        # NOTE: Vector(512) type is not supported by SQLite.
        # Migrations that use Vector will be skipped in SQLite mode.
        engine = create_engine(
            "sqlite:///:memory:",
            connect_args={"check_same_thread": False},
        )

    yield engine
    engine.dispose()


@pytest.fixture(scope="session")
def db_tables(db_engine):
    """Create all ORM tables in the test database.

    For SQLite, the pgvector ``Vector`` type is replaced with Text
    to allow unit tests to run without a real PostgreSQL instance.
    """
    from sqlalchemy import text

    # For SQLite: register a dummy "vector" type handler
    db_url = str(db_engine.url)
    is_sqlite = db_url.startswith("sqlite")

    if is_sqlite:
        # Patch Vector to behave as Text for SQLite compatibility
        try:
            from pgvector.sqlalchemy import Vector
            from sqlalchemy import Text

            # Monkey-patch: replace Vector with Text for SQLite tests
            import pgvector.sqlalchemy
            _original_vector = pgvector.sqlalchemy.Vector

            class _FakeVector(Text):
                def __init__(self, dim=None):
                    super().__init__()

            pgvector.sqlalchemy.Vector = _FakeVector

            from src.db.models import Base
            Base.metadata.create_all(db_engine)

            pgvector.sqlalchemy.Vector = _original_vector
        except Exception:
            # If pgvector not installed, create tables without Vector column
            from src.db.models import Base
            Base.metadata.create_all(db_engine)
    else:
        # PostgreSQL: enable extension and create tables normally
        with db_engine.connect() as conn:
            conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
            conn.commit()
        from src.db.models import Base
        Base.metadata.create_all(db_engine)

    yield

    from src.db.models import Base
    Base.metadata.drop_all(db_engine)


@pytest.fixture
def test_db(db_engine, db_tables) -> Generator[Session, None, None]:
    """Provide a database session that rolls back all changes after each test.

    Uses nested transactions (savepoints) to ensure complete isolation
    between tests — no data leaks between test cases.

    Yields:
        SQLAlchemy Session (rolls back on exit).
    """
    connection = db_engine.connect()
    transaction = connection.begin()

    factory = sessionmaker(bind=connection, autocommit=False, autoflush=False)
    session = factory()

    # Use SAVEPOINT for nested rollback support
    nested = connection.begin_nested()

    @event.listens_for(session, "after_transaction_end")
    def restart_savepoint(sess, trans):
        nonlocal nested
        if trans.nested and not trans._parent.nested:
            nested = connection.begin_nested()

    try:
        yield session
    finally:
        session.close()
        transaction.rollback()
        connection.close()


# ─────────────────────────────────────────────────────────────
# FastAPI Test Client Fixtures
# ─────────────────────────────────────────────────────────────


@pytest.fixture
def test_client(mock_s3):
    """Provide a FastAPI TestClient with moto S3 mock active.

    The ``mock_s3`` fixture is required so any S3 calls made by
    endpoints during tests are intercepted by moto.

    Yields:
        ``fastapi.testclient.TestClient`` instance.
    """
    from src.api.main import app

    with TestClient(app) as client:
        yield client


@pytest.fixture
def authed_client(test_client):
    """TestClient with API key pre-set in headers.

    Uses the test API key from ``env_vars`` fixture (``test-api-key-00000000``).
    """
    test_client.headers.update({"X-API-Key": "test-api-key-00000000"})
    return test_client


# ─────────────────────────────────────────────────────────────
# Sample Data Fixtures
# ─────────────────────────────────────────────────────────────


@pytest.fixture
def sample_shoe(test_db):
    """Insert and return a sample Shoe record for use in tests.

    The record is automatically rolled back after the test completes
    (via the ``test_db`` transaction rollback).

    Returns:
        ``src.db.models.Shoe`` instance persisted in the test DB.
    """
    from src.db.models import Shoe

    shoe = Shoe(
        external_site="zappos",
        external_id="test-product-001",
        brand="Nike",
        model_name="Air Max 90",
        category="mens-shoes",
        gender="mens",
        colorway="White/Black",
        price=110.00,
        description="Test shoe fixture",
        product_url="https://www.zappos.com/product/test-product-001",
    )
    test_db.add(shoe)
    test_db.flush()  # assign ID without committing
    return shoe


@pytest.fixture
def sample_shoe_image(test_db, sample_shoe):
    """Insert and return a sample ShoeImage record linked to ``sample_shoe``.

    The embedding column is left None (Vector type not available in SQLite).

    Returns:
        ``src.db.models.ShoeImage`` instance.
    """
    from src.db.models import ShoeImage

    image = ShoeImage(
        shoe_id=sample_shoe.id,
        image_type="upper",
        s3_raw_key="raw/shoes/test-product-001/upper/abc123.jpg",
        s3_thumbnail_key="thumbnails/shoes/test-product-001/upper/abc123.jpg",
        phash="a1b2c3d4e5f6g7h8",
        width=600,
        height=600,
    )
    test_db.add(image)
    test_db.flush()
    return image


@pytest.fixture
def sample_user(test_db):
    """Insert and return a sample User record.

    Returns:
        ``src.db.models.User`` instance.
    """
    from src.db.models import User

    user = User(
        email="test@gaitway.local",
        cognito_sub="test-sub-00000000-0000-0000-0000-000000000001",
        is_active=True,
    )
    test_db.add(user)
    test_db.flush()
    return user


@pytest.fixture
def sample_workspace(test_db, sample_user):
    """Insert and return a sample Workspace record linked to ``sample_user``.

    Returns:
        ``src.db.models.Workspace`` instance.
    """
    from src.db.models import Workspace

    workspace = Workspace(
        user_id=sample_user.id,
        name="Test Investigation Workspace",
        subscription_status="active",
    )
    test_db.add(workspace)
    test_db.flush()
    return workspace
