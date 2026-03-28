# Tech Context — Gaitway Footwear Intelligence Database

## Development Environment
- **OS:** Windows 11 (host) / Debian Bookworm (Dev Container)
- **IDE:** Visual Studio Code
- **AI Assistant:** Cline (Claude)
- **Container:** Docker Desktop + VS Code Dev Containers
- **Shell:** PowerShell (host) / bash (container)

## Installed Tools (as of 2026-03-01)
| Tool | Version | Location |
|------|---------|----------|
| Python | 3.13 | Dev Container |
| pip | latest | Dev Container |
| AWS CLI | v2 (latest) | Dev Container |
| Git | 2.52.0 | Host + Container |
| GitHub CLI (gh) | 2.87.3 | Host |
| Node.js | 24.14.0 (LTS) | Host |
| Docker Desktop | 4.60.1 | Host |

## VS Code Extensions
| Extension | Purpose |
|-----------|---------|
| ms-python.python | Python language support |
| ms-python.vscode-pylance | Type checking |
| ms-python.debugpy | Python debugging |
| ms-python.vscode-python-envs | Virtual environments |
| ms-azuretools.vscode-containers | Dev Containers |
| github.vscode-pull-request-github | GitHub integration |
| ms-toolsai.jupyter | Notebooks |
| saoudrizwan.claude-dev | Cline AI assistant |
| amazonwebservices.aws-toolkit-vscode | AWS resource browser |
| ms-python.black-formatter | Code formatting |
| charliermarsh.ruff | Fast Python linter |

## Python Dependencies (requirements.txt)
| Package | Purpose |
|---------|---------|
| boto3 / botocore | AWS SDK |
| Pillow | Image processing |
| requests | HTTP client |
| beautifulsoup4 / lxml | Web scraping |
| pandas | Data handling |
| python-dotenv | .env file loading |
| psycopg2-binary | PostgreSQL driver |
| SQLAlchemy | ORM / database layer |
| fastapi + uvicorn | REST API backend |
| black / pylint / ruff | Code quality |
| pytest / pytest-cov | Testing framework |
| httpx / python-multipart | HTTP utilities |
| alembic | DB migrations |
| pgvector | Vector similarity (Python client) |
| typer | CLI commands |
| opencv-python | Image preprocessing |
| stripe | Stripe billing integration |
| pyyaml | YAML config parsing |

## AWS Services (Gaitway Architecture)
| Service | Purpose | Status |
|---------|---------|--------|
| S3 | Store shoe images (raw, processed, impressions, thumbnails, crime-scene, user-shoes) | 🔧 Phase 0 |
| RDS PostgreSQL + pgvector | Shoe metadata + vector similarity search | 📋 Phase 2 |
| ECS Fargate | 3 containerized services (API, Scraper, ImageProcessor) | 📋 Phase 8 |
| EventBridge | Schedule scraper at 1:00 AM CST daily | 📋 Phase 3 |
| CloudFront | CDN for React SPA (+ presigned URL acceleration) | 📋 Phase 8 |
| CloudWatch | Logging and monitoring | 📋 Phase 8 |
| CloudTrail | Forensic audit logging (required) | 📋 Phase 8 |
| Cognito | User auth (JWT, MFA) | 📋 Phase 6 |
| Secrets Manager | Production secrets (DB, Stripe, Cognito) | 📋 Phase 8 |
| ALB | Load balancer in front of ECS API service | 📋 Phase 8 |

> ❌ AWS Rekognition — **removed from architecture**. Replaced by self-hosted
> pgvector (HNSW index) + ResNet/ViT embeddings. Reasons: cost, control,
> forensic auditability of embedding model versions.

## Tech Stack
| Category | Technology | Notes |
|----------|-----------|-------|
| Language | Python 3.13 | |
| Web Framework | FastAPI | 3 separate ECS services |
| Image Processing | OpenCV + Pillow | Preprocessing pipeline |
| ML / Embeddings | ResNet or ViT (pluggable) | Upper/sole classifier + embeddings |
| Vector Search | pgvector (HNSW index) | Replaces AWS Rekognition |
| Database | PostgreSQL (RDS) | + pgvector extension |
| Storage | AWS S3 (us-east-2) | Presigned URLs, fully private |
| Auth | AWS Cognito | JWT + MFA |
| Billing | Stripe | $1,200/year, auto-renew |
| Container | Docker (Dev Containers + ECS/Fargate) | |
| Frontend | React SPA | Forensic-lab theme |
| Version Control | Git + GitHub | |
| CI/CD | GitHub Actions | |
| Cloud | AWS (us-east-2, Ohio) | |
| AI Assistant | Cline (Claude) | |

## AWS Account & Region
| Setting | Value |
|---------|-------|
| Account ID | `791209948637` |
| Account Name | TI Forensic Services |
| Primary Region | `us-east-2` (Ohio) |
| IAM User | `shoeprint-dev` (programmatic access) |
| S3 Bucket | `gaitway-footwear-791209948637` |

## Key Paths
- **Project Root (container):** `/workspaces/simple-webpage-hosting-test`
- **Project Root (host):** `C:\AI-Testing\simple-webpage-hosting-test`
- **GitHub:** https://github.com/tiforensicservices/simple-webpage-hosting-test

## Stripe Configuration
| Setting | Value |
|---------|-------|
| Stripe Account | TI Forensic Services (`acct_1SvoCyFABZBsDngL`) |
| Stripe Product ID | `prod_TtcDNkZohuUdvB` |
| Price | $1,200 USD/year (annual, auto-renew) |
| API Version | `2026-01-28.clover` |

## Security Notes
- AWS credentials stored ONLY in `.env` (gitignored); Secrets Manager in production
- `.env.example` provides safe template (committed, no real values)
- IAM user `shoeprint-dev` — programmatic access only, not root
- S3 bucket: public access blocked, AES-256 encryption, versioning enabled
- Images accessed via presigned URLs only (never public)
- Cognito JWT required on all API endpoints; subscription status checked by middleware
- CloudTrail must be enabled on AWS account (forensic audit requirement)
- Every CrimeSceneQuery logged in DB with full params + results (forensic transparency)
- ML model versions tracked for forensic reproducibility

## Key Architecture Decisions (with rationale)
| Decision | Rationale |
|----------|-----------|
| pgvector instead of Rekognition | Lower cost, full control, forensic model versioning |
| 3 ECS services (not monolith) | Independent scaling, fault isolation, separate deploy cycles |
| Cognito for auth | Managed MFA, JWT integration, reduces auth code surface |
| `us-east-2` (Ohio) | Dedicated Gaitway region, corrected from initial `us-east-1` |
| Presigned URLs only | S3 bucket stays 100% private; audit log captures every access |
| HNSW index in pgvector | Best ANN performance for cosine similarity at expected dataset size |
| EventBridge → 1:00 AM CST | Off-peak scraping; consistent, auditable schedule |
