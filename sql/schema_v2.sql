-- Olympus Memory Engine Schema v2
-- Multi-agent memory with per-agent isolation
-- Adapted from bilateral-experiment, using Jina v4 embeddings (1024-dim)

-- Enable extensions
CREATE EXTENSION IF NOT EXISTS vector;
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- Drop old schema if exists
DROP TABLE IF EXISTS memory_vectors CASCADE;

-- Agents table (each model instance gets an agent entry)
CREATE TABLE IF NOT EXISTS agents (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    name VARCHAR(100) NOT NULL UNIQUE,
    model_id VARCHAR(100) NOT NULL,
    system_memory TEXT,
    working_memory TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Memory entries with embeddings
CREATE TABLE IF NOT EXISTS memory_entries (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    agent_id UUID NOT NULL REFERENCES agents(id) ON DELETE CASCADE,
    content TEXT NOT NULL,
    embedding vector(1024),  -- Jina v4 Matryoshka (1024-dim)
    memory_type VARCHAR(20) NOT NULL CHECK (memory_type IN ('system', 'working', 'archival')),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Indexes for efficient retrieval
CREATE INDEX IF NOT EXISTS idx_memory_entries_agent_id ON memory_entries(agent_id);
CREATE INDEX IF NOT EXISTS idx_memory_entries_memory_type ON memory_entries(agent_id, memory_type);
CREATE INDEX IF NOT EXISTS idx_memory_entries_created_at ON memory_entries(created_at DESC);

-- Vector similarity search index (HNSW for fast approximate nearest neighbor)
CREATE INDEX IF NOT EXISTS idx_memory_entries_embedding ON memory_entries
USING hnsw (embedding vector_cosine_ops)
WITH (m = 16, ef_construction = 64);

-- Conversation history
CREATE TABLE IF NOT EXISTS conversation_history (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    agent_id UUID NOT NULL REFERENCES agents(id) ON DELETE CASCADE,
    role VARCHAR(20) NOT NULL CHECK (role IN ('user', 'assistant', 'function')),
    content TEXT NOT NULL,
    function_name VARCHAR(100),
    function_args JSONB,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Indexes for conversation retrieval
CREATE INDEX IF NOT EXISTS idx_conversation_agent_id ON conversation_history(agent_id);
CREATE INDEX IF NOT EXISTS idx_conversation_created_at ON conversation_history(agent_id, created_at DESC);

-- Geometric metrics cache (for future analysis)
CREATE TABLE IF NOT EXISTS geometric_metrics (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    agent_id UUID NOT NULL REFERENCES agents(id) ON DELETE CASCADE,
    d_eff FLOAT NOT NULL,                    -- Effective dimensionality
    mean_nn_distance FLOAT,                  -- Mean k-NN distance
    beta_score FLOAT,                        -- Collapse indicator
    label_consistency FLOAT,                 -- Label consistency
    boundary_sharpness FLOAT,                -- Boundary sharpness
    distance_matrix JSONB,                   -- Cached distance relationships
    cluster_assignments JSONB,               -- Semantic clustering
    memory_entry_count INT,                  -- Number of memories analyzed
    computed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Index for latest metrics retrieval
CREATE INDEX IF NOT EXISTS idx_geometric_metrics_agent_id ON geometric_metrics(agent_id, computed_at DESC);

-- Function to update the updated_at timestamp
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = CURRENT_TIMESTAMP;
    RETURN NEW;
END;
$$ language 'plpgsql';

-- Triggers for updated_at
CREATE TRIGGER update_agents_updated_at BEFORE UPDATE ON agents
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_memory_entries_updated_at BEFORE UPDATE ON memory_entries
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

-- View for quick agent status overview
CREATE OR REPLACE VIEW agent_status AS
SELECT
    a.id,
    a.name,
    a.model_id,
    a.created_at,
    COUNT(DISTINCT me.id) FILTER (WHERE me.memory_type = 'archival') as archival_count,
    COUNT(DISTINCT ch.id) as conversation_count,
    (SELECT d_eff FROM geometric_metrics gm
     WHERE gm.agent_id = a.id
     ORDER BY computed_at DESC LIMIT 1) as latest_d_eff,
    (SELECT beta_score FROM geometric_metrics gm
     WHERE gm.agent_id = a.id
     ORDER BY computed_at DESC LIMIT 1) as latest_beta
FROM agents a
LEFT JOIN memory_entries me ON a.id = me.agent_id
LEFT JOIN conversation_history ch ON a.id = ch.agent_id
GROUP BY a.id, a.name, a.model_id, a.created_at;
