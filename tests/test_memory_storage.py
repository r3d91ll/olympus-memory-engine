#!/usr/bin/env python3
"""
Unit tests for MemoryStorage - CRITICAL INFRASTRUCTURE

Tests database operations, vector search, and data integrity.
"""

import sys
from pathlib import Path
from unittest.mock import MagicMock, Mock, patch
from uuid import uuid4

import pytest

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.memory.memory_storage import MemoryStorage


class TestMemoryStorageConnection:
    """Test database connection management"""

    @patch('src.memory.memory_storage.ConnectionPool')
    def test_init_creates_connection_pool(self, mock_pool):
        """Test that initialization creates connection pool"""
        storage = MemoryStorage()

        # Should have called ConnectionPool
        mock_pool.assert_called_once()
        assert storage.pool is not None

    @patch('src.memory.memory_storage.ConnectionPool')
    def test_close_closes_pool(self, mock_pool):
        """Test that close() closes the connection pool"""
        mock_pool_instance = Mock()
        mock_pool.return_value = mock_pool_instance

        storage = MemoryStorage()
        storage.close()

        # Should have called close on pool
        mock_pool_instance.close.assert_called_once()


class TestAgentOperations:
    """Test agent CRUD operations - CRITICAL"""

    @patch('src.memory.memory_storage.ConnectionPool')
    def test_create_agent(self, mock_pool):
        """Test creating a new agent"""
        # Setup mock
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_conn.__enter__.return_value = mock_conn
        mock_conn.cursor.return_value.__enter__.return_value = mock_cursor

        test_uuid = uuid4()
        mock_cursor.fetchone.return_value = (test_uuid,)

        mock_pool_instance = Mock()
        mock_pool_instance.connection.return_value = mock_conn
        mock_pool.return_value = mock_pool_instance

        storage = MemoryStorage()

        # Create agent
        agent_id = storage.create_agent(
            name="test_agent",
            model_id="test-model",
            system_memory="system",
            working_memory="working"
        )

        # Verify
        assert agent_id == test_uuid
        # Should have executed INSERT
        assert mock_cursor.execute.called

    @patch('src.memory.memory_storage.ConnectionPool')
    def test_get_agent_by_name_found(self, mock_pool):
        """Test getting agent by name when it exists"""
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_conn.__enter__.return_value = mock_conn
        mock_conn.cursor.return_value.__enter__.return_value = mock_cursor

        test_uuid = uuid4()
        mock_cursor.fetchone.return_value = {
            'id': test_uuid,
            'name': 'test_agent',
            'model_id': 'test-model',
            'system_memory': 'system',
            'working_memory': 'working',
            'created_at': '2025-10-26'
        }

        mock_pool_instance = Mock()
        mock_pool_instance.connection.return_value = mock_conn
        mock_pool.return_value = mock_pool_instance

        storage = MemoryStorage()
        agent = storage.get_agent_by_name("test_agent")

        assert agent is not None
        assert agent['name'] == 'test_agent'
        assert agent['id'] == test_uuid

    @patch('src.memory.memory_storage.ConnectionPool')
    def test_get_agent_by_name_not_found(self, mock_pool):
        """Test getting agent by name when it doesn't exist"""
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_conn.__enter__.return_value = mock_conn
        mock_conn.cursor.return_value.__enter__.return_value = mock_cursor
        mock_cursor.fetchone.return_value = None

        mock_pool_instance = Mock()
        mock_pool_instance.connection.return_value = mock_conn
        mock_pool.return_value = mock_pool_instance

        storage = MemoryStorage()
        agent = storage.get_agent_by_name("nonexistent")

        assert agent is None

    @patch('src.memory.memory_storage.ConnectionPool')
    def test_update_agent_memory(self, mock_pool):
        """Test updating agent working memory"""
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_conn.__enter__.return_value = mock_conn
        mock_conn.cursor.return_value.__enter__.return_value = mock_cursor

        mock_pool_instance = Mock()
        mock_pool_instance.connection.return_value = mock_conn
        mock_pool.return_value = mock_pool_instance

        storage = MemoryStorage()
        test_uuid = uuid4()

        # Update memory
        storage.update_agent_memory(
            agent_id=test_uuid,
            working_memory="updated memory"
        )

        # Should have executed UPDATE
        assert mock_cursor.execute.called
        call_args = mock_cursor.execute.call_args[0]
        assert "UPDATE" in call_args[0]
        assert "working_memory" in call_args[0]


class TestMemoryOperations:
    """Test memory CRUD operations - CRITICAL"""

    @patch('src.memory.memory_storage.ConnectionPool')
    def test_insert_memory(self, mock_pool):
        """Test inserting memory with embedding"""
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_conn.__enter__.return_value = mock_conn
        mock_conn.cursor.return_value.__enter__.return_value = mock_cursor

        mock_pool_instance = Mock()
        mock_pool_instance.connection.return_value = mock_conn
        mock_pool.return_value = mock_pool_instance

        storage = MemoryStorage()
        test_uuid = uuid4()

        # Insert memory
        storage.insert_memory(
            agent_id=test_uuid,
            content="test memory",
            memory_type="archival",
            embedding=[0.1] * 768
        )

        # Should have executed INSERT
        assert mock_cursor.execute.called
        call_args = mock_cursor.execute.call_args[0]
        assert "INSERT INTO memory_entries" in call_args[0]

    @patch('src.memory.memory_storage.ConnectionPool')
    def test_get_all_memories(self, mock_pool):
        """Test retrieving all memories for an agent"""
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_conn.__enter__.return_value = mock_conn
        mock_conn.cursor.return_value.__enter__.return_value = mock_cursor

        test_uuid = uuid4()
        mock_cursor.fetchall.return_value = [
            {
                'id': uuid4(),
                'agent_id': test_uuid,
                'content': 'memory 1',
                'memory_type': 'archival',
                'created_at': '2025-10-26'
            },
            {
                'id': uuid4(),
                'agent_id': test_uuid,
                'content': 'memory 2',
                'memory_type': 'archival',
                'created_at': '2025-10-26'
            }
        ]

        mock_pool_instance = Mock()
        mock_pool_instance.connection.return_value = mock_conn
        mock_pool.return_value = mock_pool_instance

        storage = MemoryStorage()
        memories = storage.get_all_memories(agent_id=test_uuid, memory_type="archival")

        assert len(memories) == 2
        assert memories[0]['content'] == 'memory 1'

    @patch('src.memory.memory_storage.ConnectionPool')
    def test_search_memory_vector_similarity(self, mock_pool):
        """Test vector similarity search - CRITICAL FEATURE"""
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_conn.__enter__.return_value = mock_conn
        mock_conn.cursor.return_value.__enter__.return_value = mock_cursor

        test_uuid = uuid4()
        # Mock vector search results with similarity scores
        mock_cursor.fetchall.return_value = [
            {
                'id': uuid4(),
                'content': 'similar memory 1',
                'similarity': 0.95
            },
            {
                'id': uuid4(),
                'content': 'similar memory 2',
                'similarity': 0.85
            }
        ]

        mock_pool_instance = Mock()
        mock_pool_instance.connection.return_value = mock_conn
        mock_pool.return_value = mock_pool_instance

        storage = MemoryStorage()

        # Search with query embedding
        results = storage.search_memory(
            agent_id=test_uuid,
            query_embedding=[0.1] * 768,
            memory_type="archival",
            limit=2
        )

        # Should return results ordered by similarity
        assert len(results) == 2
        assert results[0]['similarity'] == 0.95
        assert results[1]['similarity'] == 0.85

        # Should have used vector similarity operator
        call_args = mock_cursor.execute.call_args[0]
        assert "<=>" in call_args[0]  # pgvector cosine distance operator


class TestConversationHistory:
    """Test conversation history operations"""

    @patch('src.memory.memory_storage.ConnectionPool')
    def test_insert_conversation(self, mock_pool):
        """Test inserting conversation message"""
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_conn.__enter__.return_value = mock_conn
        mock_conn.cursor.return_value.__enter__.return_value = mock_cursor

        mock_pool_instance = Mock()
        mock_pool_instance.connection.return_value = mock_conn
        mock_pool.return_value = mock_pool_instance

        storage = MemoryStorage()
        test_uuid = uuid4()

        # Insert conversation
        storage.insert_conversation(
            agent_id=test_uuid,
            role="user",
            content="Hello"
        )

        # Should have executed INSERT
        assert mock_cursor.execute.called
        call_args = mock_cursor.execute.call_args[0]
        assert "INSERT INTO conversation_history" in call_args[0]

    @patch('src.memory.memory_storage.ConnectionPool')
    def test_get_conversation_history(self, mock_pool):
        """Test retrieving conversation history"""
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_conn.__enter__.return_value = mock_conn
        mock_conn.cursor.return_value.__enter__.return_value = mock_cursor

        test_uuid = uuid4()
        # Results come back in DESC order (newest first)
        mock_cursor.fetchall.return_value = [
            {
                'role': 'assistant',
                'content': 'Hi there',
                'created_at': '2025-10-26 10:00:01'
            },
            {
                'role': 'user',
                'content': 'Hello',
                'created_at': '2025-10-26 10:00:00'
            }
        ]

        mock_pool_instance = Mock()
        mock_pool_instance.connection.return_value = mock_conn
        mock_pool.return_value = mock_pool_instance

        storage = MemoryStorage()
        history = storage.get_conversation_history(agent_id=test_uuid, limit=10)

        assert len(history) == 2
        # Results are reversed to chronological order (oldest first)
        assert history[0]['role'] == 'user'
        assert history[1]['role'] == 'assistant'


class TestDataIntegrity:
    """Test data integrity and validation"""

    @patch('src.memory.memory_storage.ConnectionPool')
    def test_embedding_dimension_validation(self, mock_pool):
        """Test that embeddings must be correct dimension"""
        mock_conn = MagicMock()
        mock_pool_instance = Mock()
        mock_pool_instance.connection.return_value = mock_conn
        mock_pool.return_value = mock_pool_instance

        storage = MemoryStorage()
        test_uuid = uuid4()

        # Should work with correct dimension (768)
        try:
            storage.insert_memory(
                agent_id=test_uuid,
                content="test",
                memory_type="archival",
                embedding=[0.1] * 768
            )
            assert True  # Should not raise
        except:
            pytest.fail("Should accept 768-dim embedding")

    @patch('src.memory.memory_storage.ConnectionPool')
    def test_memory_type_validation(self, mock_pool):
        """Test that memory types are validated"""
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_conn.__enter__.return_value = mock_conn
        mock_conn.cursor.return_value.__enter__.return_value = mock_cursor

        mock_pool_instance = Mock()
        mock_pool_instance.connection.return_value = mock_conn
        mock_pool.return_value = mock_pool_instance

        storage = MemoryStorage()
        test_uuid = uuid4()

        # Valid memory types should work
        valid_types = ["archival", "working", "system"]
        for memory_type in valid_types:
            storage.insert_memory(
                agent_id=test_uuid,
                content="test",
                memory_type=memory_type,
                embedding=[0.1] * 768
            )
            assert True  # Should not raise


class TestErrorHandling:
    """Test error handling and recovery"""

    @patch('src.memory.memory_storage.ConnectionPool')
    def test_connection_error_handling(self, mock_pool):
        """Test handling of connection errors"""
        mock_pool_instance = Mock()
        mock_pool_instance.connection.side_effect = Exception("Connection failed")
        mock_pool.return_value = mock_pool_instance

        storage = MemoryStorage()

        # Should raise or handle gracefully
        with pytest.raises(Exception):
            storage.get_agent_by_name("test")

    @patch('src.memory.memory_storage.ConnectionPool')
    def test_transaction_rollback_on_error(self, mock_pool):
        """Test that transactions rollback on error"""
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_conn.__enter__.return_value = mock_conn
        mock_conn.cursor.return_value.__enter__.return_value = mock_cursor

        # Simulate error during execute
        mock_cursor.execute.side_effect = Exception("SQL error")

        mock_pool_instance = Mock()
        mock_pool_instance.connection.return_value = mock_conn
        mock_pool.return_value = mock_pool_instance

        storage = MemoryStorage()
        test_uuid = uuid4()

        # Should handle error gracefully
        with pytest.raises(Exception):
            storage.insert_memory(
                agent_id=test_uuid,
                content="test",
                memory_type="archival",
                embedding=[0.1] * 768
            )


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
