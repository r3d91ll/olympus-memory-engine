"""Pytest configuration and fixtures for integration tests."""

import os

import pytest


@pytest.fixture
def temp_db():
    """Provide database access for integration tests.

    This fixture assumes the olympus_memory database is already initialized
    (via `poetry run python scripts/init_database.py`). It just sets up
    environment variables for the test.

    Tests using this fixture should clean up their own data if needed.
    """
    # Set up environment variables for database access
    os.environ.setdefault("PG_USER", os.environ.get("USER", "postgres"))
    os.environ.setdefault("PG_PASSWORD", "")
    os.environ.setdefault("PG_HOST", "localhost")
    os.environ.setdefault("PG_PORT", "5432")
    os.environ.setdefault("PG_DATABASE", "olympus_memory")

    # Yield to test
    yield

    # Cleanup after test (if needed)
    # Tests should clean up their own data
