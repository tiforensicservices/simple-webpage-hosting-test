"""
setup_s3.py — Create and configure the Gaitway S3 bucket for footwear image storage.

This script:
  1. Creates the S3 bucket (if it doesn't already exist)
  2. Enables versioning (so we never lose an image)
  3. Applies a lifecycle policy (move old images to cheaper storage after 90 days)
  4. Enables server-side encryption (AES-256)
  5. Blocks all public access (all images accessed via presigned URLs only)
  6. Creates the Gaitway folder structure

Usage (inside Dev Container):
    python src/aws/setup_s3.py

Requirements:
    - .env file with AWS_ACCESS_KEY_ID, AWS_SECRET_ACCESS_KEY,
      AWS_DEFAULT_REGION, and S3_BUCKET_NAME set
"""

import logging
import os
import sys

import boto3
from botocore.exceptions import ClientError
from src.config import get_config

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
logger = logging.getLogger(__name__)


def get_s3_client() -> boto3.client:
    """Create and return an authenticated S3 client.

    Returns:
        boto3 S3 client configured from environment variables.
    """
    region = os.getenv("AWS_DEFAULT_REGION", "us-east-2")
    return boto3.client("s3", region_name=region)


def create_bucket(client: boto3.client, bucket_name: str, region: str) -> bool:
    """Create the S3 bucket in the specified region.

    Args:
        client: Authenticated boto3 S3 client.
        bucket_name: Name of the bucket to create.
        region: AWS region (e.g. 'us-east-1').

    Returns:
        True if bucket was created or already exists, False on error.
    """
    try:
        if region == "us-east-1":
            # us-east-1 does NOT accept LocationConstraint
            client.create_bucket(Bucket=bucket_name)
        else:
            client.create_bucket(
                Bucket=bucket_name,
                CreateBucketConfiguration={"LocationConstraint": region},
            )
        logger.info("✅ Bucket created: s3://%s", bucket_name)
        return True
    except ClientError as e:
        error_code = e.response["Error"]["Code"]
        if error_code in ("BucketAlreadyOwnedByYou", "BucketAlreadyExists"):
            logger.info("ℹ️  Bucket already exists: s3://%s", bucket_name)
            return True
        logger.error("❌ Failed to create bucket: %s", e)
        return False


def enable_versioning(client: boto3.client, bucket_name: str) -> None:
    """Enable versioning on the bucket to protect against accidental deletion.

    Args:
        client: Authenticated boto3 S3 client.
        bucket_name: Name of the target bucket.
    """
    client.put_bucket_versioning(
        Bucket=bucket_name,
        VersioningConfiguration={"Status": "Enabled"},
    )
    logger.info("✅ Versioning enabled on s3://%s", bucket_name)


def block_public_access(client: boto3.client, bucket_name: str) -> None:
    """Block all public access to the bucket — images are private.

    Args:
        client: Authenticated boto3 S3 client.
        bucket_name: Name of the target bucket.
    """
    client.put_public_access_block(
        Bucket=bucket_name,
        PublicAccessBlockConfiguration={
            "BlockPublicAcls": True,
            "IgnorePublicAcls": True,
            "BlockPublicPolicy": True,
            "RestrictPublicBuckets": True,
        },
    )
    logger.info("✅ Public access blocked on s3://%s", bucket_name)


def enable_encryption(client: boto3.client, bucket_name: str) -> None:
    """Enable AES-256 server-side encryption on all objects.

    Args:
        client: Authenticated boto3 S3 client.
        bucket_name: Name of the target bucket.
    """
    client.put_bucket_encryption(
        Bucket=bucket_name,
        ServerSideEncryptionConfiguration={
            "Rules": [
                {
                    "ApplyServerSideEncryptionByDefault": {"SSEAlgorithm": "AES256"},
                    "BucketKeyEnabled": True,
                }
            ]
        },
    )
    logger.info("✅ AES-256 encryption enabled on s3://%s", bucket_name)


def apply_lifecycle_policy(client: boto3.client, bucket_name: str) -> None:
    """Apply a lifecycle policy to move older images to cheaper storage tiers.

    Policy:
        - After 90 days  → move to S3 Standard-IA (infrequent access, 40% cheaper)
        - After 365 days → move to S3 Glacier (archive, 80% cheaper)

    Args:
        client: Authenticated boto3 S3 client.
        bucket_name: Name of the target bucket.
    """
    client.put_bucket_lifecycle_configuration(
        Bucket=bucket_name,
        LifecycleConfiguration={
            "Rules": [
                {
                    "ID": "TransitionToIA",
                    "Status": "Enabled",
                    "Filter": {"Prefix": ""},
                    "Transitions": [
                        {
                            "Days": 90,
                            "StorageClass": "STANDARD_IA",
                        },
                        {
                            "Days": 365,
                            "StorageClass": "GLACIER",
                        },
                    ],
                }
            ]
        },
    )
    logger.info("✅ Lifecycle policy applied on s3://%s", bucket_name)


def create_folder_structure(
    client: boto3.client, bucket_name: str, cfg = None
) -> None:
    """Create logical folder prefixes within the Gaitway bucket.

    Folders:
        raw/          — Original retailer images (unmodified, from scrapers)
        processed/    — Normalized/resized outsole & upper images
        impressions/  — AI-generated synthetic test impressions
        thumbnails/   — Small previews for web display
        crime-scene/  — Uploaded crime scene footwear impressions (per workspace)
        user-shoes/   — User-uploaded shoes (upload wizard)

    Args:
        client: Authenticated boto3 S3 client.
        bucket_name: Name of the target bucket.
        cfg: Optional Config object; if None, uses default environment variables.
    """
    # Use provided config or defaults from environment
    if cfg is None:
        from src.config import get_config

        cfg = get_config()

    prefixes = [
        cfg.s3_raw_prefix,
        cfg.s3_processed_prefix,
        cfg.s3_impressions_prefix,
        cfg.s3_thumbnails_prefix,
        cfg.s3_crime_scene_prefix,
        cfg.s3_user_shoes_prefix,
    ]
    for prefix in prefixes:
        client.put_object(Bucket=bucket_name, Key=prefix)
        logger.info("✅ Created folder: s3://%s/%s", bucket_name, prefix)


def verify_connection(client: boto3.client) -> bool:
    """Verify AWS credentials are valid before proceeding.

    Returns:
        True if credentials work, False otherwise.
    """
    try:
        sts = boto3.client("sts")
        identity = sts.get_caller_identity()
        logger.info(
            "✅ AWS connection verified — Account: %s, User: %s",
            identity["Account"],
            identity["Arn"],
        )
        return True
    except ClientError as e:
        logger.error("❌ AWS credentials invalid or not set: %s", e)
        return False


def main() -> None:
    """Main entry point — run the full S3 setup sequence."""
    # Use centralized config loader which canonicalizes env names
    cfg = get_config()
    bucket_name = cfg.s3_bucket
    region = cfg.aws_region or "us-east-1"

    if not bucket_name or bucket_name == "gaitway-footwear-YOUR_ACCOUNT_ID":
        logger.error(
            "❌ S3 bucket name is not configured. Set `S3_BUCKET_NAME` as an environment "
            "variable or configure your secrets manager according to the README."
        )
        sys.exit(1)

    logger.info("🚀 Starting S3 bucket setup for: %s", bucket_name)

    client = get_s3_client()

    # Step 1: Verify credentials
    if not verify_connection(client):
        sys.exit(1)

    # Step 2: Create bucket
    if not create_bucket(client, bucket_name, region):
        sys.exit(1)

    # Step 3: Security hardening
    block_public_access(client, bucket_name)
    enable_encryption(client, bucket_name)
    enable_versioning(client, bucket_name)

    # Step 4: Cost optimization
    apply_lifecycle_policy(client, bucket_name)

    # Step 5: Folder structure
    create_folder_structure(client, bucket_name, cfg)

    logger.info("")
    logger.info("🎉 S3 setup complete! Bucket s3://%s is ready.", bucket_name)
    logger.info("   Folders: raw/ | processed/ | impressions/ | thumbnails/ | crime-scene/ | user-shoes/")
    logger.info("   Next step: Phase 0.5 PoC — write ZapposScraper and upload first images")
    logger.info(
        "   Console URL: https://s3.console.aws.amazon.com/s3/buckets/%s", bucket_name
    )


if __name__ == "__main__":
    main()
