"""External storage backend using PostgreSQL + pgvector.

This module provides persistent storage for MemGPT memories with vector embeddings
and geometric analysis hooks.
"""

from typing import Any, Literal, cast
from uuid import UUID, uuid4

import numpy as np
from psycopg.rows import dict_row
from psycopg_pool import ConnectionPool

from src.config.settings import get_settings
from src.logging.logger import get_logger, log_database_operation

logger = get_logger(__name__)

MemoryType = Literal["system", "working", "archival"]


class ExternalStorage:
    """PostgreSQL-backed external storage with pgvector for embeddings."""

    def __init__(self, connection_string: str | None = None) -> None:
        """Initialize external storage with connection pool.

        Args:
            connection_string: PostgreSQL connection string. If None, uses settings.
        """
        settings = get_settings()
        self.connection_string = connection_string or settings.database_connection_string

        # Create connection pool
        self.pool = ConnectionPool(
            self.connection_string,
            min_size=settings.postgres_pool_size,
            max_size=settings.postgres_pool_size + settings.postgres_max_overflow,
        )

        logger.info("External storage initialized", pool_size=settings.postgres_pool_size)

    def close(self) -> None:
        """Close the connection pool."""
        self.pool.close()
        logger.info("External storage closed")

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
            model_id: Model identifier (e.g., "llama3.1:8b")
            system_memory: Initial system memory content
            working_memory: Initial working memory content

        Returns:
            UUID of created agent

        Raises:
            psycopg.Error: If agent creation fails
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

        log_database_operation("INSERT", "agents", agent_id=str(agent_id), name=name)
        logger.info("Agent created", agent_id=str(agent_id), name=name, model_id=model_id)
        return agent_id

    def get_agent(self, agent_id: UUID) -> dict[str, Any] | None:
        """Get agent by ID.

        Args:
            agent_id: Agent UUID

        Returns:
            Agent dict or None if not found
        """
        with self.pool.connection() as conn:
            with conn.cursor(row_factory=dict_row) as cur:
                cur.execute(
                    "SELECT * FROM agents WHERE id = %(id)s",
                    {"id": agent_id},
                )
                agent = cur.fetchone()

        if agent:
            log_database_operation("SELECT", "agents", agent_id=str(agent_id))
        return agent

    def get_agent_by_name(self, name: str) -> dict[str, Any] | None:
        """Get agent by name.

        Args:
            name: Agent name

        Returns:
            Agent dict or None if not found
        """
        with self.pool.connection() as conn:
            with conn.cursor(row_factory=dict_row) as cur:
                cur.execute(
                    "SELECT * FROM agents WHERE name = %(name)s",
                    {"name": name},
                )
                agent = cur.fetchone()

        if agent:
            log_database_operation("SELECT", "agents", name=name)
        return agent

    def delete_agent(self, agent_id: UUID) -> None:
        """Delete agent and all associated data.

        Args:
            agent_id: Agent UUID

        Note:
            Cascading delete will remove all associated memories,
            conversation history, and geometric metrics.
        """
        with self.pool.connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "DELETE FROM agents WHERE id = %(id)s",
                    {"id": agent_id},
                )
                conn.commit()

        log_database_operation("DELETE", "agents", agent_id=str(agent_id))
        logger.info("Agent deleted", agent_id=str(agent_id))

    def update_agent_memory(
        self,
        agent_id: UUID,
        system_memory: str | None = None,
        working_memory: str | None = None,
    ) -> None:
        """Update agent's system and/or working memory.

        Args:
            agent_id: Agent UUID
            system_memory: New system memory content
            working_memory: New working memory content
        """
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

        log_database_operation("UPDATE", "agents", agent_id=str(agent_id))

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
            embedding: Vector embedding (768-dim for nomic-embed-text)

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

        log_database_operation(
            "INSERT",
            "memory_entries",
            memory_id=str(memory_id),
            agent_id=str(agent_id),
            memory_type=memory_type,
            content_length=len(content),
        )

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
            query_embedding: Query vector (768-dim)
            memory_type: Optional filter by memory type
            limit: Maximum number of results

        Returns:
            List of memory entries ordered by similarity (most similar first)
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

        log_database_operation(
            "SELECT",
            "memory_entries",
            agent_id=str(agent_id),
            memory_type=memory_type,
            search_type="vector_search",
            result_count=len(results),
        )

        return results

    def get_all_memories(
        self,
        agent_id: UUID,
        memory_type: MemoryType | None = None,
    ) -> list[dict[str, Any]]:
        """Get all memories for an agent.

        Args:
            agent_id: Agent UUID
            memory_type: Optional filter by memory type

        Returns:
            List of all memory entries
        """
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
                results = cur.fetchall()

        return results

    def get_memory_embeddings(
        self,
        agent_id: UUID,
        memory_type: MemoryType | None = None,
    ) -> np.ndarray:
        """Get all embeddings for geometric analysis.

        Args:
            agent_id: Agent UUID
            memory_type: Optional filter by memory type

        Returns:
            NumPy array of shape (n_memories, embedding_dim)
        """
        memories = self.get_all_memories(agent_id, memory_type)

        # Filter out memories without embeddings
        embeddings = [m["embedding"] for m in memories if m.get("embedding")]

        if not embeddings:
            return np.array([]).reshape(0, 768)

        return np.array(embeddings)

    def insert_conversation(
        self,
        agent_id: UUID,
        role: Literal["user", "assistant", "function"],
        content: str,
        function_name: str | None = None,
        function_args: dict[str, Any] | None = None,
    ) -> UUID:
        """Insert a conversation history entry.

        Args:
            agent_id: Agent UUID
            role: Message role
            content: Message content
            function_name: Function name if role is "function"
            function_args: Function arguments if role is "function"

        Returns:
            UUID of created conversation entry
        """
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

        log_database_operation(
            "INSERT",
            "conversation_history",
            conv_id=str(conv_id),
            agent_id=str(agent_id),
            role=role,
        )

        return conv_id

    def get_conversation_history(
        self,
        agent_id: UUID,
        limit: int = 50,
    ) -> list[dict[str, Any]]:
        """Get conversation history for an agent.

        Args:
            agent_id: Agent UUID
            limit: Maximum number of entries to return

        Returns:
            List of conversation entries (most recent first)
        """
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

    def cache_geometric_metrics(
        self,
        agent_id: UUID,
        d_eff: float,
        mean_nn_distance: float | None = None,
        beta_score: float | None = None,
        label_consistency: float | None = None,
        boundary_sharpness: float | None = None,
        distance_matrix: dict[str, Any] | None = None,
        cluster_assignments: dict[str, Any] | None = None,
        memory_entry_count: int = 0,
    ) -> UUID:
        """Cache geometric analysis metrics.

        Args:
            agent_id: Agent UUID
            d_eff: Effective dimensionality
            mean_nn_distance: Mean k-NN distance
            beta_score: Temporal amplification (collapse indicator)
            label_consistency: Label consistency metric
            boundary_sharpness: Boundary sharpness metric
            distance_matrix: Cached distance relationships
            cluster_assignments: Semantic clustering
            memory_entry_count: Number of memories analyzed

        Returns:
            UUID of cached metrics entry
        """
        metrics_id = uuid4()

        with self.pool.connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO geometric_metrics
                    (id, agent_id, d_eff, mean_nn_distance, beta_score,
                     label_consistency, boundary_sharpness, distance_matrix,
                     cluster_assignments, memory_entry_count)
                    VALUES (%(id)s, %(agent_id)s, %(d_eff)s, %(mean_nn_distance)s,
                            %(beta_score)s, %(label_consistency)s, %(boundary_sharpness)s,
                            %(distance_matrix)s, %(cluster_assignments)s, %(memory_entry_count)s)
                    """,
                    {
                        "id": metrics_id,
                        "agent_id": agent_id,
                        "d_eff": d_eff,
                        "mean_nn_distance": mean_nn_distance,
                        "beta_score": beta_score,
                        "label_consistency": label_consistency,
                        "boundary_sharpness": boundary_sharpness,
                        "distance_matrix": distance_matrix,
                        "cluster_assignments": cluster_assignments,
                        "memory_entry_count": memory_entry_count,
                    },
                )
                conn.commit()

        log_database_operation(
            "INSERT",
            "geometric_metrics",
            metrics_id=str(metrics_id),
            agent_id=str(agent_id),
            d_eff=d_eff,
            beta_score=beta_score,
        )

        return metrics_id

    def get_latest_geometric_metrics(self, agent_id: UUID) -> dict[str, Any] | None:
        """Get the latest geometric metrics for an agent.

        Args:
            agent_id: Agent UUID

        Returns:
            Latest metrics dict or None if no metrics exist
        """
        with self.pool.connection() as conn:
            with conn.cursor(row_factory=dict_row) as cur:
                cur.execute(
                    """
                    SELECT * FROM geometric_metrics
                    WHERE agent_id = %(agent_id)s
                    ORDER BY computed_at DESC
                    LIMIT 1
                    """,
                    {"agent_id": agent_id},
                )
                metrics = cur.fetchone()

        return metrics
