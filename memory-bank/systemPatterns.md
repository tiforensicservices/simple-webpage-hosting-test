# System Patterns

## Architecture Overview
This project follows a containerized development workflow targeting AWS cloud hosting
for a forensic shoe print image database and automated search system.

```
Developer (Windows 11 + VS Code)
    ↓
Dev Container (Docker — Python 3.13 + AWS CLI)   ← All development here
    ↓
Git / GitHub + GitHub Actions (CI/CD)            ← Automated testing on push
    ↓
AWS                                               ← Production hosting
```

## AWS Architecture (Shoe Print Image System)

```
┌─────────────────────────────────────────────────────────────────┐
│  DATA INGESTION                                                  │
│  Manual upload / Automated scraper → S3 (raw/)                  │
└────────────────────────┬────────────────────────────────────────┘
                         │ S3 Event Trigger
┌────────────────────────▼────────────────────────────────────────┐
│  PROCESSING PIPELINE (Lambda)                                    │
│  → Normalize / resize image                                      │
│  → Extract metadata                                              │
│  → AWS Rekognition (feature extraction / similarity)            │
│  → Store processed image → S3 (processed/ + thumbnails/)        │
│  → Write metadata → RDS PostgreSQL                               │
└────────────────────────┬────────────────────────────────────────┘
                         │
┌────────────────────────▼────────────────────────────────────────┐
│  DATABASE LAYER                                                  │
│  S3 — original + processed images                                │
│  RDS PostgreSQL — metadata (brand, model, tread ID, confidence) │
│  Rekognition Collection — visual similarity index                │
└────────────────────────┬────────────────────────────────────────┘
                         │
┌────────────────────────▼────────────────────────────────────────┐
│  APPLICATION LAYER (ECS / Fargate)                              │
│  FastAPI backend — search API, upload API, admin endpoints      │
│  CloudFront CDN — serve images fast globally                    │
│  API Gateway — public-facing endpoints (if serverless)          │
└────────────────────────┬────────────────────────────────────────┘
                         │
┌────────────────────────▼────────────────────────────────────────┐
│  AUTOMATED SEARCH (Scheduled)                                    │
│  EventBridge → Lambda / ECS Task                                │
│  → Scrape web for new shoe releases                              │
│  → Compare to existing database                                  │
│  → SNS/SES notification on new matches                          │
└─────────────────────────────────────────────────────────────────┘
```

## S3 Bucket Structure
```
shoeprint-images-{account_id}/
├── raw/           ← Original uploaded images (unmodified)
├── processed/     ← Normalized, resized images
└── thumbnails/    ← Small previews for web display
```

## Development Principles
1. **Container-first** — All dev work inside Dev Container, no host dependencies
2. **Git for everything** — Every change committed with meaningful message
3. **No hardcoded secrets** — AWS keys ONLY in `.env` (gitignored)
4. **Document as you go** — Memory bank updated after significant changes
5. **Small, focused commits** — Prefer many small commits over large ones
6. **Test before commit** — `pytest tests/` must pass before pushing
7. **Security by default** — Encryption, private access, audit logging from day one

## Branching Strategy (Git Flow Lite)
- `main` — Production-ready code only
- `develop` — Integration branch for features
- `feature/[name]` — Individual feature branches
- `fix/[name]` — Bug fix branches

## File Structure
```
project-root/
├── .devcontainer/          # Docker dev environment (Python + AWS CLI)
│   ├── devcontainer.json
│   └── Dockerfile
├── .github/
│   └── workflows/
│       └── ci.yml          # GitHub Actions CI pipeline
├── memory-bank/            # Cline project memory files
├── src/
│   └── aws/
│       └── setup_s3.py     # S3 bucket creation script
├── tests/
│   └── test_setup_s3.py    # Unit tests
├── docs/
│   └── aws-setup-guide.md  # Step-by-step AWS IAM + S3 setup
├── .clinerules             # Cline AI standards
├── .env.example            # Safe credential template (committed)
├── .gitignore
├── requirements.txt
└── README.md
```

## CI/CD Pipeline (GitHub Actions)
On every push to `main` or `develop`:
1. Install Python 3.13 + dependencies
2. Run `ruff` linter
3. Check `black` formatting
4. Run `pytest` with coverage
5. On `main` only: scan for hardcoded secrets

## Security Patterns
- IAM: Separate `shoeprint-dev` user, not root
- S3: Public access blocked, AES-256 encryption, versioning enabled
- Credentials: Environment variables only, never in code or git
- Audit: CloudTrail enabled (forensic requirement)
- Lifecycle: Automatic cost optimization (S3 → IA → Glacier)
