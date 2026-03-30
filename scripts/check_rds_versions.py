"""List available PostgreSQL versions in the RDS region."""
import boto3, sys
from pathlib import Path
from dotenv import load_dotenv
load_dotenv(override=True, dotenv_path=Path(__file__).parent.parent / ".env")

rds = boto3.client("rds", region_name="us-east-2")
r = rds.describe_db_engine_versions(
    Engine="postgres",
    Filters=[{"Name": "engine-version", "Values": ["16.%"]}],
)
versions = sorted(set(v["EngineVersion"] for v in r["DBEngineVersions"]))
if versions:
    print("Available PostgreSQL 16.x versions in us-east-2:")
    for v in versions:
        print(" ", v)
else:
    # No filter match — list all postgres versions
    r2 = rds.describe_db_engine_versions(Engine="postgres")
    all_v = sorted(set(v["EngineVersion"] for v in r2["DBEngineVersions"] if v["EngineVersion"].startswith("16.")))
    print("PostgreSQL 16.x versions (unfiltered):")
    for v in all_v:
        print(" ", v)
