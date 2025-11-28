#!/usr/bin/env python3
"""
Migrate ArXiv data from ArangoDB to PostgreSQL Memory Engine
- Extracts 2.8M papers with combined_embedding (2048-dim)
- Truncates to 1024-dim using Matryoshka truncation
- Loads into olympus_memory database

Usage:
    python3 migrate_arxiv.py [--limit N] [--offset N]
"""

import os
import sys
import httpx
import psycopg2
from psycopg2.extras import execute_batch
import numpy as np
from tqdm import tqdm
import json
import argparse

# ArangoDB connection via Unix socket
ARANGO_SOCKET = "/run/arangodb3/arangodb.sock"
ARANGO_PASSWORD = os.environ.get("ARANGO_PASSWORD", "")
ARANGO_DB = "arxiv_datastore"
BASE_URL = "http://localhost"

# PostgreSQL connection via Unix socket
PG_HOST = "/var/run/postgresql"
PG_DB = "olympus_memory"
PG_USER = "todd"

# Embedding config
SOURCE_DIM = 2048
TARGET_DIM = 1024  # Matryoshka truncation


class ArangoClient:
    """Simple ArangoDB client using httpx over Unix socket"""

    def __init__(self, socket_path: str, database: str, username: str, password: str):
        transport = httpx.HTTPTransport(uds=socket_path, retries=0)
        timeout = httpx.Timeout(connect=10.0, read=300.0, write=300.0, pool=10.0)

        self.client = httpx.Client(
            http2=False,
            base_url=BASE_URL,
            transport=transport,
            timeout=timeout,
            auth=(username, password) if password else None
        )
        self.database = database

    def query(self, aql: str, batch_size: int = 100):
        """Execute AQL query and yield results in batches"""
        payload = {
            "query": aql,
            "batchSize": batch_size
        }

        path = f"/_db/{self.database}/_api/cursor"
        response = self.client.post(path, json=payload)

        if response.status_code >= 400:
            raise RuntimeError(f"ArangoDB error {response.status_code}: {response.text}")

        data = response.json()
        results = data.get("result", [])

        for result in results:
            yield result

        # Handle pagination
        while data.get("hasMore", False):
            cursor_id = data.get("id")
            response = self.client.put(f"/_api/cursor/{cursor_id}")
            if response.status_code >= 400:
                break
            data = response.json()
            for result in data.get("result", []):
                yield result

    def close(self):
        self.client.close()


def connect_postgres():
    """Connect to PostgreSQL via Unix socket"""
    print("Connecting to PostgreSQL...")
    conn = psycopg2.connect(
        host=PG_HOST,
        database=PG_DB,
        user=PG_USER
    )
    print(f"✅ Connected to PostgreSQL database: {PG_DB}")
    return conn


def migrate_arxiv_papers(arango_client, pg_conn, limit=None, offset=0, batch_size=1000):
    """
    Migrate papers from ArangoDB to PostgreSQL

    Extracts:
    - arxiv_papers (metadata)
    - arxiv_abstracts (text content)
    - arxiv_embeddings (combined_embedding: 2048-dim → truncate to 1024-dim)

    Args:
        arango_client: ArangoDB client
        pg_conn: PostgreSQL connection
        limit: Maximum number of papers to migrate (None = all)
        offset: Skip first N papers
        batch_size: Number of papers per batch insert
    """
    print(f"\nMigrating ArXiv papers...")
    print(f"  Offset: {offset}")
    print(f"  Limit: {limit if limit else 'ALL'}")
    print(f"  Batch size: {batch_size}")
    print(f"  Embedding: {SOURCE_DIM} → {TARGET_DIM} dims (Matryoshka truncation)")

    # Build query
    limit_clause = f"LIMIT {offset}, {limit}" if limit else f"LIMIT {offset}, 10000000"

    aql = f"""
        FOR paper IN arxiv_papers
            LET abstract_doc = DOCUMENT(CONCAT('arxiv_abstracts/', paper._key))
            LET embedding_doc = DOCUMENT(CONCAT('arxiv_embeddings/', paper._key))

            FILTER embedding_doc != null
            FILTER embedding_doc.combined_embedding != null
            FILTER LENGTH(embedding_doc.combined_embedding) == {SOURCE_DIM}

            {limit_clause}

            RETURN {{
                arxiv_id: paper._key,
                title: paper.title,
                abstract: abstract_doc.abstract,
                categories: paper.categories,
                primary_category: paper.primary_category,
                published: paper.published,
                updated: paper.updated,
                authors: paper.authors,
                embedding: embedding_doc.combined_embedding
            }}
    """

    # Execute migration
    with pg_conn.cursor() as cur:
        batch = []
        migrated_count = 0
        skipped_count = 0

        for paper in arango_client.query(aql, batch_size=batch_size):
            arxiv_id = paper.get('arxiv_id')

            if not arxiv_id:
                skipped_count += 1
                continue

            # Get embedding and truncate
            embedding = paper.get('embedding', [])
            if not embedding or len(embedding) != SOURCE_DIM:
                skipped_count += 1
                continue

            # Matryoshka truncation: take first 1024 dims
            embedding_truncated = embedding[:TARGET_DIM]

            # Normalize for cosine similarity
            emb_np = np.array(embedding_truncated, dtype=np.float32)
            emb_norm = emb_np / np.linalg.norm(emb_np)

            # Prepare content (title + abstract)
            title = paper.get('title', '')
            abstract = paper.get('abstract', '')
            content = f"{title}\n\n{abstract}"

            # Metadata
            metadata = {
                'categories': paper.get('categories', []),
                'primary_category': paper.get('primary_category'),
                'published': paper.get('published'),
                'updated': paper.get('updated'),
                'authors': paper.get('authors', [])
            }

            # Prepare row
            row = (
                arxiv_id,
                emb_norm.tolist(),
                content,
                json.dumps(metadata)
            )

            batch.append(row)

            # Insert batch
            if len(batch) >= batch_size:
                execute_batch(cur, """
                    INSERT INTO memory_vectors (vector_id, embedding, content, metadata)
                    VALUES (%s, %s::vector, %s, %s::jsonb)
                    ON CONFLICT (vector_id) DO NOTHING
                """, batch, page_size=batch_size)
                pg_conn.commit()
                migrated_count += len(batch)
                print(f"  Migrated: {migrated_count:,} papers...")
                batch = []

        # Insert remaining
        if batch:
            execute_batch(cur, """
                INSERT INTO memory_vectors (vector_id, embedding, content, metadata)
                VALUES (%s, %s::vector, %s, %s::jsonb)
                ON CONFLICT (vector_id) DO NOTHING
            """, batch, page_size=batch_size)
            pg_conn.commit()
            migrated_count += len(batch)

    print(f"\n✅ Migrated {migrated_count:,} papers to PostgreSQL")
    if skipped_count > 0:
        print(f"⚠️  Skipped {skipped_count:,} papers (missing embeddings or arxiv_id)")

    return migrated_count


def verify_migration(pg_conn):
    """Verify migration completeness"""
    print("\nVerifying migration...")

    with pg_conn.cursor() as cur:
        # Count total
        cur.execute("SELECT COUNT(*) FROM memory_vectors WHERE vector_id LIKE '%/%';")
        pg_count = cur.fetchone()[0]
        print(f"  PostgreSQL papers: {pg_count:,}")

        if pg_count == 0:
            print("  ❌ No papers migrated!")
            return False

        # Sample verification
        cur.execute("""
            SELECT
                vector_id,
                LEFT(content, 80),
                metadata->>'primary_category',
                array_length(embedding, 1) as emb_dim
            FROM memory_vectors
            WHERE vector_id LIKE '%/%'
            LIMIT 5;
        """)

        print("\n  Sample papers:")
        for row in cur.fetchall():
            print(f"    {row[0]}: {row[1]}...")
            print(f"      Category: {row[2]}, Embedding dim: {row[3]}")

        # Check embedding dimensions
        cur.execute("""
            SELECT COUNT(*)
            FROM memory_vectors
            WHERE vector_id LIKE '%/%'
            AND array_length(embedding, 1) != %s;
        """, (TARGET_DIM,))
        wrong_dim_count = cur.fetchone()[0]

        if wrong_dim_count > 0:
            print(f"  ⚠️  {wrong_dim_count:,} papers have wrong embedding dimensions!")
        else:
            print(f"  ✅ All embeddings have correct dimension ({TARGET_DIM})")

    return True


def main():
    """Main migration workflow"""
    parser = argparse.ArgumentParser(description="Migrate ArXiv data from ArangoDB to PostgreSQL")
    parser.add_argument('--limit', type=int, default=None, help='Limit number of papers to migrate')
    parser.add_argument('--offset', type=int, default=0, help='Skip first N papers')
    parser.add_argument('--batch-size', type=int, default=1000, help='Batch size for inserts')
    args = parser.parse_args()

    print("=" * 70)
    print("ArXiv Data Migration: ArangoDB → PostgreSQL Memory Engine")
    print("=" * 70)

    # Connect to databases
    arango_client = ArangoClient(
        socket_path=ARANGO_SOCKET,
        database=ARANGO_DB,
        username='root',
        password=ARANGO_PASSWORD
    )
    pg_conn = connect_postgres()

    try:
        # Migrate data
        migrated = migrate_arxiv_papers(
            arango_client,
            pg_conn,
            limit=args.limit,
            offset=args.offset,
            batch_size=args.batch_size
        )

        # Verify
        if migrated > 0 and verify_migration(pg_conn):
            print("\n" + "=" * 70)
            print("✅ Migration complete!")
            print("=" * 70)
        else:
            print("\n❌ Migration verification failed")
            sys.exit(1)

    finally:
        arango_client.close()
        pg_conn.close()


if __name__ == "__main__":
    main()
