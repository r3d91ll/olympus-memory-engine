-- Olympus Memory Engine Schema
-- PostgreSQL + pgvector for fast vector similarity search

-- Enable pgvector extension
CREATE EXTENSION IF NOT EXISTS vector;

-- Main embeddings table
CREATE TABLE memory_vectors (
    id BIGSERIAL PRIMARY KEY,
    vector_id VARCHAR(255) UNIQUE NOT NULL,
    embedding vector(2048) NOT NULL,        -- Jina v4 2048-dim
    content TEXT NOT NULL,
    metadata JSONB DEFAULT '{}',
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

-- HNSW index for cosine similarity search
-- m=16: connections per layer (trade-off: higher = better recall, more memory)
-- ef_construction=64: search depth during index build (higher = better index quality)
CREATE INDEX memory_vectors_embedding_idx
ON memory_vectors
USING hnsw (embedding vector_cosine_ops)
WITH (m = 16, ef_construction = 64);

-- Metadata index for filtering
CREATE INDEX memory_vectors_metadata_idx
ON memory_vectors
USING gin(metadata);

-- Vector ID index
CREATE INDEX memory_vectors_vector_id_idx
ON memory_vectors(vector_id);

-- Trigger to update updated_at
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ language 'plpgsql';

CREATE TRIGGER update_memory_vectors_updated_at
BEFORE UPDATE ON memory_vectors
FOR EACH ROW
EXECUTE FUNCTION update_updated_at_column();

-- Grant permissions
GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA public TO postgres;
GRANT ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA public TO postgres;
