"""
fix_iam_slr.py — Add iam:CreateServiceLinkedRole for RDS to shoeprint-dev
=========================================================================
Run this with admin credentials (not shoeprint-dev) OR use the AWS Console
to update the GaitwayPhaseProv inline policy with the JSON printed below.

Usage:
    python scripts/fix_iam_slr.py

If it fails with AccessDenied, copy the UPDATED POLICY JSON printed below
into the AWS Console:
  IAM -> Users -> shoeprint-dev -> Permissions ->
  GaitwayPhaseProv -> Edit -> JSON -> paste -> Save changes
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

import boto3
from dotenv import load_dotenv

load_dotenv(override=True, dotenv_path=PROJECT_ROOT / ".env")

IAM_USER    = "shoeprint-dev"
POLICY_NAME = "GaitwayPhaseProv"
ACCOUNT_ID  = "791209948637"
REGION      = "us-east-2"

# Full updated policy — adds iam:CreateServiceLinkedRole for RDS
UPDATED_POLICY = {
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
                "ec2:DescribeVpcs",
                "ec2:DescribeSubnets"
            ],
            "Resource": "*"
        },
        {
            "Sid": "RDSProvisioning",
            "Effect": "Allow",
            "Action": [
                "rds:CreateDBInstance",
                "rds:DescribeDBInstances",
                "rds:ModifyDBInstance",
                "rds:AddTagsToResource",
                "rds:ListTagsForResource"
            ],
            "Resource": "*"
        },
        {
            "Sid": "RDSServiceLinkedRole",
            "Effect": "Allow",
            "Action": "iam:CreateServiceLinkedRole",
            "Resource": f"arn:aws:iam::{ACCOUNT_ID}:role/aws-service-role/rds.amazonaws.com/AWSServiceRoleForRDS",
            "Condition": {
                "StringLike": {
                    "iam:AWSServiceName": "rds.amazonaws.com"
                }
            }
        },
        {
            "Sid": "SecretsManager",
            "Effect": "Allow",
            "Action": [
                "secretsmanager:CreateSecret",
                "secretsmanager:UpdateSecret",
                "secretsmanager:GetSecretValue",
                "secretsmanager:DescribeSecret"
            ],
            "Resource": f"arn:aws:secretsmanager:{REGION}:{ACCOUNT_ID}:secret:gaitway/*"
        }
    ]
}


def main() -> None:
    print("=" * 65)
    print("  Gaitway — IAM SLR Fix for RDS")
    print("=" * 65)

    # Always print the JSON so user can paste it manually if needed
    print(f"\n--- UPDATED POLICY JSON (paste into AWS Console if script fails) ---\n")
    print(json.dumps(UPDATED_POLICY, indent=2))
    print("\n" + "-" * 65)

    print(f"\nAttempting to update {POLICY_NAME} via boto3...")
    try:
        iam = boto3.client("iam", region_name=REGION)
        iam.put_user_policy(
            UserName=IAM_USER,
            PolicyName=POLICY_NAME,
            PolicyDocument=json.dumps(UPDATED_POLICY),
        )
        print("  [OK] Policy updated via boto3!")
        print("\nNext step: python -X utf8 scripts/provision_rds.py")
    except Exception as e:
        print(f"  [FAILED] {e}")
        print("\nAction required:")
        print("  1. Go to: IAM -> Users -> shoeprint-dev -> Permissions")
        print("  2. Click GaitwayPhaseProv -> Edit")
        print("  3. Switch to JSON tab")
        print("  4. Paste the JSON printed above")
        print("  5. Click 'Save changes'")
        print("  6. Re-run: python -X utf8 scripts/provision_rds.py")


if __name__ == "__main__":
    main()
