-- PostgreSQL initialization script
-- Creates pgvector extension and necessary databases

-- Enable pgvector extension
CREATE EXTENSION IF NOT EXISTS vector;

-- Create gitea database for Gitea service
CREATE DATABASE gitea;

-- Grant permissions to triagebot user
GRANT ALL PRIVILEGES ON DATABASE langgraph TO triagebot;
GRANT ALL PRIVILEGES ON DATABASE gitea TO triagebot;

-- Create issue_embeddings table for duplicate detection
\c langgraph;

CREATE TABLE IF NOT EXISTS issue_embeddings (
    issue_id INTEGER PRIMARY KEY,
    title TEXT NOT NULL,
    description TEXT NOT NULL,
    embedding vector(1536),  -- text-embedding-3-large truncated (ivfflat/hnsw max 2000 dims)
    stacktrace_hash TEXT,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

-- Create index for fast similarity search (HNSW supports up to 2000 dims)
CREATE INDEX IF NOT EXISTS issue_embeddings_embedding_idx 
ON issue_embeddings 
USING hnsw (embedding vector_cosine_ops);

-- Create index for stacktrace hash lookup
CREATE INDEX IF NOT EXISTS issue_embeddings_stacktrace_hash_idx 
ON issue_embeddings (stacktrace_hash)
WHERE stacktrace_hash IS NOT NULL;

-- Log successful initialization
SELECT 'pgvector extension and tables initialized successfully' AS status;
