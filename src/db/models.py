"""
models.py — SQLAlchemy ORM models for Gaitway Footwear Intelligence Database.

Entities
--------
  User               — Gaitway subscriber (law enforcement / forensic professional)
  Workspace          — Isolated investigation workspace per user
  Shoe               — A retailer shoe product record
  ShoeImage          — One image of a shoe, with pgvector embedding for search
  CrimeSceneQuery    — Forensic audit log of every crime scene search
  SubscriptionPlan   — Stripe product/price configuration
  UserSubscription   — A user's active Stripe subscription

Prerequisites
-------------
  The PostgreSQL database must have the pgvector extension enabled::

      CREATE EXTENSION IF NOT EXISTS vector;

  This is handled automatically by the PoC bootstrap and by Alembic migrations.
"""

from __future__ import annotations

from typing import Optional

from pgvector.sqlalchemy import Vector
from sqlalchemy import (
    BigInteger,
    Boolean,
    Column,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    JSON,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import DeclarativeBase, relationship


# ---------------------------------------------------------------------------
# Base class — all models inherit shared timestamps
# ---------------------------------------------------------------------------


class Base(DeclarativeBase):
    """Shared declarative base with automatic created_at / updated_at columns."""

    created_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
    updated_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )


# ---------------------------------------------------------------------------
# User
# ---------------------------------------------------------------------------


class User(Base):
    """A Gaitway subscriber (law enforcement officer or forensic analyst)."""

    __tablename__ = "users"

    id = Column(Integer, primary_key=True, autoincrement=True)
    email = Column(String(255), unique=True, nullable=False, index=True)
    cognito_sub = Column(
        String(128), unique=True, nullable=True, index=True,
        comment="AWS Cognito user pool subject (UUID)",
    )
    is_active = Column(Boolean, default=True, nullable=False)

    # Relationships
    workspaces = relationship(
        "Workspace", back_populates="user", cascade="all, delete-orphan"
    )
    subscription = relationship(
        "UserSubscription", back_populates="user", uselist=False
    )

    def __repr__(self) -> str:
        return f"<User id={self.id} email={self.email!r}>"


# ---------------------------------------------------------------------------
# Workspace
# ---------------------------------------------------------------------------


class Workspace(Base):
    """An isolated investigation workspace belonging to a User.

    Each workspace has its own crime scene query history and
    subscription status check.
    """

    __tablename__ = "workspaces"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(
        Integer,
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    name = Column(String(255), nullable=False)
    subscription_status = Column(
        String(50),
        default="inactive",
        nullable=False,
        comment="inactive | active | past_due | canceled",
    )

    # Relationships
    user = relationship("User", back_populates="workspaces")
    crime_scene_queries = relationship(
        "CrimeSceneQuery",
        back_populates="workspace",
        cascade="all, delete-orphan",
    )

    def __repr__(self) -> str:
        return f"<Workspace id={self.id} name={self.name!r}>"


# ---------------------------------------------------------------------------
# Shoe
# ---------------------------------------------------------------------------


class Shoe(Base):
    """A shoe product scraped from a retailer site.

    ``external_site`` + ``external_id`` form a unique pair identifying
    the product's origin, used for deduplication on re-scrape.
    """

    __tablename__ = "shoes"
    __table_args__ = (
        UniqueConstraint(
            "external_site", "external_id", name="uq_shoe_site_id"
        ),
    )

    id = Column(Integer, primary_key=True, autoincrement=True)
    external_site = Column(
        String(50), nullable=False, index=True,
        comment="e.g. zappos | amazon | dsw",
    )
    external_id = Column(
        String(100), nullable=False, index=True,
        comment="Site-specific product identifier",
    )
    brand = Column(String(100), nullable=False, index=True)
    model_name = Column(String(255), nullable=False)
    category = Column(String(100), nullable=True)
    gender = Column(
        String(20), nullable=True,
        comment="mens | womens | kids | unisex",
    )
    colorway = Column(String(255), nullable=True)
    price = Column(Float, nullable=True)
    description = Column(Text, nullable=True)
    product_url = Column(Text, nullable=True)

    # Relationships
    images = relationship(
        "ShoeImage", back_populates="shoe", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        return f"<Shoe id={self.id} brand={self.brand!r} model={self.model_name!r}>"


# ---------------------------------------------------------------------------
# ShoeImage
# ---------------------------------------------------------------------------


class ShoeImage(Base):
    """One image associated with a Shoe record.

    The ``embedding`` column is a pgvector Vector(512) used for cosine
    similarity search during crime scene matching.

    Image type classification:
      - "upper"   — side/top view of the shoe upper
      - "sole"    — bottom/outsole view (primary search target)
      - "unknown" — not yet classified
    """

    __tablename__ = "shoe_images"
    __table_args__ = (
        Index("ix_shoe_images_phash", "phash"),
    )

    id = Column(Integer, primary_key=True, autoincrement=True)
    shoe_id = Column(
        Integer,
        ForeignKey("shoes.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    image_type = Column(
        String(20), nullable=False,
        comment="upper | sole | unknown",
    )

    # S3 keys for each processed variant
    s3_raw_key = Column(String(512), nullable=True)
    s3_processed_key = Column(String(512), nullable=True)
    s3_thumbnail_key = Column(String(512), nullable=True)
    s3_impression_key = Column(
        String(512), nullable=True,
        comment="AI-generated synthetic test impression S3 key",
    )

    # Deduplication + search
    phash = Column(
        String(64), nullable=True,
        comment="Perceptual hash (pHash) for near-duplicate detection",
    )
    # Vector(512) — must match embedding model output dimension
    # HNSW index created by Alembic migration (not inline here)
    embedding = Column(
        Vector(512), nullable=True,
        comment="ResNet/ViT embedding for cosine similarity search",
    )

    # Image dimensions
    width = Column(Integer, nullable=True)
    height = Column(Integer, nullable=True)

    # Relationships
    shoe = relationship("Shoe", back_populates="images")

    def __repr__(self) -> str:
        return (
            f"<ShoeImage id={self.id} shoe_id={self.shoe_id} "
            f"type={self.image_type!r}>"
        )


# ---------------------------------------------------------------------------
# CrimeSceneQuery
# ---------------------------------------------------------------------------


class CrimeSceneQuery(Base):
    """Forensic audit log entry for every crime scene footwear search.

    Every search is logged here for forensic transparency and
    reproducibility. This record must never be deleted.
    """

    __tablename__ = "crime_scene_queries"

    id = Column(Integer, primary_key=True, autoincrement=True)
    workspace_id = Column(
        Integer,
        ForeignKey("workspaces.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    s3_key = Column(
        String(512), nullable=False,
        comment="S3 key of the uploaded crime scene image",
    )
    variants_json = Column(
        JSON, nullable=True,
        comment="Embedding variants generated (pre-processing steps applied)",
    )
    results_json = Column(
        JSON, nullable=True,
        comment="Top-N candidate shoes with cosine similarity scores",
    )
    query_duration_ms = Column(
        Integer, nullable=True,
        comment="End-to-end search duration in milliseconds (for audit)",
    )

    # Relationships
    workspace = relationship("Workspace", back_populates="crime_scene_queries")

    def __repr__(self) -> str:
        return (
            f"<CrimeSceneQuery id={self.id} "
            f"workspace_id={self.workspace_id}>"
        )


# ---------------------------------------------------------------------------
# SubscriptionPlan
# ---------------------------------------------------------------------------


class SubscriptionPlan(Base):
    """A Stripe subscription plan (product + price configuration).

    Currently: $1,200/year, annual auto-renew.
    """

    __tablename__ = "subscription_plans"

    id = Column(Integer, primary_key=True, autoincrement=True)
    stripe_price_id = Column(
        String(100), unique=True, nullable=False,
        comment="Stripe Price ID (e.g. price_xxx)",
    )
    name = Column(String(100), nullable=False)
    price_usd = Column(Float, nullable=False)
    interval = Column(
        String(20), nullable=False, default="year",
        comment="month | year",
    )

    # Relationships
    subscribers = relationship(
        "UserSubscription", back_populates="plan"
    )

    def __repr__(self) -> str:
        return (
            f"<SubscriptionPlan id={self.id} "
            f"name={self.name!r} price=${self.price_usd}>"
        )


# ---------------------------------------------------------------------------
# UserSubscription
# ---------------------------------------------------------------------------


class UserSubscription(Base):
    """A user's current Stripe subscription record.

    Synced via Stripe webhooks (customer.subscription.updated, etc.).
    """

    __tablename__ = "user_subscriptions"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(
        Integer,
        ForeignKey("users.id", ondelete="CASCADE"),
        unique=True,
        nullable=False,
    )
    plan_id = Column(
        Integer, ForeignKey("subscription_plans.id"), nullable=True
    )
    stripe_subscription_id = Column(
        String(100), unique=True, nullable=False,
        comment="Stripe Subscription ID (e.g. sub_xxx)",
    )
    status = Column(
        String(50), nullable=False, default="inactive",
        comment="active | past_due | canceled | trialing | incomplete",
    )
    current_period_end = Column(
        DateTime(timezone=True), nullable=True,
        comment="When the current billing period ends (UTC)",
    )

    # Relationships
    user = relationship("User", back_populates="subscription")
    plan = relationship("SubscriptionPlan", back_populates="subscribers")

    def __repr__(self) -> str:
        return (
            f"<UserSubscription user_id={self.user_id} "
            f"status={self.status!r}>"
        )
