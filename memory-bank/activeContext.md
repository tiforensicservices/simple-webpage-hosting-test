# Active Context

## Current Focus
**Test suite is clean (99/99, no warnings).** Phase 1 is fully complete and committed.
Next step: **Start the API dev server** to verify Swagger UI, then proceed to
**Phase 2 — RDS PostgreSQL + pgvector**.

## What Was Just Done (2026-03-29 Session 7)

### Test Suite Hygiene — pytest.ini + conftest.py ✅

Problem: lxml's `HTMLParser` C extension emits a `DeprecationWarning` about `strip_cdata`
that cannot be suppressed via module-based pytest.ini filters (it originates in compiled
C code with no Python module name).

Fixes applied:
1. `pytest.ini` — created with `filterwarnings = ignore:The 'strip_cdata' option of HTMLParser:DeprecationWarning`
2. `tests/conftest.py` — added `warnings.filterwarnings(...)` call *before* any imports
   so the Python-level filter is registered before lxml is imported.

Result: **99 passed, 0 errors, 0 warnings in 0.51s** ✅

Committed: `0097fc9` — "tests: silence lxml third-party DeprecationWarning"

## What Was Done Previously (2026-03-28 / 2026-03-29)

### Phase 1 — Backend Foundation — All Files Written + Committed ✅

#### Alembic Migration Framework
- `alembic.ini`, `alembic/env.py`, `alembic/script.py.mako`
- `alembic/versions/20260328_0100_aaa111000001_initial_tables.py` — pgvector extension + 7 tables
- `alembic/versions/20260328_0200_bbb222000002_hnsw_index.py` — HNSW index (m=16, ef=64)

#### FastAPI API Layer
- `src/api/main.py` — 5 route blueprints, CORS, lifespan handler (no deprecation warnings)
- `src/api/routes/` — shoes, crime_scene, upload, admin, stripe_billing
- `src/api/middleware/` — 3-path auth (Cognito JWT → API key → dev mode)

#### CLI + Config
- `src/cli.py` — full Typer + Rich CLI
- `config/scrapers.yaml` — 9 sites (zappos enabled)

#### Tests
- `tests/conftest.py` — full shared fixture suite (env_vars, mock_s3, db_*, test_client, etc.)
- `tests/test_api.py` — 21 API tests ✅
- `tests/test_base_scraper.py` — 29 scraper tests ✅
- `tests/test_zappos_scraper.py` — 45 Zappos-specific tests ✅
- `tests/test_setup_s3.py` — 4 S3 config tests ✅

#### CI / Developer Tools
- `.github/workflows/tests.yml` — CI (py3.11 + 3.13, ruff, black, pytest + cov)
- `.github/workflows/security.yml` — Gitleaks + .gitignore checks
- `scripts/run_tests.py` — local test runner

## Next Steps

### Immediate (this session or next)
1. **Start API dev server:**
   ```
   uvicorn src.api.main:app --reload
   # Verify Swagger UI at http://localhost:8000/docs
   ```

2. **Phase 2 — RDS PostgreSQL provisioning:**
   - Set `DB_PASSWORD` in `.env` (strong password)
   - Run `python scripts/provision_rds.py --dry-run` to review
   - Run `python scripts/provision_rds.py` to provision db.t3.medium in us-east-2
   - Update `.env` with RDS endpoint
   - `python -m alembic upgrade head` against RDS
   - Verify HNSW index created

3. **Phase 2 — Integration tests against live PostgreSQL:**
   ```
   TEST_DATABASE_URL=postgresql+psycopg2://gaitway_admin:<pw>@<rds-endpoint>/gaitway_db pytest tests/ -v
   ```

## Environment State
- Python: 3.13 (host)
- All requirements: ✅ installed
- `.env`: ✅ (us-east-2, gaitway-footwear-791209948637, DB creds)
- AWS Account: `791209948637`
- S3 bucket: `gaitway-footwear-791209948637` (us-east-2) — ✅ LIVE
- PostgreSQL: local via Docker (`docker compose up -d`) on port 5432
- Git: on `develop` branch — all Phase 0 through Phase 1 committed
- Test suite: **99/99 passing, 0 warnings** ✅

## Current Blockers
- None. Everything committed and clean.
- Phase 2 requires AWS console/CLI access to provision RDS instance.
