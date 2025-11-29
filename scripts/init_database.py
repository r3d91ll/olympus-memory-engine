#!/usr/bin/env python3
"""Initialize Olympus Memory Engine database.

Creates PostgreSQL database and schema for multi-agent memory storage.
"""

import os
import sys
from pathlib import Path

import psycopg
from psycopg import sql

# Database connection settings from environment variables
PG_HOST = os.environ.get("PG_HOST", "/var/run/postgresql")  # Unix socket
PG_DB = os.environ.get("PG_DB", "olympus_memory")
PG_USER = os.environ.get("PG_USER", "todd")  # Should match OS user for peer auth


def main():
    """Initialize the database."""
    print("=" * 70)
    print("Olympus Memory Engine - Database Initialization")
    print("=" * 70)

    # Connect to postgres to create database
    print(f"\n1. Connecting to PostgreSQL via Unix socket...")
    print(f"   Socket: {PG_HOST}, User: {PG_USER}")
    try:
        conn = psycopg.connect(
            host=PG_HOST,
            dbname="postgres",
            user=PG_USER,
            autocommit=True
        )
    except psycopg.Error as e:
        print(f"✗ Failed to connect to PostgreSQL: {e}")
        print("\nMake sure PostgreSQL is running and user exists:")
        print("  sudo systemctl status postgresql")
        print("\nTo create PostgreSQL user matching your OS user:")
        print("  sudo -u postgres createuser --createdb todd")
        sys.exit(1)

    print(f"✓ Connected to PostgreSQL")

    # Create database if it doesn't exist
    print(f"\n2. Creating database '{PG_DB}'...")
    with conn.cursor() as cur:
        # Check if database exists
        cur.execute(
            "SELECT 1 FROM pg_database WHERE datname = %s",
            (PG_DB,)
        )
        exists = cur.fetchone()

        if exists:
            print(f"  Database '{PG_DB}' already exists")
        else:
            # Use sql.SQL and sql.Identifier to safely construct CREATE DATABASE statement
            cur.execute(sql.SQL("CREATE DATABASE {}").format(sql.Identifier(PG_DB)))
            print(f"✓ Database '{PG_DB}' created")

    conn.close()

    # Connect to the new database and create schema
    print(f"\n3. Creating schema in '{PG_DB}'...")
    try:
        conn = psycopg.connect(
            host=PG_HOST,
            dbname=PG_DB,
            user=PG_USER
        )
    except psycopg.Error as e:
        print(f"✗ Failed to connect to database '{PG_DB}': {e}")
        print("\nConnection details:")
        print(f"  Socket: {PG_HOST}")
        print(f"  Database: {PG_DB}")
        print(f"  User: {PG_USER}")
        sys.exit(1)

    # Enable pgvector extension
    print("  - Enabling pgvector extension...")
    with conn.cursor() as cur:
        cur.execute("CREATE EXTENSION IF NOT EXISTS vector")
        cur.execute("CREATE EXTENSION IF NOT EXISTS \"uuid-ossp\"")
    conn.commit()
    print("  ✓ Extensions enabled")

    # Load and execute schema
    schema_path = Path(__file__).parent.parent / "src" / "memory" / "schema.sql"
    print(f"  - Loading schema from: {schema_path}")

    if not schema_path.exists():
        print(f"✗ Schema file not found: {schema_path}")
        sys.exit(1)

    schema_sql = schema_path.read_text()

    print("  - Executing schema...")
    with conn.cursor() as cur:
        # Drop existing triggers first (PostgreSQL doesn't support CREATE TRIGGER IF NOT EXISTS)
        cur.execute("DROP TRIGGER IF EXISTS update_agents_updated_at ON agents")
        cur.execute("DROP TRIGGER IF EXISTS update_memory_entries_updated_at ON memory_entries")

        # Execute the full schema
        cur.execute(schema_sql)
    conn.commit()
    print("  ✓ Schema created")

    # Verify tables were created
    print("\n4. Verifying schema...")
    with conn.cursor() as cur:
        cur.execute("""
            SELECT table_name
            FROM information_schema.tables
            WHERE table_schema = 'public'
            ORDER BY table_name
        """)
        tables = [row[0] for row in cur.fetchall()]

    expected_tables = ['agents', 'memory_entries', 'conversation_history', 'geometric_metrics']

    print("  Tables created:")
    for table in tables:
        status = "✓" if table in expected_tables else " "
        print(f"    {status} {table}")

    missing = set(expected_tables) - set(tables)
    if missing:
        print(f"\n  ✗ Missing tables: {', '.join(missing)}")
    else:
        print("\n  ✓ All expected tables present")

    conn.close()

    print("\n" + "=" * 70)
    print("Database initialization complete!")
    print("=" * 70)
    print(f"\nConnection string:")
    print(f"  host={PG_HOST} dbname={PG_DB} user={PG_USER}")
    print()


if __name__ == "__main__":
    main()
