"""
provision_rds.py — Phase 2: Provision RDS PostgreSQL 16 + pgvector in AWS
==========================================================================

Run once to create the Gaitway production RDS instance.
After running:
  1. Copy the endpoint from the output into .env  DB_HOST=<endpoint>
  2. Store credentials in AWS Secrets Manager (see instructions at bottom)
  3. Run: alembic upgrade head  (against RDS endpoint)
  4. Verify HNSW index: psql -h <endpoint> -U admin -d gaitway_db -c
       "\\d shoe_images"

Usage:
    python scripts/provision_rds.py [--dry-run]

    --dry-run   Print the boto3 call parameters but do NOT create anything.

Prerequisites:
    pip install boto3 python-dotenv
    AWS credentials with rds:CreateDBInstance, ec2:CreateSecurityGroup,
    ec2:AuthorizeSecurityGroupIngress, secretsmanager:CreateSecret permissions.

    .env must have:
        AWS_ACCESS_KEY_ID, AWS_SECRET_ACCESS_KEY, AWS_DEFAULT_REGION
        DB_PASSWORD   (desired master password for the new RDS instance)
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

import boto3
from botocore.exceptions import ClientError
from dotenv import load_dotenv

load_dotenv(override=True)

# ── Configuration ──────────────────────────────────────────────────────────

REGION          = os.getenv("AWS_DEFAULT_REGION", "us-east-2")
DB_IDENTIFIER   = "gaitway-db-prod"       # RDS instance identifier
DB_NAME         = "gaitway_db"             # PostgreSQL database name
DB_USER         = "gaitway_admin"          # Master username
DB_PASSWORD     = os.getenv("DB_PASSWORD", "CHANGE_ME_IN_DOT_ENV")
INSTANCE_CLASS  = "db.t3.medium"           # 2 vCPU, 4 GB RAM (~$50/month)
STORAGE_GB      = 100                      # gp3 SSD
ENGINE_VERSION  = "16.6"                   # PostgreSQL 16.x with pgvector support
MULTI_AZ        = False                    # Set True for production HA ($$$)
SG_NAME         = "gaitway-rds-sg"        # Security group name
SECRET_NAME     = "gaitway/rds/master"    # Secrets Manager secret name

# ── Helpers ────────────────────────────────────────────────────────────────


def get_default_vpc_id(ec2) -> str:
    """Return the default VPC ID for the region."""
    vpcs = ec2.describe_vpcs(Filters=[{"Name": "isDefault", "Values": ["true"]}])
    vpcs_list = vpcs["Vpcs"]
    if not vpcs_list:
        raise RuntimeError(
            "No default VPC found in region. Create a VPC first or specify one."
        )
    return vpcs_list[0]["VpcId"]


def ensure_security_group(ec2, vpc_id: str) -> str:
    """Create or retrieve the RDS security group; return its ID."""
    # Check if it already exists
    try:
        result = ec2.describe_security_groups(
            Filters=[
                {"Name": "group-name", "Values": [SG_NAME]},
                {"Name": "vpc-id", "Values": [vpc_id]},
            ]
        )
        if result["SecurityGroups"]:
            sg_id = result["SecurityGroups"][0]["GroupId"]
            print(f"  ✅ Security group already exists: {sg_id}")
            return sg_id
    except ClientError:
        pass

    # Create new security group
    sg = ec2.create_security_group(
        GroupName=SG_NAME,
        Description="Gaitway RDS PostgreSQL - allow 5432 from ECS + dev",
        VpcId=vpc_id,
    )
    sg_id = sg["GroupId"]

    # Allow PostgreSQL inbound (RESTRICT to ECS SG in production; 0.0.0.0/0 for dev)
    ec2.authorize_security_group_ingress(
        GroupId=sg_id,
        IpPermissions=[
            {
                "IpProtocol": "tcp",
                "FromPort": 5432,
                "ToPort": 5432,
                # ⚠️  TODO Phase 8: replace with ECS task security group ID
                "IpRanges": [{"CidrIp": "0.0.0.0/0", "Description": "dev-only - tighten for prod"}],
            }
        ],
    )
    print(f"  ✅ Security group created: {sg_id}")
    return sg_id


def store_secret(secretsmanager, endpoint: str) -> None:
    """Store RDS credentials in AWS Secrets Manager."""
    secret_value = json.dumps({
        "host":     endpoint,
        "port":     5432,
        "dbname":   DB_NAME,
        "username": DB_USER,
        "password": DB_PASSWORD,
    })
    try:
        secretsmanager.create_secret(
            Name=SECRET_NAME,
            Description="Gaitway RDS master credentials",
            SecretString=secret_value,
        )
        print(f"  ✅ Secret stored: {SECRET_NAME}")
    except secretsmanager.exceptions.ResourceExistsException:
        secretsmanager.update_secret(
            SecretId=SECRET_NAME,
            SecretString=secret_value,
        )
        print(f"  ✅ Secret updated: {SECRET_NAME}")


def wait_for_available(rds, identifier: str, timeout: int = 900) -> str:
    """Poll until the RDS instance is 'available'; return its endpoint."""
    print(f"\n⏳ Waiting for {identifier} to become available (up to {timeout}s)…")
    deadline = time.time() + timeout
    while time.time() < deadline:
        resp = rds.describe_db_instances(DBInstanceIdentifier=identifier)
        instance = resp["DBInstances"][0]
        status = instance["DBInstanceStatus"]
        print(f"   Status: {status}", end="\r")
        if status == "available":
            endpoint = instance["Endpoint"]["Address"]
            print(f"\n  ✅ RDS instance available! Endpoint: {endpoint}")
            return endpoint
        if status in ("failed", "incompatible-parameters", "incompatible-restore"):
            raise RuntimeError(f"RDS provisioning failed — status: {status}")
        time.sleep(15)
    raise TimeoutError(f"RDS instance did not become available within {timeout}s")


# ── Main ───────────────────────────────────────────────────────────────────


def provision(dry_run: bool = False) -> None:
    """Provision the RDS PostgreSQL 16 instance for Phase 2."""
    print("=" * 65)
    print("  Gaitway Phase 2 — RDS PostgreSQL 16 Provisioning")
    print("=" * 65)
    print(f"  Region:           {REGION}")
    print(f"  DB identifier:    {DB_IDENTIFIER}")
    print(f"  Engine:           PostgreSQL {ENGINE_VERSION}")
    print(f"  Instance class:   {INSTANCE_CLASS}")
    print(f"  Storage:          {STORAGE_GB} GB gp3")
    print(f"  Multi-AZ:         {MULTI_AZ}")
    print(f"  DB name:          {DB_NAME}")
    print(f"  Master user:      {DB_USER}")
    print(f"  Secrets Manager:  {SECRET_NAME}")
    if dry_run:
        print("\n  [DRY RUN] No resources will be created.")
        return

    session   = boto3.Session(region_name=REGION)
    ec2       = session.client("ec2")
    rds       = session.client("rds")
    sm        = session.client("secretsmanager")

    # Step 1 — Security group
    print("\nStep 1: Security group")
    vpc_id = get_default_vpc_id(ec2)
    print(f"  VPC: {vpc_id}")
    sg_id = ensure_security_group(ec2, vpc_id)

    # Step 2 — Check if instance already exists
    print("\nStep 2: RDS instance")
    try:
        existing = rds.describe_db_instances(DBInstanceIdentifier=DB_IDENTIFIER)
        status = existing["DBInstances"][0]["DBInstanceStatus"]
        endpoint = existing["DBInstances"][0].get("Endpoint", {}).get("Address", "")
        print(f"  ℹ️  Instance already exists — status: {status}, endpoint: {endpoint}")
    except rds.exceptions.DBInstanceNotFoundFault:
        # Create the instance
        print("  Creating RDS instance (this takes ~5-10 minutes)…")
        rds.create_db_instance(
            DBInstanceIdentifier=DB_IDENTIFIER,
            DBName=DB_NAME,
            DBInstanceClass=INSTANCE_CLASS,
            Engine="postgres",
            EngineVersion=ENGINE_VERSION,
            MasterUsername=DB_USER,
            MasterUserPassword=DB_PASSWORD,
            AllocatedStorage=STORAGE_GB,
            StorageType="gp3",
            MultiAZ=MULTI_AZ,
            PubliclyAccessible=True,       # False in production (use VPC peering)
            VpcSecurityGroupIds=[sg_id],
            BackupRetentionPeriod=7,       # 7-day automated backups
            DeletionProtection=False,      # Enable True before go-live
            Tags=[
                {"Key": "Project", "Value": "Gaitway"},
                {"Key": "Phase",   "Value": "2"},
                {"Key": "Env",     "Value": "dev"},
            ],
        )
        endpoint = wait_for_available(rds, DB_IDENTIFIER)

    # Step 3 — Enable pgvector extension (via psql or alembic migration)
    print("\nStep 3: pgvector extension")
    print("  pgvector is enabled by the first Alembic migration.")
    print("  Run 'alembic upgrade head' with DB_HOST pointing to RDS.")
    print(f"  Endpoint to use: {endpoint}")

    # Step 4 — Store credentials in Secrets Manager
    print("\nStep 4: Secrets Manager")
    store_secret(sm, endpoint)

    # ── Post-provisioning instructions ─────────────────────────────────────
    print("\n" + "=" * 65)
    print("  ✅ RDS provisioning complete!")
    print("=" * 65)
    print(f"""
Next steps:
  1. Update .env with RDS connection details:
       DB_HOST={endpoint}
       DB_PORT=5432
       DB_NAME={DB_NAME}
       DB_USER={DB_USER}
       DB_PASSWORD=<your password>

  2. Run Alembic migrations against RDS:
       (in project root)
       python -m alembic upgrade head

  3. Verify the HNSW index was created:
       docker run --rm postgres:16 psql \\
         "postgresql://{DB_USER}:<password>@{endpoint}:5432/{DB_NAME}" \\
         -c "\\d shoe_images"
       Look for: shoe_images_embedding_hnsw_idx

  4. Run integration tests:
       TEST_DATABASE_URL="postgresql+psycopg2://{DB_USER}:<password>@{endpoint}:5432/{DB_NAME}" \\
       pytest tests/ -v

  5. Tighten the security group (production):
       - Remove 0.0.0.0/0 ingress from {SG_NAME}
       - Add ingress from ECS task security group only
       - Set PubliclyAccessible=False and use VPC routing

  6. Enable deletion protection before go-live:
       aws rds modify-db-instance \\
         --db-instance-identifier {DB_IDENTIFIER} \\
         --deletion-protection \\
         --apply-immediately
""")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Provision Gaitway RDS PostgreSQL 16 instance (Phase 2)"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print config and exit without creating any AWS resources",
    )
    args = parser.parse_args()
    provision(dry_run=args.dry_run)
