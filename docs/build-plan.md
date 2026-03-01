# Gaitway Footwear Intelligence Database — Build Plan

**Created:** 2026-03-01
**Last Updated:** 2026-03-01
**Status:** Phase 0 — Infrastructure Setup

---

## Project Overview

Gaitway is a cloud-hosted forensic footwear platform that automatically collects shoe
data from retail sites and supports crime-scene footwear impression searches. It builds
a centralized, searchable database of footwear (uppers and soles), generates standardized
AI test impressions from outsole images, and compares them with crime-scene footwear
impressions to suggest likely shoe models.

**Business Model:** $1,200/year annual subscription (Stripe)
**Target Users:** Forensic examiners, law enforcement agencies, forensic labs

---

## Architecture Summary

```
┌──────────────────────────────────────────────────────────────────────┐
│  DATA INGESTION                                                       │
│  Scheduled scraper (EventBridge → ECS) → 14+ retailer sites          │
│  User uploads via Upload Wizard → S3 gaitway/raw/                    │
└──────────────────────┬───────────────────────────────────────────────┘
                       │ S3 Event / direct trigger
┌──────────────────────▼───────────────────────────────────────────────┐
│  PROCESSING PIPELINE (ECS Task / Lambda)                              │
│  → Classify upper vs sole (CNN/ViT)                                   │
│  → pHash dedup (skip duplicates)                                      │
│  → OpenCV preprocessing (grayscale, contrast, denoise, orient)       │
│  → Generate AI test impression (synthetic 2D scene print)            │
│  → Compute vector embedding (ResNet/ViT → pgvector)                  │
│  → Store processed image + thumbnail → S3                             │
│  → Write metadata → RDS PostgreSQL                                    │
└──────────────────────┬───────────────────────────────────────────────┘
                       │
┌──────────────────────▼───────────────────────────────────────────────┐
│  DATABASE LAYER                                                       │
│  S3 — raw, processed, impressions, thumbnails, crime-scene, user     │
│  RDS PostgreSQL + pgvector — metadata, embeddings, dedup hashes      │
│  Entities: User, Workspace, Shoe, ShoeImage, CrimeSceneQuery,       │
│            SubscriptionPlan, UserSubscription                         │
└──────────────────────┬───────────────────────────────────────────────┘
                       │
┌──────────────────────▼───────────────────────────────────────────────┐
│  APPLICATION LAYER                                                    │
│  FastAPI backend on ECS Fargate (us-east-2)                          │
│  React SPA on S3 + CloudFront                                        │
│  Cognito authentication + subscription middleware                    │
│  Stripe billing ($1,200/year)                                        │
└──────────────────────┬───────────────────────────────────────────────┘
                       │
┌──────────────────────▼───────────────────────────────────────────────┐
│  CRIME SCENE SEARCH                                                   │
│  Upload → preprocess (grayscale, perspective, contrast, CRF)        │
│  → Multi-variant generation → Embed each variant                     │
│  → Cosine similarity vs pgvector index → Ranked candidates           │
│  → Full audit logging in CrimeSceneQuery                             │
└──────────────────────────────────────────────────────────────────────┘
```

**Three separate services** (not monolithic):
1. **API Service** — FastAPI, lean, handles web requests (24/7)
2. **Scraper Worker** — ECS task triggered by EventBridge (runs ~4 hrs/day)
3. **Image Processor** — ECS task triggered by S3 events (runs on demand)

---

## Phase Plan

### Phase 0 — Infrastructure Corrections (2–4 hours)

| Task | Details |
|---|---|
| Create S3 bucket | `gaitway-footwear-791209948637` in `us-east-2` |
| S3 folder structure | `gaitway/raw/`, `gaitway/processed/`, `gaitway/impressions/`, `gaitway/thumbnails/`, `gaitway/crime-scene/`, `gaitway/user-shoes/` |
| Update region | All config from `us-east-1` → `us-east-2` |
| Rename project refs | "Shoeprint" → "Gaitway Footwear Intelligence Database" |
| IAM role planning | Document production role structure |
| Update memory bank | Full brief in `projectbrief.md` |

**Build cost:** $0

---

### Phase 0.5 — End-to-End Proof of Concept (1–2 weeks)

Prove the full pipeline works with ONE retailer (Zappos recommended):

| Task | Details |
|---|---|
| Write `ZapposScraper` | Extract brand, model, images, metadata |
| Upload to S3 | Raw images → `gaitway/raw/` |
| Classify upper vs sole | Pre-trained ResNet50 with transfer learning |
| Generate AI impression | OpenCV: grayscale → contrast → denoise → synthetic impression |
| Store embedding | Vector in local PostgreSQL + pgvector |
| Search by embedding | Prove cosine similarity returns correct results |

**Build cost:** ~$0–5

---

### Phase 1 — Backend Foundation (1–2 weeks)

Project structure:
```
src/
├── api/                  # FastAPI application
│   ├── main.py
│   ├── routes/
│   │   ├── auth.py
│   │   ├── shoes.py
│   │   ├── search.py
│   │   ├── crime_scene.py
│   │   ├── admin.py
│   │   └── subscription.py
│   ├── middleware/
│   │   ├── auth.py
│   │   └── subscription.py
│   └── schemas/          # Pydantic request/response models
├── models/               # SQLAlchemy ORM models
│   ├── user.py           # User, Workspace
│   ├── shoe.py           # Shoe, ShoeImage
│   ├── crime_scene.py    # CrimeSceneQuery
│   └── subscription.py   # SubscriptionPlan, UserSubscription
├── scraper/              # Web scraping framework
│   ├── base.py           # BaseScraper class
│   ├── sites/            # Site-specific scrapers
│   └── config.py         # YAML config loader
├── pipeline/             # Image processing
│   ├── classifier.py     # Upper/sole CNN classifier
│   ├── preprocessor.py   # OpenCV preprocessing
│   ├── impression.py     # AI impression generator
│   ├── embedder.py       # Vector embedding generator
│   └── dedup.py          # pHash + embedding deduplication
├── cli.py                # Typer CLI
└── config/
    ├── scrapers.yaml     # Target sites + rate limits
    └── pipeline.yaml     # Dedupe thresholds, model paths
```

| Task | Details |
|---|---|
| SQLAlchemy models | All 7 entities with pgvector column types |
| Alembic | Database migration framework |
| Typer CLI | `init-db`, `crawl-all`, `crawl-site`, `dedupe-images`, `reindex`, `crime-scene-search` |
| YAML config | Scraper targets, rate limits, dedupe thresholds |
| Auth decision | AWS Cognito recommended |
| FastAPI skeleton | CORS, error handlers, health check |

**Build cost:** $0

---

### Phase 2 — RDS PostgreSQL + pgvector (3–5 days)

| Task | Details |
|---|---|
| Provision RDS | PostgreSQL 16 + pgvector, `us-east-2` |
| Instance | `db.t3.medium` (2 vCPU, 4GB RAM) — minimum for pgvector |
| Storage | 20GB gp3, auto-scaling |
| Security | Only ECS/dev container security group access |
| Migrations | `alembic upgrade head` |
| pgvector index | HNSW index on embedding columns |
| Backups | Automated daily, 7-day retention |

**Build cost:** ~$50/month once provisioned

---

### Phase 3 — Scraper Framework + First Retailers (3–4 weeks)

| Week | Task |
|---|---|
| 1 | `BaseScraper` class: robots.txt, rate limiting, retry logic, structured logging, proxy rotation |
| 1 | Anti-bot infrastructure: proxy rotation, user-agent rotation, random delays, Playwright for JS sites |
| 1 | Deduplication logic: primary `(external_site, external_id)`, secondary `(brand, model, colorway)` |
| 2 | `ZapposScraper` (harden from PoC), `AmazonScraper` (ASIN-based, multi-domain) |
| 3 | `DSWScraper`, `FootlockerScraper`, `FinishLineScraper`, `ShoeCarnivalScraper` |
| 4 | Testing, reliability, EventBridge rule (1:00 AM CST daily trigger) |

**Target sites (14+):** Amazon (.com + intl), Zappos, DSW, Footlocker, FinishLine,
ShoeCarnival, ShoeMall, ShoePalace, FootwearEtc, Zalando, ASOS, Taobao, JD

**Build cost:** ~$30–75/month for residential proxies

---

### Phase 4 — Image Processing Pipeline (3–5 weeks)

| Week | Task |
|---|---|
| 1 | Upper/Sole classifier (ResNet50/EfficientNet transfer learning, ~500–1000 labeled images) |
| 1–2 | pHash deduplication (`imagehash` library, configurable Hamming distance) |
| 2–3 | OpenCV preprocessing (grayscale, CLAHE, bilateral denoising, orientation normalization) |
| 3–4 | AI test impression generation (edge detection → morphological ops → pressure simulation) |
| 4–5 | Vector embeddings (ResNet/ViT, 512/2048-dim, stored via pgvector) |
| 5 | Nightly maintenance (dedup pass, duplicate reports, optional merge) |

**Build cost:** ~$15–30 for GPU training (SageMaker), or $0 with Google Colab

---

### Phase 5 — Crime Scene Search Pipeline (2–3 weeks)

| Week | Task |
|---|---|
| 1 | Upload endpoint → `gaitway/crime-scene/` in S3 |
| 1 | Preprocessing: grayscale, perspective correction, CLAHE, background suppression |
| 2 | CRF/segmentation (optional), multi-variant generation (3–5 variants per upload) |
| 2–3 | Embed variants with same CNN, cosine similarity search vs pgvector, ranked results |
| 3 | Forensic audit logging in `CrimeSceneQuery` |

**Build cost:** $0

---

### Phase 6 — FastAPI API Layer + Stripe (1–2 weeks)

| Task | Details |
|---|---|
| Auth middleware | JWT via Cognito, subscription status check |
| Core endpoints | CRUD shoes, search, crime-scene upload/search |
| Admin endpoints | Crawl trigger, crawl status, dedupe |
| Stripe Checkout | $1,200/year (`prod_TtcDNkZohuUdvB`) |
| Stripe webhooks | subscription.created/updated/deleted, invoice events |
| Billing Portal | Self-service cancel/update |
| Presigned URLs | All image access via time-limited S3 URLs |

**Build cost:** $0 (Stripe charges only on transactions: 2.9% + $0.30)

---

### Phase 7 — React Frontend (3–4 weeks)

| Week | Component |
|---|---|
| 1 | Setup + layout: React + TypeScript, forensic-lab theme, Cognito auth |
| 1 | Dashboard: shoe counts, impression counts, crawl status, recent queries |
| 2 | Search & Compare: filters, outsole AI impression grid, detail modal |
| 2–3 | Crime Scene Search: drag-and-drop upload, progress, ranked results |
| 3 | Upload Wizard: 4-step (metadata → upper → sole → review) |
| 4 | Subscription page: plan display, Stripe Checkout, billing portal link |
| 4 | Polish: cross-browser, responsive, accessibility |

**Build cost:** $0

---

### Phase 8 — Production Deployment (1–2 weeks)

| Task | Details |
|---|---|
| Dockerize | 3 separate containers (API, scraper, image processor) |
| ECS Fargate | Task definitions in `us-east-2` |
| IAM task roles | Least-privilege per service |
| ALB + Cognito | Auth at load balancer level |
| S3 + CloudFront | React SPA hosting |
| Secrets Manager | DB creds, Stripe keys, proxy keys |
| CloudWatch | Logging, alarms, storage monitoring |
| CloudTrail | Forensic audit trail |
| Route 53 | Custom domain |

**Build cost:** Domain ~$12–15/year

---

### Phase 9 — Scale Scrapers (Ongoing)

Add remaining retailers one at a time:
1. ShoeMall, ShoePalace, FootwearEtc (simpler)
2. Zalando, ASOS (European, EU proxy nodes)
3. JD (Playwright for JS rendering)
4. Taobao (hardest — may need data API provider instead)

---

## Cost Estimates

### Development Build Costs (Non-Labor)

| Category | Item | One-Time | Monthly During Dev |
|---|---|---|---|
| **AWS** | RDS db.t3.medium | — | $50 |
| | S3 storage (< 5GB free tier) | — | $0 |
| | ECS Fargate (testing) | — | $10–20 |
| | Secrets Manager | — | $2 |
| **External** | Residential proxies | — | $30–50 |
| | Domain registration | $12–15 | — |
| **ML** | SageMaker GPU (or Colab free) | $0–30 | — |

| | **Total** |
|---|---|
| One-time costs | **$12–45** |
| Monthly during dev (4–5 months) | **$90–125/month** |
| **Total development spend** | **$400–670** |

💡 Use `db.t3.micro` (free tier) during early dev to save ~$200 in first 2 months.

---

### Monthly Operational Costs (Production)

#### Tier 1: Launch (0–20 subscribers)

| Service | Spec | Monthly |
|---|---|---|
| RDS PostgreSQL | db.t3.medium, 50GB gp3 | $56 |
| ECS Fargate — API | 0.5 vCPU, 1GB, 24/7 | $18 |
| ECS Fargate — Scraper | 1 vCPU, 2GB, 4 hrs/day | $6 |
| ECS Fargate — Image Proc | 1 vCPU, 2GB, 2 hrs/day | $3 |
| S3 Storage | ~100GB | $5 |
| S3 Requests | PUT/GET/LIST | $5 |
| CloudFront | React SPA + light traffic | $5 |
| NAT Gateway | VPC private subnet | $37 |
| ALB | Application Load Balancer | $22 |
| Route 53 | Hosted zone + DNS | $1 |
| Secrets Manager | 5 secrets | $2 |
| CloudWatch | Logs + metrics | $8 |
| EventBridge | Daily cron | <$1 |
| Cognito | First 50K MAUs free | $0 |
| Residential Proxies | External service | $40 |
| Stripe fees | 2.9% + $0.30 per sub | ~$3/sub |
| **TOTAL** | | **~$210–250/month** |
| **Annual** | | **~$2,500–3,000/year** |

#### Tier 2: Growth (20–100 subscribers)

| Service | Spec | Monthly |
|---|---|---|
| RDS PostgreSQL | db.r6g.large, 100GB gp3 | $180 |
| ECS Fargate (all 3) | Scaled | $57 |
| S3 Storage | ~500GB | $15 |
| CloudFront | Moderate traffic | $15 |
| NAT Gateway + ALB | | $60 |
| Proxies | Expanded pool | $60 |
| CloudWatch | Enhanced | $15 |
| Misc | Secrets, Route 53, EventBridge | $5 |
| Stripe fees | ~50 subs avg | $145 |
| **TOTAL** | | **~$550–600/month** |
| **Annual** | | **~$6,600–7,200/year** |

#### Tier 3: Scale (100+ subscribers)

| Service | Spec | Monthly |
|---|---|---|
| RDS PostgreSQL | db.r6g.xlarge, 200GB gp3, read replica | $385 |
| ECS Fargate | Auto-scaling | $120 |
| S3 Storage | ~2TB | $50 |
| CloudFront | High traffic | $30 |
| SageMaker endpoint | GPU inference | $250 |
| NAT Gateway + ALB | | $65 |
| Proxies | Premium tier | $100 |
| CloudWatch + CloudTrail | Full monitoring | $25 |
| Misc | | $10 |
| Stripe fees | ~100 subs avg | $290 |
| **TOTAL** | | **~$1,325/month** |
| **Annual** | | **~$15,900/year** |

---

### Revenue vs Cost Break-Even

| Subscribers | Annual Revenue | Annual Ops Cost | Net Profit |
|---|---|---|---|
| **3** | $3,600 | ~$3,000 | **+$600** (break-even) |
| 10 | $12,000 | ~$3,000 | **+$9,000** |
| 50 | $60,000 | ~$7,200 | **+$52,800** |
| 100 | $120,000 | ~$15,900 | **+$104,100** |

**Break-even: ~3 paying subscribers.**

---

### Cost Reduction Opportunities

| Optimization | Savings |
|---|---|
| VPC endpoints instead of NAT Gateway | -$37/month |
| Fargate Savings Plans (1yr commit) | -20–30% on compute |
| RDS Reserved Instance (1yr) | -30–40% on database |
| EC2 Spot for scraper tasks | -50–70% on scraper compute |
| Lambda for image processor | -$3–9/month |
| Defer SageMaker — use CPU inference | -$250/month at scale |

With optimizations, Tier 1 can drop to **~$140–170/month**.

---

## Timeline Summary

| Phase | Duration | Cumulative |
|---|---|---|
| Phase 0: Infra fixes | 2–4 hours | Day 1 |
| Phase 0.5: PoC | 1–2 weeks | Week 2 |
| Phase 1: Backend foundation | 1–2 weeks | Week 4 |
| Phase 2: RDS + pgvector | 3–5 days | Week 5 |
| Phase 3: Scrapers (first 6) | 3–4 weeks | Week 9 |
| Phase 4: Image pipeline | 3–5 weeks | Week 14 |
| Phase 5: Crime scene search | 2–3 weeks | Week 17 |
| Phase 6: API + Stripe | 1–2 weeks | Week 19 |
| Phase 7: React frontend | 3–4 weeks | Week 23 |
| Phase 8: Production deploy | 1–2 weeks | Week 25 |
| Phase 9: Scale scrapers | Ongoing | Ongoing |

**Total to MVP: ~5–6 months** (solo developer, part-time adjusted)

---

## Key Technical Decisions

| Decision | Choice | Rationale |
|---|---|---|
| Region | `us-east-2` (Ohio) | Per project spec |
| S3 bucket | `gaitway-footwear-791209948637` | Dedicated, not shared CF bucket |
| Database | RDS PostgreSQL + pgvector | Vector similarity search native in DB |
| Auth | AWS Cognito | Managed auth, JWT, MFA, integrates with ALB |
| Frontend | React + TypeScript | Modern SPA, forensic-lab theme |
| Backend | FastAPI | Async, fast, type-safe, Python ecosystem |
| Billing | Stripe ($1,200/year) | Industry standard, webhooks, billing portal |
| Scraper anti-bot | Residential proxies + Playwright | Required for major retailers |
| Image embeddings | ResNet50/ViT → pgvector | Proven for visual similarity |
| Architecture | 3 separate services | API, scraper, processor — independent scaling |

---

## Risk Register

| Risk | Impact | Mitigation |
|---|---|---|
| Retailer anti-bot blocks scraping | High | Proxy rotation, rate limits, Playwright, fallback to API providers |
| Taobao scraping fails entirely | Medium | Descope or use third-party data provider |
| ML model accuracy insufficient | High | Start with pre-trained, iterate; collect labeled training data early |
| AWS costs exceed projections | Medium | Monitor CloudWatch billing alerts, use cost optimizations listed above |
| Context window limits during dev | Low | Session management rules in `.clinerules`, memory bank saves |
| Legal risk from scraping | Medium | Respect robots.txt, document compliance approach, consult legal |
