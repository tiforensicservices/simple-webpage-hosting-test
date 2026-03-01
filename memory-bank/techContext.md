# Tech Context

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

## AWS Services (Planned Architecture)
| Service | Purpose |
|---------|---------|
| S3 | Store shoe print images (raw, processed, thumbnails) |
| RDS PostgreSQL | Shoe metadata database |
| Lambda | Image processing on S3 upload trigger |
| AWS Rekognition | Visual similarity search for shoe prints |
| ECS / Fargate | Run containerized FastAPI backend |
| EventBridge | Schedule automated shoe scraper |
| CloudFront | CDN for fast image delivery |
| CloudWatch | Logging and monitoring |
| CloudTrail | Audit logging (forensic requirement) |
| SNS / SES | Notifications when new matches found |

## Tech Stack
| Category | Technology |
|----------|-----------|
| Language | Python 3.13 |
| Web Framework | FastAPI |
| Image Processing | Pillow + AWS Rekognition |
| Database | PostgreSQL (RDS) |
| Storage | AWS S3 |
| Container | Docker (Dev Containers + ECS/Fargate) |
| Version Control | Git + GitHub |
| CI/CD | GitHub Actions |
| Cloud | AWS |
| AI Assistant | Cline (Claude) |

## Key Paths
- **Project Root:** `/workspaces/simple-webpage-hosting-test` (container)
- **Host Root:** `C:\AI-Testing\simple-webpage-hosting-test`
- **GitHub:** https://github.com/tiforensicservices/simple-webpage-hosting-test

## Security Notes
- AWS credentials stored ONLY in `.env` (gitignored)
- `.env.example` provides safe template (committed)
- IAM user `shoeprint-dev` — programmatic access only, not root
- S3 bucket: public access blocked, AES-256 encryption, versioning enabled
- CloudTrail must be enabled on AWS account (forensic audit requirement)
