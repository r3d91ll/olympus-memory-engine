#!/usr/bin/env python3
"""
Olympus Memory Storage
PostgreSQL + pgvector backend for multi-agent memory
Adapted from bilateral-experiment ExternalStorage
"""

from typing import Any, Literal, cast
from uuid import UUID, uuid4

import numpy as np
from psycopg.rows import dict_row
from psycopg_pool import ConnectionPool

MemoryType = Literal["system", "working", "archival"]


class MemoryStorage:
    """PostgreSQL-backed memory storage with pgvector for embeddings."""

    def __init__(self, connection_string: str | None = None):
        """Initialize memory storage with connection pool.

        Args:
            connection_string: PostgreSQL connection string.
                             Default: connects to olympus_memory via Unix socket
        """
        if connection_string is None:
            connection_string = (
                "host=/var/run/postgresql "
                "dbname=olympus_memory "
                "user=todd"
            )

        self.connection_string = connection_string

        # Create connection pool
        self.pool = ConnectionPool(
            self.connection_string,
            min_size=2,
            max_size=10,
        )

        print("[MemoryStorage] Initialized (pool_size=2-10)")

    def close(self):
        """Close the connection pool."""
        self.pool.close()
        print("[MemoryStorage] Closed")

    #
    # Agent operations
    #

    def create_agent(
        self,
        name: str,
        model_id: str,
        system_memory: str | None = None,
        working_memory: str | None = None,
    ) -> UUID:
        """Create a new agent.

        Args:
            name: Agent name (must be unique)
            model_id: Model identifier (e.g., "qwen3-30b")
            system_memory: Initial system memory content
            working_memory: Initial working memory content

        Returns:
            UUID of created agent
        """
        with self.pool.connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO agents (name, model_id, system_memory, working_memory)
                    VALUES (%(name)s, %(model_id)s, %(system_memory)s, %(working_memory)s)
                    RETURNING id
                    """,
                    {
                        "name": name,
                        "model_id": model_id,
                        "system_memory": system_memory,
                        "working_memory": working_memory,
                    },
                )
                result = cur.fetchone()
                agent_id = cast(UUID, result[0]) if result else uuid4()
                conn.commit()

        print(f"[MemoryStorage] Agent created: {name} ({agent_id})")
        return agent_id

    def get_agent(self, agent_id: UUID) -> dict[str, Any] | None:
        """Get agent by ID."""
        with self.pool.connection() as conn:
            with conn.cursor(row_factory=dict_row) as cur:
                cur.execute(
                    "SELECT * FROM agents WHERE id = %(id)s",
                    {"id": agent_id},
                )
                return cur.fetchone()

    def get_agent_by_name(self, name: str) -> dict[str, Any] | None:
        """Get agent by name."""
        with self.pool.connection() as conn:
            with conn.cursor(row_factory=dict_row) as cur:
                cur.execute(
                    "SELECT * FROM agents WHERE name = %(name)s",
                    {"name": name},
                )
                return cur.fetchone()

    def update_agent_memory(
        self,
        agent_id: UUID,
        system_memory: str | None = None,
        working_memory: str | None = None,
    ):
        """Update agent's system and/or working memory."""
        updates = []
        params: dict[str, Any] = {"id": agent_id}

        if system_memory is not None:
            updates.append("system_memory = %(system_memory)s")
            params["system_memory"] = system_memory

        if working_memory is not None:
            updates.append("working_memory = %(working_memory)s")
            params["working_memory"] = working_memory

        if not updates:
            return

        with self.pool.connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    f"UPDATE agents SET {', '.join(updates)} WHERE id = %(id)s",
                    params,
                )
                conn.commit()

    #
    # Memory operations
    #

    def insert_memory(
        self,
        agent_id: UUID,
        content: str,
        memory_type: MemoryType,
        embedding: list[float] | None = None,
    ) -> UUID:
        """Insert a memory entry.

        Args:
            agent_id: Agent UUID
            content: Memory content text
            memory_type: Type of memory (system, working, archival)
            embedding: Vector embedding (1024-dim Jina v4)

        Returns:
            UUID of created memory entry
        """
        memory_id = uuid4()

        with self.pool.connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO memory_entries
                    (id, agent_id, content, memory_type, embedding)
                    VALUES (%(id)s, %(agent_id)s, %(content)s, %(memory_type)s, %(embedding)s)
                    """,
                    {
                        "id": memory_id,
                        "agent_id": agent_id,
                        "content": content,
                        "memory_type": memory_type,
                        "embedding": embedding,
                    },
                )
                conn.commit()

        print(f"[MemoryStorage] Memory inserted: {memory_type} ({len(content)} chars)")
        return memory_id

    def search_memory(
        self,
        agent_id: UUID,
        query_embedding: list[float],
        memory_type: MemoryType | None = None,
        limit: int = 10,
    ) -> list[dict[str, Any]]:
        """Search memories by vector similarity.

        Args:
            agent_id: Agent UUID
            query_embedding: Query vector (1024-dim)
            memory_type: Optional filter by memory type
            limit: Maximum number of results

        Returns:
            List of memory entries ordered by similarity
        """
        where_clauses = ["agent_id = %(agent_id)s", "embedding IS NOT NULL"]
        params: dict[str, Any] = {"agent_id": agent_id, "limit": limit}

        if memory_type:
            where_clauses.append("memory_type = %(memory_type)s")
            params["memory_type"] = memory_type

        with self.pool.connection() as conn:
            with conn.cursor(row_factory=dict_row) as cur:
                # Using cosine distance (1 - cosine similarity)
                cur.execute(
                    f"""
                    SELECT
                        id, agent_id, content, memory_type, created_at,
                        1 - (embedding <=> %(query_embedding)s::vector) as similarity
                    FROM memory_entries
                    WHERE {' AND '.join(where_clauses)}
                    ORDER BY embedding <=> %(query_embedding)s::vector
                    LIMIT %(limit)s
                    """,
                    {**params, "query_embedding": query_embedding},
                )
                results = cur.fetchall()

        print(f"[MemoryStorage] Memory search: found {len(results)} results")
        return results

    def get_all_memories(
        self,
        agent_id: UUID,
        memory_type: MemoryType | None = None,
    ) -> list[dict[str, Any]]:
        """Get all memories for an agent."""
        where_clauses = ["agent_id = %(agent_id)s"]
        params: dict[str, Any] = {"agent_id": agent_id}

        if memory_type:
            where_clauses.append("memory_type = %(memory_type)s")
            params["memory_type"] = memory_type

        with self.pool.connection() as conn:
            with conn.cursor(row_factory=dict_row) as cur:
                cur.execute(
                    f"""
                    SELECT id, agent_id, content, memory_type, embedding, created_at
                    FROM memory_entries
                    WHERE {' AND '.join(where_clauses)}
                    ORDER BY created_at DESC
                    """,
                    params,
                )
                return cur.fetchall()

    def get_memory_embeddings(
        self,
        agent_id: UUID,
        memory_type: MemoryType | None = None,
    ) -> np.ndarray:
        """Get all embeddings for geometric analysis.

        Returns:
            NumPy array of shape (n_memories, 1024)
        """
        memories = self.get_all_memories(agent_id, memory_type)

        # Filter out memories without embeddings
        embeddings = [m["embedding"] for m in memories if m.get("embedding")]

        if not embeddings:
            return np.array([]).reshape(0, 1024)

        return np.array(embeddings)

    #
    # Conversation history
    #

    def insert_conversation(
        self,
        agent_id: UUID,
        role: Literal["user", "assistant", "function", "system"],
        content: str,
        function_name: str | None = None,
        function_args: dict[str, Any] | None = None,
    ) -> UUID:
        """Insert a conversation history entry."""
        conv_id = uuid4()

        with self.pool.connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO conversation_history
                    (id, agent_id, role, content, function_name, function_args)
                    VALUES (%(id)s, %(agent_id)s, %(role)s, %(content)s,
                            %(function_name)s, %(function_args)s)
                    """,
                    {
                        "id": conv_id,
                        "agent_id": agent_id,
                        "role": role,
                        "content": content,
                        "function_name": function_name,
                        "function_args": function_args,
                    },
                )
                conn.commit()

        return conv_id

    def get_conversation_history(
        self,
        agent_id: UUID,
        limit: int = 50,
    ) -> list[dict[str, Any]]:
        """Get conversation history for an agent."""
        with self.pool.connection() as conn:
            with conn.cursor(row_factory=dict_row) as cur:
                cur.execute(
                    """
                    SELECT id, agent_id, role, content, function_name, function_args, created_at
                    FROM conversation_history
                    WHERE agent_id = %(agent_id)s
                    ORDER BY created_at DESC
                    LIMIT %(limit)s
                    """,
                    {"agent_id": agent_id, "limit": limit},
                )
                results = cur.fetchall()

        return results[::-1]  # Reverse to get chronological order


if __name__ == "__main__":
    # Quick test
    print("=" * 70)
    print("Olympus Memory Storage - Quick Test")
    print("=" * 70)

    storage = MemoryStorage()

    # Create test agent
    agent_id = storage.create_agent(
        name="test-agent-1",
        model_id="qwen3-30b",
        system_memory="Test system memory",
        working_memory="Test working memory"
    )

    # Insert test memory with random embedding
    embedding = np.random.randn(1024).astype(np.float32)
    embedding = embedding / np.linalg.norm(embedding)  # Normalize

    memory_id = storage.insert_memory(
        agent_id=agent_id,
        content="This is a test memory about machine learning",
        memory_type="archival",
        embedding=embedding.tolist()
    )

    # Search memory
    query_emb = np.random.randn(1024).astype(np.float32)
    query_emb = query_emb / np.linalg.norm(query_emb)

    results = storage.search_memory(
        agent_id=agent_id,
        query_embedding=query_emb.tolist(),
        limit=5
    )

    print(f"\nSearch results: {len(results)}")
    for r in results:
        print(f"  - {r['content'][:60]}... (similarity: {r['similarity']:.4f})")

    storage.close()
    print("\n" + "=" * 70)
