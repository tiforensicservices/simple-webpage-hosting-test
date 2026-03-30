"""
fix_iam_phase2.py — Add EC2 / RDS / SecretsManager permissions to shoeprint-dev
================================================================================
Run ONCE before provision_rds.py.

Attaches an inline policy 'GaitwayPhase2Provisioning' to IAM user shoeprint-dev
granting the minimum rights needed to:
  • Create/describe the gaitway-rds-sg security group
  • Create / describe the gaitway-db-prod RDS instance
  • Create / update the gaitway/rds/master Secrets Manager secret

Usage:
    python scripts/fix_iam_phase2.py
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

import boto3
from dotenv import load_dotenv

load_dotenv(override=True, dotenv_path=PROJECT_ROOT / ".env")

IAM_USER    = "shoeprint-dev"
POLICY_NAME = "GaitwayPhase2Provisioning"
ACCOUNT_ID  = "791209948637"
REGION      = "us-east-2"

# Minimum-privilege policy for provision_rds.py
POLICY_DOCUMENT = {
    "Version": "2012-10-17",
    "Statement": [
        {
            "Sid": "EC2SecurityGroup",
            "Effect": "Allow",
            "Action": [
                "ec2:CreateSecurityGroup",
                "ec2:DescribeSecurityGroups",
                "ec2:AuthorizeSecurityGroupIngress",
                "ec2:RevokeSecurityGroupIngress",
                "ec2:DeleteSecurityGroup",
                "ec2:DescribeVpcs",
                "ec2:DescribeSubnets",
            ],
            "Resource": "*",
        },
        {
            "Sid": "RDSProvisioning",
            "Effect": "Allow",
            "Action": [
                "rds:CreateDBInstance",
                "rds:DescribeDBInstances",
                "rds:ModifyDBInstance",
                "rds:DeleteDBInstance",
                "rds:AddTagsToResource",
                "rds:ListTagsForResource",
                "rds:DescribeDBEngineVersions",
                "rds:DescribeOrderableDBInstanceOptions",
            ],
            "Resource": "*",
        },
        {
            "Sid": "SecretsManager",
            "Effect": "Allow",
            "Action": [
                "secretsmanager:CreateSecret",
                "secretsmanager:UpdateSecret",
                "secretsmanager:GetSecretValue",
                "secretsmanager:DescribeSecret",
                "secretsmanager:TagResource",
            ],
            "Resource": f"arn:aws:secretsmanager:{REGION}:{ACCOUNT_ID}:secret:gaitway/*",
        },
        {
            "Sid": "IAMSelfCheck",
            "Effect": "Allow",
            "Action": [
                "iam:GetUser",
                "iam:ListAttachedUserPolicies",
                "iam:ListUserPolicies",
            ],
            "Resource": f"arn:aws:iam::{ACCOUNT_ID}:user/{IAM_USER}",
        },
    ],
}


def main() -> None:
    print(f"Connecting to IAM (account {ACCOUNT_ID})…")
    iam = boto3.client("iam", region_name=REGION)

    # ── Show current state ──────────────────────────────────────────────────
    print(f"\nCurrent policies for {IAM_USER}:")
    managed = iam.list_attached_user_policies(UserName=IAM_USER)["AttachedPolicies"]
    inline  = iam.list_user_policies(UserName=IAM_USER)["PolicyNames"]

    if managed:
        for p in managed:
            print(f"  [managed] {p['PolicyName']}  {p['PolicyArn']}")
    else:
        print("  (no managed policies)")

    if inline:
        for p in inline:
            print(f"  [inline]  {p}")
    else:
        print("  (no inline policies)")

    # ── Attach / update inline policy ───────────────────────────────────────
    print(f"\nAttaching inline policy '{POLICY_NAME}' to {IAM_USER}…")
    iam.put_user_policy(
        UserName=IAM_USER,
        PolicyName=POLICY_NAME,
        PolicyDocument=json.dumps(POLICY_DOCUMENT),
    )
    print("  ✅ Policy attached successfully!")

    # ── Verify ──────────────────────────────────────────────────────────────
    inline_after = iam.list_user_policies(UserName=IAM_USER)["PolicyNames"]
    print(f"\nInline policies after update: {inline_after}")

    print("""
Next step:
    python scripts/provision_rds.py
""")


if __name__ == "__main__":
    main()
