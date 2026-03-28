# Active Context

## Current Focus
**Phase 1 complete.** All Phase 1 — Backend Foundation files have been written.
Next session should run the Phase 0.5 PoC (`docker compose up -d && python scripts/poc_zappos.py`)
to verify the end-to-end pipeline, then move to **Phase 2 — RDS PostgreSQL + pgvector**.

## What Was Just Done (2026-03-28 Session 6)

### Phase 1 — Backend Foundation — All Files Written ✅

#### Alembic Migration Framework
- `alembic.ini` — Alembic config (prepend_sys_path=., UTC, slug file names)
- `alembic/env.py` — configured to import Base from src.db.models, uses get_database_url()
- `alembic/script.py.mako` — migration file template
- `alembic/versions/20260328_0100_aaa111000001_initial_tables.py` — creates pgvector extension
  + all 7 tables (users, workspaces, subscription_plans, user_subscriptions,
  shoes, shoe_images, crime_scene_queries) with all indexes
- `alembic/versions/20260328_0200_bbb222000002_hnsw_index.py` — creates HNSW index on
  shoe_images.embedding (vector_cosine_ops, m=16, ef_construction=64)

#### FastAPI API Layer
- `src/api/main.py` — updated: registers all 5 route blueprints, adds CORS middleware,
  adds /api/v1/billing/plans to root navigation
- `src/api/routes/__init__.py` — exports all 5 routers
- `src/api/routes/shoes.py` — 5 endpoints: GET /shoes, GET /shoes/{id},
  GET /shoes/{id}/images, POST /shoes, DELETE /shoes/{id}
- `src/api/routes/crime_scene.py` — 3 endpoints: POST /crime-scene/search,
  GET /crime-scene/queries, GET /crime-scene/queries/{id}
- `src/api/routes/upload.py` — 3 endpoints: POST /upload/presign-shoe,
  POST /upload/presign-crime-scene, POST /upload/shoe-image
  (presign endpoints fully wired to boto3 — functional with real AWS)
- `src/api/routes/admin.py` — 5 endpoints: GET /admin/stats (live DB ping),
  GET /admin/users, GET /admin/db-status (live Alembic check),
  POST /admin/scraper/trigger, GET /admin/scraper/sites (reads scrapers.yaml)
- `src/api/routes/stripe_billing.py` — 4 endpoints: GET /billing/plans,
  POST /billing/checkout (wired to Stripe SDK), POST /billing/portal,
  POST /billing/webhook (signature validation + 4 event handlers)

#### Authentication Middleware
- `src/api/middleware/__init__.py` — exports get_current_user, RequireAuth
- `src/api/middleware/auth.py` — 3-path auth resolver:
  Path 1: Cognito JWT (Phase 6 — stub)
  Path 2: X-API-Key header check (Phase 1 — functional)
  Path 3: Dev mode fallback (no auth configured)
  `RequireAuth(strict=True)` raises 401 in dev mode

#### CLI (Typer + Rich)
- `src/cli.py` — full CLI with sub-commands:
  `gaitway db init` — alembic upgrade head (with confirmation)
  `gaitway db status` — show current/head revision in Rich table
  `gaitway db downgrade [rev]` — roll back with confirmation
  `gaitway scraper crawl <site>` — run ZapposScraper synchronously
  `gaitway scraper crawl-all` — crawl all enabled sites from scrapers.yaml
  `gaitway scraper list-sites` — Rich table of all configured sites
  `gaitway crime-search <image>` — Phase 5 stub
  `gaitway check-health` — verify config, DB, S3 in sequence
  `gaitway setup-s3` — delegates to src.aws.setup_s3

#### Config
- `config/scrapers.yaml` — 9 retailer sites: zappos (enabled), amazon/dsw/foot_locker/
  nike/adidas/finish_line/new_balance/skechers (all disabled for Phase 9)
  Global defaults: timeout=30s, retry=3, robots.txt=true, UA pool (4 agents)

#### Tests
- `tests/conftest.py` — shared pytest fixtures:
  `env_vars` (session) — safe test credentials, test bucket name
  `mock_s3` — moto-mocked S3, creates gaitway-footwear-test bucket
  `db_engine` (session) — SQLite in-memory (or TEST_DATABASE_URL for PG)
  `db_tables` (session) — creates schema (patches Vector→Text for SQLite)
  `test_db` — per-test session with SAVEPOINT rollback isolation
  `test_client` — FastAPI TestClient with mock_s3 active
  `authed_client` — TestClient with X-API-Key header preset
  `sample_shoe`, `sample_shoe_image`, `sample_user`, `sample_workspace`

### Previously Created (same session, interrupted)
- `src/config.py` — centralized Config dataclass, get_config()
- `src/__init__.py` — package init
- `src/api/__init__.py` — API package init
- `tests/__init__.py` — tests package init
- `.github/workflows/tests.yml` — CI pipeline (py3.11 + 3.13, ruff, black, pytest)
- `.github/workflows/security.yml` — Gitleaks + .gitignore checks
- `scripts/run_tests.py` — local test runner (--cov, --fast, --api flags)

## Key Decisions Made This Session
- Alembic migration IDs: `aaa111000001` (initial), `bbb222000002` (HNSW index)
- HNSW index params: m=16, ef_construction=64 (good recall/speed balance)
- Auth: 3-path resolver (Cognito > API key > dev mode) — zero-friction local dev
- conftest.py DB: SQLite in-memory default, pgvector.Vector patched to Text for SQLite
- presign upload endpoints: fully functional with real boto3 (live S3 calls)
- Admin /db-status: wired to live Alembic + SQLAlchemy (functional endpoint)
- Admin /scraper/sites: reads config/scrapers.yaml dynamically

## Next Steps (Phase 2 — RDS PostgreSQL + pgvector)
1. **Run PoC first** (still pending from Phase 0.5):
   ```
   docker compose up -d
   python scripts/poc_zappos.py
   ```
   Fix any selector issues in src/scraper/zappos.py if Zappos HTML changed.

2. **Phase 2 — RDS PostgreSQL provisioning:**
   - Create RDS PostgreSQL 16 instance in us-east-2 (Multi-AZ for prod)
   - Create security group: allow port 5432 from ECS task SGs
   - Run Alembic migrations against RDS: `alembic upgrade head`
   - Verify HNSW index created on shoe_images.embedding
   - Update .env with RDS endpoint + credentials (via Secrets Manager in prod)

3. **Phase 2 — Integration tests against live PostgreSQL:**
   ```
   TEST_DATABASE_URL=postgresql+psycopg2://... pytest tests/ -v
   ```

4. **Phase 2 — Verify API layer starts cleanly:**
   ```
   uvicorn src.api.main:app --reload
   # Visit http://localhost:8000/docs
   ```

## Environment State
- Python: 3.13 (Dev Container) / host Python also available
- boto3 + python-dotenv: ✅ (Dev Container + host)
- `.env`: ✅ (us-east-2, gaitway-footwear-791209948637, DB creds)
- AWS Account: `791209948637`
- S3 bucket: `gaitway-footwear-791209948637` (us-east-2) — ✅ LIVE
- PostgreSQL: local via Docker (`docker compose up -d`) on port 5432
- Git: on `develop` branch — Phase 0 + Phase 0.5 + Phase 1 to be committed

## Current Blockers
- None. Phase 1 is complete.
- PoC still needs to be run (needed before Phase 2 RDS provisioning).
- Phase 2 requires AWS console access to provision RDS instance.
