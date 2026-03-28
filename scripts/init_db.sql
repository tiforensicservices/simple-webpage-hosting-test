-- init_db.sql — Bootstrap script run on first PostgreSQL container start.
--
-- This script is mounted at /docker-entrypoint-initdb.d/01_init.sql
-- and is executed automatically when the container initialises a fresh
-- data directory.
--
-- Purpose:
--   1. Enable the pgvector extension (required for Vector columns)
--   2. Create the HNSW index on shoe_images.embedding (done after migrations
--      in production; here we just ensure the extension is available)

-- Enable pgvector
CREATE EXTENSION IF NOT EXISTS vector;

-- Verify
DO $$
BEGIN
  IF EXISTS (
    SELECT 1 FROM pg_extension WHERE extname = 'vector'
  ) THEN
    RAISE NOTICE '✅ pgvector extension is enabled';
  ELSE
    RAISE EXCEPTION '❌ pgvector extension failed to install';
  END IF;
END;
$$;
