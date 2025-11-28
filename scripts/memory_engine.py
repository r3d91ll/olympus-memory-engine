#!/usr/bin/env python3
"""
Olympus Memory Engine - Python Prototype
PostgreSQL + pgvector with HNSW index
Jina v4 embeddings (1024-dim Matryoshka truncation)
"""

import psycopg2
import psycopg2.extras
import numpy as np
from typing import List, Dict, Tuple, Optional
import time
import json

class MemoryEngine:
    """
    PostgreSQL + pgvector based memory engine
    Uses HNSW index for fast similarity search

    Target Performance:
    - Prototype: <10ms query latency
    - C++ version: <1ms
    - Final optimized: <100μs
    """

    def __init__(self,
                 host='/var/run/postgresql',  # UNIX socket for speed
                 database='olympus_memory',
                 user='todd',  # Default to current user for peer auth
                 password=None):
        """Initialize connection to PostgreSQL"""
        self.conn = psycopg2.connect(
            host=host,
            database=database,
            user=user,
            password=password
        )
        psycopg2.extensions.register_adapter(dict, psycopg2.extras.Json)

    def insert(self,
               vector_id: str,
               embedding: np.ndarray,
               content: str,
               metadata: Optional[Dict] = None) -> None:
        """
        Insert a single embedding into the database

        Args:
            vector_id: Unique identifier for this vector
            embedding: 1024-dim numpy array (Jina v4 Matryoshka)
            content: The actual text/data being embedded
            metadata: Optional JSON metadata
        """
        if embedding.shape[0] != 1024:
            raise ValueError(f"Expected 1024-dim embedding, got {embedding.shape[0]}")

        if metadata is None:
            metadata = {}

        # Normalize for cosine similarity
        embedding_norm = embedding / np.linalg.norm(embedding)

        with self.conn.cursor() as cur:
            cur.execute("""
                INSERT INTO memory_vectors (vector_id, embedding, content, metadata)
                VALUES (%s, %s, %s, %s)
                ON CONFLICT (vector_id) DO UPDATE
                SET embedding = EXCLUDED.embedding,
                    content = EXCLUDED.content,
                    metadata = EXCLUDED.metadata,
                    updated_at = NOW()
            """, (vector_id, embedding_norm.tolist(), content, json.dumps(metadata)))
            self.conn.commit()

    def batch_insert(self,
                    vectors: List[Tuple[str, np.ndarray, str, Dict]],
                    batch_size: int = 1000,
                    verbose: bool = True) -> None:
        """
        Batch insert many embeddings (much faster than individual inserts)

        Args:
            vectors: List of (vector_id, embedding, content, metadata) tuples
            batch_size: Number of vectors per batch
            verbose: Print progress
        """
        if verbose:
            print(f"Inserting {len(vectors)} vectors in batches of {batch_size}...")

        with self.conn.cursor() as cur:
            for i in range(0, len(vectors), batch_size):
                batch = vectors[i:i+batch_size]

                # Normalize all embeddings in batch
                normalized_batch = [
                    (vid, (emb / np.linalg.norm(emb)).tolist(), cnt, json.dumps(meta))
                    for vid, emb, cnt, meta in batch
                ]

                # Use execute_batch for better performance
                psycopg2.extras.execute_batch(cur, """
                    INSERT INTO memory_vectors (vector_id, embedding, content, metadata)
                    VALUES (%s, %s, %s, %s)
                    ON CONFLICT (vector_id) DO NOTHING
                """, normalized_batch, page_size=batch_size)

                self.conn.commit()

                if verbose:
                    print(f"  Inserted {min(i+batch_size, len(vectors))}/{len(vectors)}")

    def query(self,
             embedding: np.ndarray,
             k: int = 10,
             min_score: float = 0.0,
             filter_metadata: Optional[Dict] = None) -> Tuple[List[Dict], float]:
        """
        Query for similar embeddings using cosine similarity

        Args:
            embedding: 1024-dim query embedding
            k: Number of results to return
            min_score: Minimum similarity score (0-1)
            filter_metadata: Optional JSON filter for metadata

        Returns:
            (results, latency_ms) where results is list of dicts with:
                - vector_id: ID of the vector
                - content: The stored content
                - metadata: The stored metadata
                - score: Similarity score (0-1, higher is better)
        """
        if embedding.shape[0] != 1024:
            raise ValueError(f"Expected 1024-dim embedding, got {embedding.shape[0]}")

        start = time.perf_counter()

        # Normalize for cosine similarity
        embedding_norm = embedding / np.linalg.norm(embedding)

        with self.conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            # The <=> operator is cosine distance
            # 1 - cosine_distance = cosine_similarity
            query = """
                SELECT
                    vector_id,
                    content,
                    metadata,
                    1 - (embedding <=> %s::vector) as score
                FROM memory_vectors
                WHERE 1 - (embedding <=> %s::vector) >= %s
            """

            params = [embedding_norm.tolist(), embedding_norm.tolist(), min_score]

            # Add metadata filtering if provided
            if filter_metadata:
                query += " AND metadata @> %s::jsonb"
                params.append(json.dumps(filter_metadata))

            query += " ORDER BY embedding <=> %s::vector LIMIT %s"
            params.extend([embedding_norm.tolist(), k])

            cur.execute(query, params)
            results = cur.fetchall()

        latency_ms = (time.perf_counter() - start) * 1000

        # Convert RealDictRow to regular dicts
        return [dict(r) for r in results], latency_ms

    def count(self) -> int:
        """Get total number of vectors in database"""
        with self.conn.cursor() as cur:
            cur.execute("SELECT COUNT(*) FROM memory_vectors")
            return cur.fetchone()[0]

    def stats(self) -> Dict:
        """Get database statistics"""
        with self.conn.cursor() as cur:
            cur.execute("""
                SELECT
                    COUNT(*) as total_vectors,
                    pg_size_pretty(pg_total_relation_size('memory_vectors')) as table_size,
                    pg_size_pretty(pg_indexes_size('memory_vectors')) as index_size
                FROM memory_vectors
            """)
            row = cur.fetchone()
            return {
                'total_vectors': row[0],
                'table_size': row[1],
                'index_size': row[2]
            }

    def close(self):
        """Close database connection"""
        self.conn.close()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()


def generate_random_embeddings(n: int, dim: int = 1024) -> np.ndarray:
    """Generate random normalized embeddings for testing"""
    embeddings = np.random.randn(n, dim).astype(np.float32)
    # Normalize each embedding
    norms = np.linalg.norm(embeddings, axis=1, keepdims=True)
    return embeddings / norms


if __name__ == '__main__':
    print("Olympus Memory Engine - Python Prototype")
    print("=" * 50)

    # Test with sample data
    print("\n1. Connecting to database...")
    with MemoryEngine() as engine:
        print(f"   Connected! Current vectors: {engine.count()}")

        # Generate sample embeddings
        print("\n2. Generating 100 random embeddings...")
        n_samples = 100
        embeddings = generate_random_embeddings(n_samples)

        # Prepare batch data
        vectors = [
            (f"test_vec_{i}", embeddings[i], f"Sample content {i}", {"index": i, "category": f"cat_{i % 5}"})
            for i in range(n_samples)
        ]

        print("\n3. Inserting embeddings...")
        engine.batch_insert(vectors, batch_size=50, verbose=True)

        print(f"\n4. Database now contains {engine.count()} vectors")
        print(f"   Stats: {engine.stats()}")

        # Test query
        print("\n5. Testing query...")
        query_embedding = embeddings[0]  # Query with first embedding
        results, latency = engine.query(query_embedding, k=5)

        print(f"   Query latency: {latency:.2f}ms")
        print(f"   Found {len(results)} results:")
        for i, result in enumerate(results):
            print(f"     {i+1}. {result['vector_id']}: score={result['score']:.4f}")

        print("\n✅ Prototype working successfully!")
