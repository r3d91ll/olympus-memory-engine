#!/usr/bin/env python3
"""
Inspect ArangoDB to see what ArXiv data exists
"""

import os
import httpx

ARANGO_SOCKET = "/run/arangodb3/arangodb.sock"
ARANGO_PASSWORD = os.environ.get("ARANGO_PASSWORD", "")
ARANGO_DB = "arxiv_datastore"
BASE_URL = "http://localhost"


class ArangoClient:
    """Simple ArangoDB client using httpx over Unix socket"""

    def __init__(self, socket_path: str, database: str, username: str, password: str):
        transport = httpx.HTTPTransport(uds=socket_path, retries=0)
        timeout = httpx.Timeout(connect=5.0, read=60.0, write=60.0, pool=5.0)

        self.client = httpx.Client(
            http2=False,
            base_url=BASE_URL,
            transport=transport,
            timeout=timeout,
            auth=(username, password) if password else None
        )
        self.database = database

    def query(self, aql: str):
        """Execute AQL query"""
        payload = {
            "query": aql,
            "batchSize": 10
        }

        path = f"/_db/{self.database}/_api/cursor"
        response = self.client.post(path, json=payload)

        if response.status_code >= 400:
            raise RuntimeError(f"ArangoDB error {response.status_code}: {response.text}")

        data = response.json()
        return data.get("result", [])

    def list_databases(self):
        """List all databases"""
        response = self.client.get("/_api/database")
        if response.status_code >= 400:
            raise RuntimeError(f"ArangoDB error {response.status_code}: {response.text}")
        return response.json().get("result", [])

    def close(self):
        self.client.close()


def inspect_data():
    print("=" * 70)
    print("Inspecting ArangoDB for ArXiv Data")
    print("=" * 70)

    print(f"\nConnecting to ArangoDB:")
    print(f"  Socket: {ARANGO_SOCKET}")
    print(f"  Database: {ARANGO_DB}")
    print(f"  Auth: {'Yes' if ARANGO_PASSWORD else 'No password (peer auth)'}")

    client = ArangoClient(
        socket_path=ARANGO_SOCKET,
        database="_system",  # Start with _system to list databases
        username='root',
        password=ARANGO_PASSWORD
    )

    try:
        # List databases
        print("\n1. Available databases:")
        databases = client.list_databases()
        for db in databases:
            print(f"   - {db}")

        if ARANGO_DB not in databases:
            print(f"\n❌ Database '{ARANGO_DB}' not found!")
            print(f"Available databases: {databases}")
            return

        # Now connect to arxiv_datastore
        client.close()
        client = ArangoClient(
            socket_path=ARANGO_SOCKET,
            database=ARANGO_DB,
            username='root',
            password=ARANGO_PASSWORD
        )

        # Count papers
        print(f"\n2. Collection counts in '{ARANGO_DB}':")
        for collection in ['arxiv_papers', 'arxiv_abstracts', 'arxiv_embeddings']:
            try:
                result = client.query(f"RETURN LENGTH({collection})")
                print(f"   {collection}: {result[0]:,}")
            except Exception as e:
                print(f"   {collection}: ❌ {str(e)[:50]}")

        # Sample embedding to check dimension
        print("\n3. Sample embedding structure:")
        embeddings = client.query("FOR e IN arxiv_embeddings LIMIT 1 RETURN e")
        if embeddings:
            embedding = embeddings[0]
            print(f"   _key: {embedding.get('_key')}")
            if 'embedding' in embedding:
                emb = embedding['embedding']
                print(f"   Embedding type: {type(emb).__name__}")
                if isinstance(emb, (list, tuple)):
                    print(f"   Embedding dimension: {len(emb)}")
                    print(f"   Sample values (first 5): {emb[:5]}")
        else:
            print("   ❌ No embeddings found")

        # Count papers with valid embeddings
        print("\n4. Papers with valid embeddings:")

        # First check what dimensions exist
        result = client.query("""
            FOR e IN arxiv_embeddings
                LIMIT 5
                RETURN LENGTH(e.embedding)
        """)
        if result:
            print(f"   Sample embedding dimensions: {result}")

        # Count 2048-dim embeddings
        result_2048 = client.query("""
            FOR e IN arxiv_embeddings
                FILTER e.embedding != null
                FILTER LENGTH(e.embedding) == 2048
                COLLECT WITH COUNT INTO count
                RETURN count
        """)
        print(f"   2048-dim embeddings: {result_2048[0]:,}")

        # Count 1024-dim embeddings
        result_1024 = client.query("""
            FOR e IN arxiv_embeddings
                FILTER e.embedding != null
                FILTER LENGTH(e.embedding) == 1024
                COLLECT WITH COUNT INTO count
                RETURN count
        """)
        print(f"   1024-dim embeddings: {result_1024[0]:,}")

        # Sample paper with all data
        print("\n5. Sample complete paper:")
        result = client.query("""
            FOR paper IN arxiv_papers
                LET abstract_doc = DOCUMENT(CONCAT('arxiv_abstracts/', paper._key))
                LET embedding_doc = DOCUMENT(CONCAT('arxiv_embeddings/', paper._key))
                FILTER embedding_doc != null
                LIMIT 1
                RETURN {
                    arxiv_id: paper._key,
                    title: paper.title,
                    has_abstract: abstract_doc != null,
                    has_embedding: embedding_doc != null,
                    embedding_dim: embedding_doc.embedding != null ? LENGTH(embedding_doc.embedding) : null,
                    categories: paper.categories
                }
        """)
        if result:
            import json
            print(json.dumps(result[0], indent=2))

    except Exception as e:
        print(f"\n❌ Error: {e}")

    finally:
        client.close()

    print("\n" + "=" * 70)


if __name__ == "__main__":
    inspect_data()
