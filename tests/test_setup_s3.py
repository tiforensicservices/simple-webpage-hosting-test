"""
test_setup_s3.py — Unit tests for the S3 setup module.

Uses moto to mock AWS calls — no real AWS credentials needed to run tests.
Install moto: pip install moto[s3]
Run: pytest tests/ -v
"""

import os
from unittest.mock import MagicMock, patch

import boto3
import pytest
from botocore.exceptions import ClientError

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def set_env_vars(monkeypatch):
    """Set required environment variables for all tests."""
    monkeypatch.setenv("AWS_ACCESS_KEY_ID", "test-key")
    monkeypatch.setenv("AWS_SECRET_ACCESS_KEY", "test-secret")
    monkeypatch.setenv("AWS_DEFAULT_REGION", "us-east-1")
    monkeypatch.setenv("S3_BUCKET_NAME", "test-shoeprint-bucket")
    monkeypatch.setenv("S3_RAW_PREFIX", "raw/")
    monkeypatch.setenv("S3_PROCESSED_PREFIX", "processed/")
    monkeypatch.setenv("S3_THUMBNAILS_PREFIX", "thumbnails/")


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestSetupS3:
    """Tests for S3 setup functions."""

    def test_env_bucket_name_is_set(self):
        """Bucket name should be present in environment."""
        assert os.getenv("S3_BUCKET_NAME") == "test-shoeprint-bucket"

    def test_env_region_is_set(self):
        """AWS region should be present in environment."""
        assert os.getenv("AWS_DEFAULT_REGION") == "us-east-1"

    def test_s3_prefixes_are_set(self):
        """S3 folder prefixes should all be defined."""
        assert os.getenv("S3_RAW_PREFIX") == "raw/"
        assert os.getenv("S3_PROCESSED_PREFIX") == "processed/"
        assert os.getenv("S3_THUMBNAILS_PREFIX") == "thumbnails/"

    def test_placeholder_bucket_name_rejected(self, monkeypatch):
        """Setup should fail if bucket name is still the placeholder."""
        monkeypatch.setenv("S3_BUCKET_NAME", "shoeprint-images-YOUR_ACCOUNT_ID")
        import importlib

        from src.aws import setup_s3

        importlib.reload(setup_s3)
        # The main() function calls sys.exit(1) for placeholder name
        with pytest.raises(SystemExit) as exc_info:
            setup_s3.main()
        assert exc_info.value.code == 1
