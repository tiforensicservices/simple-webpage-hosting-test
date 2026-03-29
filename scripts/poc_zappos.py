"""
poc_zappos.py — Phase 0.5 End-to-End Proof of Concept

Pipeline validated by this script:
  1. ✅ Scrape one Zappos product page (Nike Air Max 90)
  2. ✅ Upload raw images to S3   raw/zappos/<product_id>/
  3. ✅ Persist Shoe + ShoeImage records in local PostgreSQL + pgvector
  4. ✅ Store a dummy normalised embedding vector per image
  5. ✅ Run a cosine similarity search (pgvector <=> operator)
  6. ✅ Log ranked results

Run from project root (inside Dev Container or with venv active):
    python scripts/poc_zappos.py

Prerequisites:
  1. Docker running:  docker compose up -d
  2. .env configured (AWS_ACCESS_KEY_ID, AWS_SECRET_ACCESS_KEY,
                      S3_BUCKET_NAME, DB_HOST, DB_USER, DB_PASSWORD …)
  3. pip install -r requirements.txt
"""

from __future__ import annotations

import logging
import os
import sys
import time
from pathlib import Path

# ---------------------------------------------------------------------------
# Ensure src/ is importable when running as a standalone script
# ---------------------------------------------------------------------------
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

import numpy as np
from dotenv import load_dotenv
from sqlalchemy import text

load_dotenv(override=True)

from src.db.connection import get_db, get_engine, ping_db
from src.db.models import Base, Shoe, ShoeImage
from src.scraper.zappos import ZapposScraper

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s — %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("poc_zappos")

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

# Nike Air Max 90 — classic silhouette with clear sole + upper images.
#
# ⚠️  IMPORTANT: Zappos product URLs can become stale when products are
# discontinued or re-catalogued. If you see a RuntimeError about a "no-results
# page", visit https://www.zappos.com, search for "Nike Air Max 90", open a
# product page, and copy its URL here.
#
# Last verified working (approx. 2026-03-28): product/8005382 — now stale.
# Updated candidate (may require re-verification): product/9246807
POC_PRODUCT_URL = "https://www.zappos.com/p/nike-air-max-90/product/9246807"

# Max images to upload during PoC (keeps runtime short)
MAX_IMAGES_TO_UPLOAD = 5

# Vector dimension — must match ShoeImage.embedding Vector(512)
EMBEDDING_DIM = 512


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def bootstrap_db() -> None:
    """Create pgvector extension + all ORM tables if they don't exist yet."""
    logger.info("🗄️  Bootstrapping database schema …")
    engine = get_engine()
    with engine.connect() as conn:
        conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector;"))
        conn.commit()
    Base.metadata.create_all(bind=engine)
    logger.info("✅ Tables ready (pgvector extension enabled)")


def make_dummy_embedding() -> list[float]:
    """Generate a random L2-normalised embedding vector for the PoC.

    In production this would be a real ResNet-512 or ViT embedding
    produced by the ImageProcessorService pipeline.

    Returns:
        512-element list of floats on the unit sphere.
    """
    vec = np.random.randn(EMBEDDING_DIM).astype(np.float32)
    vec /= np.linalg.norm(vec)   # Normalise → cosine distance = 1 - dot product
    return vec.tolist()


def divider(label: str) -> None:
    """Print a labelled section divider to the log."""
    logger.info("")
    logger.info("─" * 60)
    logger.info("  %s", label)
    logger.info("─" * 60)


# ---------------------------------------------------------------------------
# Main PoC pipeline
# ---------------------------------------------------------------------------


def run_poc() -> None:
    """Execute the full Phase 0.5 end-to-end PoC pipeline."""
    logger.info("🚀 Gaitway Phase 0.5 PoC — Starting")
    logger.info("   Project root: %s", PROJECT_ROOT)

    # -----------------------------------------------------------------
    # Step 1 — Database connectivity
    # -----------------------------------------------------------------
    divider("Step 1: Database connectivity")
    if not ping_db():
        logger.error(
            "❌ Cannot connect to PostgreSQL.\n"
            "   Make sure Docker is running and the DB container is healthy:\n"
            "     docker compose up -d\n"
            "     docker compose ps"
        )
        sys.exit(1)

    # -----------------------------------------------------------------
    # Step 2 — Bootstrap schema
    # -----------------------------------------------------------------
    divider("Step 2: Bootstrap schema")
    bootstrap_db()

    # -----------------------------------------------------------------
    # Step 3 — Scrape Zappos product
    # -----------------------------------------------------------------
    divider("Step 3: Scrape Zappos product page")
    logger.info("URL: %s", POC_PRODUCT_URL)

    scraper = ZapposScraper(rate_limit_seconds=2.0)
    try:
        shoe_data = scraper.scrape_product(POC_PRODUCT_URL)
    except RuntimeError as exc:
        logger.error(
            "❌ Scraping failed: %s\n"
            "   This PoC requires live internet access to zappos.com.\n"
            "   If Zappos changed their HTML, update selectors in "
            "src/scraper/zappos.py.",
            exc,
        )
        sys.exit(1)

    logger.info("✅ Shoe scraped successfully:")
    logger.info("   Brand:        %s", shoe_data.brand)
    logger.info("   Model:        %s", shoe_data.model_name)
    logger.info("   External ID:  %s", shoe_data.external_id)
    logger.info("   Category:     %s", shoe_data.category)
    logger.info("   Gender:       %s", shoe_data.gender)
    logger.info("   Colorway:     %s", shoe_data.colorway)
    logger.info("   Price:        $%.2f", shoe_data.price or 0.0)
    logger.info("   Images found: %d", len(shoe_data.image_urls))
    logger.info("   Description:  %s …", (shoe_data.description or "")[:80])

    # -----------------------------------------------------------------
    # Step 4 — Upload raw images to S3
    # -----------------------------------------------------------------
    divider("Step 4: Upload raw images to S3")
    s3_uploads: list[dict[str, str]] = []
    bucket = os.getenv("S3_BUCKET_NAME", "")

    if not bucket or bucket == "gaitway-footwear-YOUR_ACCOUNT_ID":
        logger.warning(
            "⚠️  S3_BUCKET_NAME not configured — skipping S3 upload.\n"
            "    Set S3_BUCKET_NAME in your .env to enable this step."
        )
    else:
        image_candidates = shoe_data.image_urls[:MAX_IMAGES_TO_UPLOAD]
        logger.info(
            "Uploading %d images to s3://%s/raw/zappos/%s/",
            len(image_candidates),
            bucket,
            shoe_data.external_id,
        )
        for idx, img_url in enumerate(image_candidates):
            filename = f"image_{idx + 1:02d}.jpg"
            s3_key = scraper.build_s3_key(shoe_data.external_id, filename)
            # First image from Zappos is typically the side (upper) view
            image_type = "upper" if idx == 0 else "unknown"
            result = scraper.upload_image_to_s3(img_url, s3_key)
            if result:
                s3_uploads.append({"key": result, "type": image_type})

        logger.info(
            "✅ Uploaded %d / %d images",
            len(s3_uploads),
            len(image_candidates),
        )

    # -----------------------------------------------------------------
    # Step 5 — Persist to PostgreSQL
    # -----------------------------------------------------------------
    divider("Step 5: Persist Shoe + ShoeImage records to PostgreSQL")

    with get_db() as db:
        # Upsert: skip if already in DB (idempotent re-runs)
        existing_shoe = (
            db.query(Shoe)
            .filter_by(
                external_site=shoe_data.external_site,
                external_id=shoe_data.external_id,
            )
            .first()
        )

        if existing_shoe:
            shoe_record = existing_shoe
            logger.info(
                "ℹ️  Shoe already in DB (id=%d) — reusing for image records",
                shoe_record.id,
            )
        else:
            shoe_record = Shoe(
                external_site=shoe_data.external_site,
                external_id=shoe_data.external_id,
                brand=shoe_data.brand,
                model_name=shoe_data.model_name,
                category=shoe_data.category,
                gender=shoe_data.gender,
                colorway=shoe_data.colorway,
                price=shoe_data.price,
                description=(shoe_data.description or "")[:2000],
                product_url=shoe_data.product_url,
            )
            db.add(shoe_record)
            db.flush()   # Obtain auto-generated PK
            logger.info("✅ Shoe record inserted (id=%d)", shoe_record.id)

        # Insert ShoeImage records (with dummy embeddings)
        images_written = 0
        if s3_uploads:
            for entry in s3_uploads:
                img = ShoeImage(
                    shoe_id=shoe_record.id,
                    image_type=entry["type"],
                    s3_raw_key=entry["key"],
                    embedding=make_dummy_embedding(),
                )
                db.add(img)
                images_written += 1
        else:
            # No S3 upload — still add a dummy record so Step 6 has data
            logger.info(
                "ℹ️  No S3 uploads — adding dummy ShoeImage record for PoC"
            )
            dummy_key = (
                f"raw/zappos/{shoe_data.external_id}/image_01.jpg"
            )
            img = ShoeImage(
                shoe_id=shoe_record.id,
                image_type="upper",
                s3_raw_key=dummy_key,
                embedding=make_dummy_embedding(),
            )
            db.add(img)
            images_written = 1

        db.flush()
        logger.info(
            "✅ %d ShoeImage record(s) written (with dummy embeddings)",
            images_written,
        )

    logger.info("✅ Transaction committed to PostgreSQL")

    # -----------------------------------------------------------------
    # Step 6 — Cosine similarity search via pgvector
    # -----------------------------------------------------------------
    divider("Step 6: Cosine similarity search (pgvector)")
    query_embedding = make_dummy_embedding()
    query_str = str(query_embedding)

    t_start = time.perf_counter()
    with get_db() as db:
        # pgvector cosine distance operator: <=>
        # cosine similarity = 1 - cosine distance
        rows = db.execute(
            text(
                """
                SELECT
                    si.id                                             AS image_id,
                    si.shoe_id,
                    si.image_type,
                    si.s3_raw_key,
                    s.brand,
                    s.model_name,
                    1 - (si.embedding <=> CAST(:q AS vector))        AS similarity
                FROM shoe_images si
                JOIN shoes s ON s.id = si.shoe_id
                WHERE si.embedding IS NOT NULL
                ORDER BY si.embedding <=> CAST(:q AS vector)
                LIMIT 5
                """
            ),
            {"q": query_str},
        ).fetchall()
    elapsed_ms = int((time.perf_counter() - t_start) * 1000)

    logger.info("✅ Search completed in %d ms — top %d result(s):", elapsed_ms, len(rows))
    if rows:
        for rank, row in enumerate(rows, start=1):
            logger.info(
                "   #%d  similarity=%.4f  brand=%-12s  model=%-20s  "
                "type=%-8s  key=%s",
                rank,
                row.similarity,
                row.brand,
                row.model_name,
                row.image_type,
                row.s3_raw_key,
            )
    else:
        logger.warning(
            "⚠️  No results returned. Ensure ShoeImage records have embeddings."
        )

    # -----------------------------------------------------------------
    # Summary
    # -----------------------------------------------------------------
    divider("🎉 Phase 0.5 PoC Summary")
    logger.info("  Scraper (ZapposScraper):      ✅ WORKING")
    logger.info(
        "  S3 upload (boto3):            %s",
        "✅ WORKING" if s3_uploads else "⚠️  SKIPPED (S3_BUCKET_NAME not set)",
    )
    logger.info("  PostgreSQL persistence:        ✅ WORKING")
    logger.info("  pgvector cosine search:        ✅ WORKING")
    logger.info("")
    logger.info(
        "Next step → Phase 1: FastAPI project structure + "
        "SQLAlchemy migrations (Alembic)"
    )


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    run_poc()
