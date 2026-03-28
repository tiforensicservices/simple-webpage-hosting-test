"""Initial tables — create all Gaitway core schema.

Creates the pgvector extension and all 7 ORM tables:
  users, workspaces, subscription_plans, user_subscriptions,
  shoes, shoe_images, crime_scene_queries.

Revision ID: aaa111000001
Revises: (none — first migration)
Create Date: 2026-03-28 01:00:00.000000
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from pgvector.sqlalchemy import Vector

# revision identifiers
revision: str = "aaa111000001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Create pgvector extension and all core tables."""

    # ── 0. Enable pgvector extension ────────────────────────────────────────
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")

    # ── 1. users ────────────────────────────────────────────────────────────
    op.create_table(
        "users",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("email", sa.String(255), nullable=False),
        sa.Column("cognito_sub", sa.String(128), nullable=True,
                  comment="AWS Cognito user pool subject (UUID)"),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )
    op.create_index("ix_users_email", "users", ["email"], unique=True)
    op.create_index("ix_users_cognito_sub", "users", ["cognito_sub"], unique=True)

    # ── 2. workspaces ────────────────────────────────────────────────────────
    op.create_table(
        "workspaces",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column(
            "user_id",
            sa.Integer(),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column(
            "subscription_status",
            sa.String(50),
            nullable=False,
            server_default="inactive",
            comment="inactive | active | past_due | canceled",
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )
    op.create_index("ix_workspaces_user_id", "workspaces", ["user_id"])

    # ── 3. subscription_plans ────────────────────────────────────────────────
    op.create_table(
        "subscription_plans",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column(
            "stripe_price_id",
            sa.String(100),
            nullable=False,
            comment="Stripe Price ID (e.g. price_xxx)",
        ),
        sa.Column("name", sa.String(100), nullable=False),
        sa.Column("price_usd", sa.Float(), nullable=False),
        sa.Column(
            "interval",
            sa.String(20),
            nullable=False,
            server_default="year",
            comment="month | year",
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )
    op.create_index(
        "ix_subscription_plans_stripe_price_id",
        "subscription_plans",
        ["stripe_price_id"],
        unique=True,
    )

    # ── 4. user_subscriptions ────────────────────────────────────────────────
    op.create_table(
        "user_subscriptions",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column(
            "user_id",
            sa.Integer(),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "plan_id",
            sa.Integer(),
            sa.ForeignKey("subscription_plans.id"),
            nullable=True,
        ),
        sa.Column(
            "stripe_subscription_id",
            sa.String(100),
            nullable=False,
            comment="Stripe Subscription ID (e.g. sub_xxx)",
        ),
        sa.Column(
            "status",
            sa.String(50),
            nullable=False,
            server_default="inactive",
            comment="active | past_due | canceled | trialing | incomplete",
        ),
        sa.Column(
            "current_period_end",
            sa.DateTime(timezone=True),
            nullable=True,
            comment="When the current billing period ends (UTC)",
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.UniqueConstraint("user_id", name="uq_user_subscriptions_user_id"),
        sa.UniqueConstraint(
            "stripe_subscription_id",
            name="uq_user_subscriptions_stripe_id",
        ),
    )

    # ── 5. shoes ─────────────────────────────────────────────────────────────
    op.create_table(
        "shoes",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column(
            "external_site",
            sa.String(50),
            nullable=False,
            comment="e.g. zappos | amazon | dsw",
        ),
        sa.Column(
            "external_id",
            sa.String(100),
            nullable=False,
            comment="Site-specific product identifier",
        ),
        sa.Column("brand", sa.String(100), nullable=False),
        sa.Column("model_name", sa.String(255), nullable=False),
        sa.Column("category", sa.String(100), nullable=True),
        sa.Column(
            "gender",
            sa.String(20),
            nullable=True,
            comment="mens | womens | kids | unisex",
        ),
        sa.Column("colorway", sa.String(255), nullable=True),
        sa.Column("price", sa.Float(), nullable=True),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("product_url", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.UniqueConstraint(
            "external_site",
            "external_id",
            name="uq_shoe_site_id",
        ),
    )
    op.create_index("ix_shoes_external_site", "shoes", ["external_site"])
    op.create_index("ix_shoes_external_id", "shoes", ["external_id"])
    op.create_index("ix_shoes_brand", "shoes", ["brand"])

    # ── 6. shoe_images ───────────────────────────────────────────────────────
    op.create_table(
        "shoe_images",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column(
            "shoe_id",
            sa.Integer(),
            sa.ForeignKey("shoes.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "image_type",
            sa.String(20),
            nullable=False,
            comment="upper | sole | unknown",
        ),
        sa.Column("s3_raw_key", sa.String(512), nullable=True),
        sa.Column("s3_processed_key", sa.String(512), nullable=True),
        sa.Column("s3_thumbnail_key", sa.String(512), nullable=True),
        sa.Column(
            "s3_impression_key",
            sa.String(512),
            nullable=True,
            comment="AI-generated synthetic test impression S3 key",
        ),
        sa.Column(
            "phash",
            sa.String(64),
            nullable=True,
            comment="Perceptual hash (pHash) for near-duplicate detection",
        ),
        sa.Column(
            "embedding",
            Vector(512),
            nullable=True,
            comment="ResNet/ViT embedding for cosine similarity search",
        ),
        sa.Column("width", sa.Integer(), nullable=True),
        sa.Column("height", sa.Integer(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )
    op.create_index("ix_shoe_images_shoe_id", "shoe_images", ["shoe_id"])
    op.create_index("ix_shoe_images_phash", "shoe_images", ["phash"])

    # ── 7. crime_scene_queries ───────────────────────────────────────────────
    op.create_table(
        "crime_scene_queries",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column(
            "workspace_id",
            sa.Integer(),
            sa.ForeignKey("workspaces.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "s3_key",
            sa.String(512),
            nullable=False,
            comment="S3 key of the uploaded crime scene image",
        ),
        sa.Column(
            "variants_json",
            sa.JSON(),
            nullable=True,
            comment="Embedding variants generated",
        ),
        sa.Column(
            "results_json",
            sa.JSON(),
            nullable=True,
            comment="Top-N candidate shoes with cosine similarity scores",
        ),
        sa.Column(
            "query_duration_ms",
            sa.Integer(),
            nullable=True,
            comment="End-to-end search duration in milliseconds",
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )
    op.create_index(
        "ix_crime_scene_queries_workspace_id",
        "crime_scene_queries",
        ["workspace_id"],
    )


def downgrade() -> None:
    """Drop all tables and the pgvector extension (reverse order of creation)."""
    op.drop_table("crime_scene_queries")
    op.drop_table("shoe_images")
    op.drop_table("shoes")
    op.drop_table("user_subscriptions")
    op.drop_table("subscription_plans")
    op.drop_table("workspaces")
    op.drop_table("users")
    op.execute("DROP EXTENSION IF EXISTS vector")
