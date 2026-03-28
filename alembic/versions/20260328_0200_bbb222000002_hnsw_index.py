"""Add HNSW index on shoe_images.embedding for cosine similarity search.

Creates a pgvector HNSW index on the ``shoe_images.embedding`` column using
cosine distance (``vector_cosine_ops``).  This index enables fast approximate
nearest-neighbour (ANN) queries used by the crime-scene search pipeline.

Parameters
----------
m : 16
    Max number of connections per layer (higher = better recall, more memory).
ef_construction : 64
    Candidate list size during index construction (higher = better quality).

Usage after applying::

    SELECT si.id, 1 - (si.embedding <=> %s) AS cosine_similarity
    FROM shoe_images si
    ORDER BY si.embedding <=> %s
    LIMIT 20;

Revision ID: bbb222000002
Revises: aaa111000001
Create Date: 2026-03-28 02:00:00.000000
"""

from __future__ import annotations

from typing import Sequence, Union

from alembic import op

# revision identifiers
revision: str = "bbb222000002"
down_revision: Union[str, None] = "aaa111000001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Create HNSW index on shoe_images.embedding (cosine distance)."""
    # NOTE: This statement is NOT run with CONCURRENTLY because Alembic
    # wraps migrations in a transaction.  For large tables (>100k rows)
    # consider running the following SQL manually outside a transaction:
    #
    #   CREATE INDEX CONCURRENTLY ix_shoe_images_embedding_hnsw
    #   ON shoe_images
    #   USING hnsw (embedding vector_cosine_ops)
    #   WITH (m = 16, ef_construction = 64);
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS ix_shoe_images_embedding_hnsw
        ON shoe_images
        USING hnsw (embedding vector_cosine_ops)
        WITH (m = 16, ef_construction = 64)
        """
    )


def downgrade() -> None:
    """Drop the HNSW index (cosine similarity queries will still work, just slower)."""
    op.execute("DROP INDEX IF EXISTS ix_shoe_images_embedding_hnsw")
