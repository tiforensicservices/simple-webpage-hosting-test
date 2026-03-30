# Active Context

## Current Focus
**Phase 2 — RDS PostgreSQL is LIVE.** `gaitway-db-prod` is fully provisioned and migrated
in `us-east-2`. Test suite remains 99/99 clean.
Next step: **Phase 3 — Scraper Framework + First Retailers**
(anti-bot infra, pHash dedup, EventBridge scheduler, 6 additional scrapers).

## What Was Just Done (2026-03-30 Session 8)

### Phase 2 — RDS PostgreSQL 16.6 + pgvector — COMPLETE ✅

| Step | Result |
|---|---|
| IAM policy `GaitwayPhaseProv` created for `shoeprint-dev` | ✅ |
| IAM inline policy updated with `iam:CreateServiceLinkedRole` (`Resource: *`) | ✅ |
| `provision_rds.py` fixed (ASCII SG description, ENGINE_VERSION 16.3→16.6) | ✅ |
| `gaitway-db-prod` provisioned — `db.t3.medium`, 100 GB gp3, us-east-2 | ✅ |
| Endpoint: `gaitway-db-prod.cjwqeu04o87z.us-east-2.rds.amazonaws.com` | ✅ |
| Security group `gaitway-rds-sg` (`sg-0610eef0774d4f9ee`) created | ✅ |
| `.env` updated — `DB_HOST`, `DB_NAME=gaitway_db`, `DB_USER=gaitway_admin` | ✅ |
| `alembic upgrade head` — both migrations applied to live RDS | ✅ |
| Alembic current: `bbb222000002 (head)` | ✅ |
| HNSW index `ix_shoe_images_embedding_hnsw` confirmed on RDS | ✅ |
| Credentials stored in Secrets Manager: `gaitway/rds/master` | ✅ |
| Test suite: **99/99 passed, 0 warnings** | ✅ |

### RDS Connection Details
```
Host:     gaitway-db-prod.cjwqeu04o87z.us-east-2.rds.amazonaws.com
Port:     5432
DB name:  gaitway_db
User:     gaitway_admin
Password: (see .env / Secrets Manager: gaitway/rds/master)
SG:       sg-0610eef0774d4f9ee  (gaitway-rds-sg)
```

### IAM Policy — GaitwayPhaseProv (final version)
- `EC2SecurityGroup` — describe/create/authorize SGs
- `RDSProvisioning` — create/describe/modify DB instances
- `RDSServiceLinkedRole` — `iam:CreateServiceLinkedRole` with `Resource: *`
- `SecretsManager` — create/update/get/describe `gaitway/*` secrets

## What Was Done Previously (2026-03-29 Session 7)

### Test Suite Hygiene — pytest.ini + conftest.py ✅
- `pytest.ini` created with `filterwarnings` to suppress lxml C DeprecationWarning
- Result: **99 passed, 0 errors, 0 warnings in 0.51s** ✅
- Committed: `0097fc9` — "tests: silence lxml third-party DeprecationWarning"

## Next Steps

### Immediate (next session)
1. **Tighten RDS security group** (Phase 8 pre-req):
   - Currently `0.0.0.0/0` on port 5432 (dev-only)
   - Before go-live: restrict to ECS task SG, set `PubliclyAccessible=False`

2. **Phase 3 — Scraper Framework:**
   - Anti-bot infrastructure (session rotation, proxy pool, User-Agent rotation)
   - pHash deduplication logic (`imagehash` library)
   - 6 additional site-specific scrapers (DSW, Foot Locker, Amazon, Nike, Adidas, New Balance)
   - EventBridge daily scheduler (1:00 AM CST)

3. **Integration tests against live RDS:**
   ```
   TEST_DATABASE_URL=postgresql+psycopg2://gaitway_admin:<pw>@gaitway-db-prod.cjwqeu04o87z.us-east-2.rds.amazonaws.com/gaitway_db pytest tests/ -v
   ```

## Environment State
- Python: 3.13 (host)
- All requirements: ✅ installed
- `.env`: ✅ pointing to RDS (us-east-2)
- AWS Account: `791209948637`
- S3 bucket: `gaitway-footwear-791209948637` (us-east-2) — ✅ LIVE
- RDS: `gaitway-db-prod.cjwqeu04o87z.us-east-2.rds.amazonaws.com` — ✅ LIVE, at `head`
- Git: on `develop` branch — Phase 0 through Phase 1 committed; Phase 2 pending commit
- Test suite: **99/99 passing, 0 warnings** ✅

## Current Blockers
- None. RDS is live, migrations applied, tests green.
- SG tightening (0.0.0.0/0 → ECS SG) deferred to Phase 8 go-live.
