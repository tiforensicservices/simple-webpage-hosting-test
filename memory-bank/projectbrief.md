# Project Brief — Gaitway Footwear Intelligence Database

## Project Name
Gaitway Footwear Intelligence Database (repo: `simple-webpage-hosting-test`)

## Overview
A cloud-hosted forensic footwear platform that automatically collects shoe data from
retail sites and supports crime-scene footwear impression searches. It builds a
centralized, searchable database of footwear (uppers and soles), generates standardized
AI test impressions from outsole images, and compares them with crime-scene footwear
impressions to suggest likely shoe models.

## Business Model
- **Product:** Gaitway Footwear Intelligence Database
- **Stripe Product ID:** `prod_TtcDNkZohuUdvB`
- **Stripe Account:** TI Forensic Services (`acct_1SvoCyFABZBsDngL`)
- **Price:** $1,200 USD/year (annual, auto-renew)
- **API Version:** `2026-01-28.clover`

## Core Purpose
1. Build a centralized, searchable database of footwear (uppers and soles) collected
   from retail sites and user uploads
2. Generate standardized AI test impressions from outsole images and compare them with
   crime-scene footwear impressions to suggest likely shoe models
3. Offer access through a web application with user-specific workspaces and paid subscriptions

## Data Collection
- Crawl a fixed list of footwear retailers every day at **1:00 AM CST** (America/Chicago)
- **Target sites (14+):** Amazon (.com + international domains), Zappos, DSW, Footlocker,
  FinishLine, ShoeCarnival, ShoeMall, ShoePalace, FootwearEtc, Zalando, ASOS, Taobao, JD
- Site-specific scraper classes (e.g., `AmazonScraper`, `ZapposScraper`)
- Respect robots.txt and rate limits
- Log counts of new/updated/duplicate shoes and errors per site
- Extract: brand, model, category, gender, colorway, price, sizes, description, URLs, images

## Database Design
- **Engine:** Amazon RDS for PostgreSQL with SQLAlchemy + pgvector
- **Key entities:**
  - `User` / `Workspace` — multi-tenant user management
  - `Shoe` — metadata, `external_site`, `external_id` (e.g., ASIN)
  - `ShoeImage` — image type (upper/sole), S3 keys, dimensions, file size, pHash, embedding
  - `CrimeSceneQuery` — parameters, variants, results (forensic audit trail)
  - `SubscriptionPlan` / `UserSubscription` — Stripe billing integration
- **Product dedup:** Primary `(external_site, external_id)`, secondary cross-site heuristic
  on normalized `(brand, model_name, colorway)`
- **Image dedup:** pHash comparison + optional embedding similarity; nightly maintenance pass

## Image Pipeline
- All images stored in S3 bucket `gaitway-footwear-791209948637` (region `us-east-2`)
  under folders: `raw/`, `processed/`, `impressions/`, `thumbnails/`, `crime-scene/`, `user-shoes/`
- Access via presigned URLs only (never public)
- Each image classified as **upper** or **sole** (CNN/ViT classifier, pluggable model)
- For each sole image:
  - OpenCV preprocessing (grayscale, contrast, denoising, orientation normalization)
  - Generate synthetic AI test impression (high-contrast 2D scene print)
  - Compute vector embedding (ResNet/ViT), stored via pgvector

## Crime Scene Search
- Users upload crime-scene footwear impression images
- Pipeline: grayscale → perspective correction → contrast enhancement → background
  suppression → CRF segmentation → multi-variant generation
- Embed each variant with same CNN as AI impressions
- Cosine similarity search against pgvector index → ranked candidates with scores
- Every query logged in `CrimeSceneQuery` for forensic transparency

## AWS Architecture
- **Account:** TI Forensic Services, AWS Account ID `791209948637`
- **Region:** `us-east-2` (Ohio)
- **Backend:** FastAPI on ECS Fargate (3 separate services: API, scraper, image processor)
- **Frontend:** React SPA on S3 + CloudFront
- **Database:** RDS PostgreSQL + pgvector
- **Storage:** S3 with presigned URL access
- **Scheduling:** EventBridge → daily crawl at 1:00 AM CST
- **Auth:** AWS Cognito (JWT, MFA)
- **Secrets:** AWS Secrets Manager (production)
- **Monitoring:** CloudWatch + CloudTrail (forensic audit)

## Stripe Integration
- Stripe Checkout for sign-up (yearly price)
- Stripe Billing Portal for self-service
- Webhook handling: `customer.subscription.created/updated/deleted`,
  `invoice.payment_succeeded/failed`
- Access control middleware: active subscription required for full access; demo mode limited
- Env vars: `STRIPE_SECRET_KEY`, `STRIPE_PUBLISHABLE_KEY`, `STRIPE_PRICE_ID_YEARLY`,
  `STRIPE_WEBHOOK_SECRET`

## Application Features (UI)
- **Dashboard:** shoe counts, impression counts, crawl status per site, recent queries
- **Search & Compare:** filters (brand, category, gender, price), outsole AI impression
  grid, detail view (upper + sole + AI impression + metadata)
- **Crime Scene Search:** drag-and-drop upload, progress indicators, ranked candidates
- **Upload Wizard:** 4-step (metadata → upper images → sole/impression → review & save)
- **Subscription Page:** $1,200/year plan, Stripe Checkout, status, billing portal link
- **Theme:** forensic-lab aesthetic with subtle outsole/crime-scene imagery, high-contrast

## CLI Commands
- `init-db` — Initialize database schema
- `crawl-all` — Run all scrapers
- `crawl-site <name>` — Run specific scraper
- `dedupe-images` — Run dedup maintenance pass
- `reindex` — Rebuild vector index
- `crime-scene-search <image>` — CLI-based search

## Configuration
- YAML/JSON config for target domains, scraper settings, rate limits
- Thresholds for dedupe (pHash distance, similarity cutoffs)
- Extensive logging and versioning of ML models for forensic auditability

## Key Stakeholders
- Developer / Owner: kigow (tiforensicservices)

## Status
🟡 Phase 0 — Infrastructure Setup

## Created
2026-03-01

## Last Updated
2026-03-01
