#!/usr/bin/env python3
"""
Unit tests for AgentManager
"""

import sys
import tempfile
from pathlib import Path
from unittest.mock import Mock, patch

import pytest

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.agents.agent_manager import AgentInfo, AgentManager


@pytest.fixture
def temp_config_file():
    """Create a temporary config file"""
    content = """
models:
  - id: test-model
    name: Test Model

agents:
  - name: test_agent
    model: test-model
    description: Test agent
    enable_tools: true
"""
    with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
        f.write(content)
        temp_path = Path(f.name)

    yield temp_path

    temp_path.unlink()


class TestAgentManager:
    """Test AgentManager class"""

    def test_agent_manager_init(self):
        """Test AgentManager initialization"""
        manager = AgentManager()

        assert manager._agents == {}
        assert manager._agent_info == {}
        assert manager._storage is None

    def test_agent_manager_init_with_config(self, temp_config_file):
        """Test AgentManager initialization with config file"""
        manager = AgentManager(config_file=temp_config_file)

        assert manager.config is not None

    @patch('src.agents.agent_manager.MemGPTAgent')
    @patch('src.agents.agent_manager.MemoryStorage')
    def test_create_agent(self, mock_storage, mock_agent):
        """Test creating an agent"""
        # Setup mocks
        mock_agent_instance = Mock()
        mock_agent_instance.agent_id = "test-id"
        mock_agent_instance.name = "test_agent"
        mock_agent_instance.model_id = "test-model"
        mock_agent_instance.get_stats.return_value = {
            "archival_memories": 0
        }
        mock_agent.return_value = mock_agent_instance

        manager = AgentManager()

        # Create agent
        info = manager.create_agent(
            name="test_agent",
            model_id="test-model"
        )

        assert isinstance(info, AgentInfo)
        assert info.name == "test_agent"
        assert info.model_id == "test-model"
        assert "test_agent" in manager._agents

    @patch('src.agents.agent_manager.MemGPTAgent')
    def test_create_agent_duplicate_name(self, mock_agent):
        """Test creating agent with duplicate name raises error"""
        mock_agent_instance = Mock()
        mock_agent_instance.agent_id = "test-id"
        mock_agent_instance.get_stats.return_value = {"archival_memories": 0}
        mock_agent.return_value = mock_agent_instance

        manager = AgentManager()

        # Create first agent
        manager.create_agent(name="test_agent", model_id="test-model")

        # Attempt to create duplicate
        with pytest.raises(ValueError, match="already exists"):
            manager.create_agent(name="test_agent", model_id="test-model")

    @patch('src.agents.agent_manager.MemGPTAgent')
    def test_get_agent(self, mock_agent):
        """Test getting an agent"""
        mock_agent_instance = Mock()
        mock_agent_instance.agent_id = "test-id"
        mock_agent_instance.get_stats.return_value = {"archival_memories": 0}
        mock_agent.return_value = mock_agent_instance

        manager = AgentManager()
        manager.create_agent(name="test_agent", model_id="test-model")

        # Get agent
        agent = manager.get_agent("test_agent")
        assert agent is not None

        # Get non-existent agent
        agent = manager.get_agent("non_existent")
        assert agent is None

    @patch('src.agents.agent_manager.MemGPTAgent')
    def test_get_agent_info(self, mock_agent):
        """Test getting agent info"""
        mock_agent_instance = Mock()
        mock_agent_instance.agent_id = "test-id"
        mock_agent_instance.get_stats.return_value = {"archival_memories": 0}
        mock_agent.return_value = mock_agent_instance

        manager = AgentManager()
        manager.create_agent(name="test_agent", model_id="test-model")

        # Get agent info
        info = manager.get_agent_info("test_agent")
        assert info is not None
        assert info.name == "test_agent"

    @patch('src.agents.agent_manager.MemGPTAgent')
    def test_list_agents(self, mock_agent):
        """Test listing agents"""
        mock_agent_instance = Mock()
        mock_agent_instance.agent_id = "test-id"
        mock_agent_instance.get_stats.return_value = {"archival_memories": 0}
        mock_agent.return_value = mock_agent_instance

        manager = AgentManager()

        # No agents initially
        agents = manager.list_agents()
        assert len(agents) == 0

        # Create agents
        manager.create_agent(name="alice", model_id="test-model")
        manager.create_agent(name="bob", model_id="test-model")

        # List agents
        agents = manager.list_agents()
        assert len(agents) == 2

    @patch('src.agents.agent_manager.MemGPTAgent')
    def test_delete_agent(self, mock_agent):
        """Test deleting an agent"""
        mock_agent_instance = Mock()
        mock_agent_instance.agent_id = "test-id"
        mock_agent_instance.get_stats.return_value = {"archival_memories": 0}
        mock_agent.return_value = mock_agent_instance

        manager = AgentManager()
        manager.create_agent(name="test_agent", model_id="test-model")

        # Delete agent
        result = manager.delete_agent("test_agent")
        assert result is True
        assert "test_agent" not in manager._agents

        # Try to delete non-existent agent
        result = manager.delete_agent("non_existent")
        assert result is False

    @patch('src.agents.agent_manager.MemGPTAgent')
    def test_route_message(self, mock_agent):
        """Test routing message to agent"""
        mock_agent_instance = Mock()
        mock_agent_instance.agent_id = "test-id"
        mock_agent_instance.name = "test_agent"
        mock_agent_instance.model_id = "test-model"
        mock_agent_instance.chat.return_value = "Test response"
        mock_agent_instance.get_stats.return_value = {
            "archival_memories": 0,
            "name": "test_agent"
        }
        mock_agent.return_value = mock_agent_instance

        manager = AgentManager()
        manager.create_agent(name="test_agent", model_id="test-model")

        # Route message
        response, stats = manager.route_message("test_agent", "Hello")

        assert response == "Test response"
        assert "name" in stats

    @patch('src.agents.agent_manager.MemGPTAgent')
    def test_route_message_non_existent_agent(self, mock_agent):
        """Test routing message to non-existent agent raises error"""
        manager = AgentManager()

        with pytest.raises(ValueError, match="not found"):
            manager.route_message("non_existent", "Hello", auto_create=False)

    def test_register_existing_agent(self):
        """Test registering an existing agent"""
        mock_agent = Mock()
        mock_agent.name = "test_agent"
        mock_agent.agent_id = "test-id"
        mock_agent.model_id = "test-model"
        mock_agent.get_stats.return_value = {"archival_memories": 0}

        manager = AgentManager()

        # Register agent
        info = manager.register_existing_agent(mock_agent)

        assert isinstance(info, AgentInfo)
        assert info.name == "test_agent"
        assert "test_agent" in manager._agents

    def test_register_existing_agent_duplicate(self):
        """Test registering duplicate agent raises error"""
        mock_agent1 = Mock()
        mock_agent1.name = "test_agent"
        mock_agent1.agent_id = "test-id"
        mock_agent1.model_id = "test-model"
        mock_agent1.get_stats.return_value = {"archival_memories": 0}

        manager = AgentManager()
        manager.register_existing_agent(mock_agent1)

        # Try to register again
        mock_agent2 = Mock()
        mock_agent2.name = "test_agent"

        with pytest.raises(ValueError, match="already registered"):
            manager.register_existing_agent(mock_agent2)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
