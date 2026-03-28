# System Patterns — Gaitway Footwear Intelligence Database

## Architecture Overview
Three-service containerized backend on ECS Fargate, with a React SPA frontend,
scheduled scraping via EventBridge, and PostgreSQL + pgvector for search.

```
Developer (Windows 11 + VS Code)
    ↓
Dev Container (Docker — Python 3.13 + AWS CLI)   ← All development here
    ↓
Git / GitHub + GitHub Actions (CI/CD)            ← Automated testing on push
    ↓
AWS us-east-2 (Ohio)                             ← Production hosting
```

## AWS Architecture (Gaitway)

```
┌─────────────────────────────────────────────────────────────────────┐
│  DATA INGESTION — Scheduled (EventBridge → 1:00 AM CST daily)       │
│  ECS Task: ScraperService                                           │
│  → ZapposScraper / AmazonScraper / DSWScraper / ... (14+ sites)    │
│  → Respects robots.txt + rate limits                                │
│  → Raw images → S3 raw/                                             │
│  → Metadata → RDS PostgreSQL (Shoe + ShoeImage tables)             │
└──────────────────────────┬──────────────────────────────────────────┘
                           │ S3 raw/ upload event
┌──────────────────────────▼──────────────────────────────────────────┐
│  IMAGE PROCESSING PIPELINE                                          │
│  ECS Service: ImageProcessorService                                 │
│  → Upper / sole classifier (CNN/ViT — pluggable model)             │
│  → pHash dedup (compare against existing ShoeImage records)        │
│  → OpenCV preprocessing (grayscale, contrast, denoising,           │
│    orientation normalization)                                       │
│  → Synthetic AI test impression (high-contrast 2D scene print)     │
│  → Vector embedding (ResNet/ViT) → pgvector index                  │
│  → Processed images → S3 processed/ + thumbnails/ + impressions/   │
│  → Update RDS (ShoeImage: pHash, embedding, s3 keys)               │
└──────────────────────────┬──────────────────────────────────────────┘
                           │
┌──────────────────────────▼──────────────────────────────────────────┐
│  DATABASE LAYER                                                     │
│  S3 gaitway-footwear-791209948637 (us-east-2)                      │
│    raw/          — Original scraper images                         │
│    processed/    — Normalized outsole & upper images               │
│    impressions/  — AI-generated synthetic test impressions         │
│    thumbnails/   — Web preview images                              │
│    crime-scene/  — Crime scene uploads (per workspace)             │
│    user-shoes/   — User upload wizard images                       │
│  RDS PostgreSQL (us-east-2) + pgvector extension                   │
│    Users / Workspaces / Shoes / ShoeImages                         │
│    CrimeSceneQuery / SubscriptionPlan / UserSubscription           │
│  Access: presigned URLs only (bucket is 100% private)              │
└──────────────────────────┬──────────────────────────────────────────┘
                           │
┌──────────────────────────▼──────────────────────────────────────────┐
│  API LAYER                                                          │
│  ECS Service: APIService (FastAPI + uvicorn)                       │
│  → Cognito JWT middleware (auth + subscription check)              │
│  → /shoes/search — metadata filters + outsole AI impression grid  │
│  → /crime-scene/search — upload + cosine similarity search        │
│  → /upload — upload wizard (4-step)                               │
│  → /admin — crawl status, maintenance triggers                    │
│  → /stripe/webhook — subscription lifecycle                       │
│  ALB (Application Load Balancer) in front of ECS                  │
└──────────────────────────┬──────────────────────────────────────────┘
                           │
┌──────────────────────────▼──────────────────────────────────────────┐
│  FRONTEND                                                           │
│  React SPA → S3 + CloudFront CDN                                   │
│  → Dashboard, Search & Compare, Crime Scene Search                 │
│  → Upload Wizard, Subscription Page                                │
│  → Forensic-lab aesthetic / high-contrast theme                    │
└──────────────────────────┬──────────────────────────────────────────┘
                           │
┌──────────────────────────▼──────────────────────────────────────────┐
│  CRIME SCENE SEARCH PIPELINE                                        │
│  Upload → grayscale → perspective correction → contrast enhance    │
│  → background suppression → CRF segmentation                      │
│  → multi-variant embedding (same CNN as AI impressions)            │
│  → cosine similarity search via pgvector (HNSW index)             │
│  → ranked candidates + scores → forensic audit log                │
│  All queries logged in CrimeSceneQuery (forensic transparency)     │
└─────────────────────────────────────────────────────────────────────┘
```

## S3 Bucket Structure
```
gaitway-footwear-791209948637/   (us-east-2, private, AES-256, versioned)
├── raw/           ← Original scraper images (unmodified)
├── processed/     ← Normalized outsole & upper images
├── impressions/   ← AI-generated synthetic test impressions
├── thumbnails/    ← Small previews for web display
├── crime-scene/   ← Crime scene footwear uploads (per workspace)
└── user-shoes/    ← User-uploaded shoes via upload wizard
```

## Database Entities
| Entity | Key Fields |
|--------|-----------|
| `User` | id, email, cognito_sub, created_at |
| `Workspace` | id, user_id, name, subscription_status |
| `Shoe` | id, external_site, external_id, brand, model_name, category, gender, colorway, price, description |
| `ShoeImage` | id, shoe_id, image_type (upper/sole), s3_raw_key, s3_processed_key, s3_thumbnail_key, phash, embedding (vector), dimensions |
| `CrimeSceneQuery` | id, workspace_id, s3_key, variants_json, results_json, created_at |
| `SubscriptionPlan` | id, stripe_price_id, name, price_usd, interval |
| `UserSubscription` | id, user_id, stripe_subscription_id, status, current_period_end |

## Service Boundaries (3 ECS Services)
| Service | Responsibility |
|---------|---------------|
| `APIService` | FastAPI REST API, Cognito auth, Stripe webhooks, presigned URLs |
| `ScraperService` | Site-specific scrapers, dedup checks, S3 raw upload, RDS writes |
| `ImageProcessorService` | Classification, preprocessing, impressions, embeddings, pHash |

## Development Principles
1. **Container-first** — All dev work inside Dev Container, no host dependencies
2. **Git for everything** — Every change committed with meaningful message
3. **No hardcoded secrets** — AWS keys ONLY in `.env` (gitignored); Secrets Manager in prod
4. **Document as you go** — Memory bank updated after significant changes
5. **Small, focused commits** — Prefer many small commits over large ones
6. **Test before commit** — `pytest tests/` must pass before pushing
7. **Security by default** — Encryption, private access, audit logging from day one
8. **Forensic auditability** — Every crime scene query logged; ML models versioned

## Branching Strategy (Git Flow Lite)
- `main` — Production-ready code only
- `develop` — Integration branch for features
- `feature/[name]` — Individual feature branches
- `fix/[name]` — Bug fix branches

## File Structure (Target)
```
project-root/
├── .devcontainer/              # Docker dev environment (Python + AWS CLI)
│   ├── devcontainer.json
│   └── Dockerfile
├── .github/
│   └── workflows/
│       └── ci.yml              # GitHub Actions CI pipeline
├── memory-bank/                # Cline project memory files
├── docs/
│   ├── aws-setup-guide.md
│   └── build-plan.md
├── src/
│   ├── aws/
│   │   └── setup_s3.py         # S3 bucket creation script
│   ├── api/                    # FastAPI app (Phase 1+)
│   ├── models/                 # SQLAlchemy models (Phase 1+)
│   ├── scraper/                # Scraper classes (Phase 0.5+)
│   └── pipeline/               # Image processing pipeline (Phase 4+)
├── tests/
│   └── test_setup_s3.py        # Unit tests
├── config/
│   └── scrapers.yaml           # Scraper config (Phase 1+)
├── .clinerules                 # Cline AI standards
├── .env.example                # Safe credential template (committed)
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
- IAM: Separate `shoeprint-dev` user (may be renamed to `gaitway-dev`), not root
- ECS: Task-level IAM roles (least privilege per service)
- S3: Public access blocked, AES-256 encryption, versioning enabled, presigned URLs only
- Auth: AWS Cognito (JWT + MFA); active subscription check on API middleware
- Secrets: `.env` in dev; AWS Secrets Manager in production
- Audit: CloudTrail enabled (forensic requirement); CrimeSceneQuery log in DB
- Lifecycle: Automatic cost optimization (S3 → IA after 90d → Glacier after 365d)
