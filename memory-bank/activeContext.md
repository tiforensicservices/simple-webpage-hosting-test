# Active Context

## Current Focus
Setting up AWS infrastructure and project scaffolding for the Shoe Print Image System.
Dev Container, project structure, S3 setup script, CI/CD pipeline, and documentation
are all created. Next: Create IAM user in AWS Console, configure `.env`, and do first commit.

## What Was Just Done (2026-03-01)
- Created `.devcontainer/devcontainer.json` and `Dockerfile`
  - Python 3.13-slim-bookworm base image
  - AWS CLI v2 installed inside container
  - All Python packages defined in `requirements.txt`
- Created `requirements.txt` with boto3, Pillow, FastAPI, SQLAlchemy, etc.
- Created `.env.example` — safe template for AWS credentials (committed)
- Created `src/aws/setup_s3.py` — full S3 bucket setup script with:
  - Bucket creation
  - Public access block
  - AES-256 encryption
  - Versioning
  - Lifecycle policy (→ Standard-IA at 90 days, → Glacier at 365 days)
  - Folder structure (raw/, processed/, thumbnails/)
- Created `tests/test_setup_s3.py` — unit tests
- Created `docs/aws-setup-guide.md` — step-by-step AWS IAM + S3 setup guide
- Created `.github/workflows/ci.yml` — GitHub Actions CI pipeline
- Updated all memory bank files with new shoe print system scope

## In Progress
- **Step 3:** User needs to create IAM user in AWS Console (see `docs/aws-setup-guide.md`)
- **Step 2:** Push initial commit to GitHub on `develop` branch

## Next Steps
1. 🙋 **User action:** Follow `docs/aws-setup-guide.md` to create IAM user + access keys
2. 🙋 **User action:** Copy `.env.example` → `.env` and fill in credentials
3. ✅ Run `python src/aws/setup_s3.py` inside Dev Container to create S3 bucket
4. Open project in Dev Container (VS Code "Reopen in Container")
5. Begin planning image ingestion pipeline

## Current Blockers
- None — Dev Container needs to be rebuilt to pick up new `.devcontainer/` config
- IAM credentials needed before running `setup_s3.py`
