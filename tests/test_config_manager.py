#!/usr/bin/env python3
"""
Unit tests for ConfigManager
"""

import sys
import tempfile
from pathlib import Path

import pytest

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.infrastructure.config_manager import (
    AgentConfig,
    ConfigManager,
    ExperimentConfig,
    SystemConfig,
)


@pytest.fixture
def sample_config_file():
    """Create a sample config file for testing"""
    content = """
system:
  log_level: INFO
  log_dir: logs
  metrics_dir: metrics
  output_dir: output

database:
  host: localhost
  port: 5432

monitoring:
  prometheus_enabled: true

models:
  - id: test-model
    name: Test Model
    description: A test model

agents:
  - name: test_agent
    model: test-model
    description: Test agent
    enable_tools: true

experiments:
  - name: test_experiment
    type: test_type
    description: Test experiment
    agents:
      - test_agent
    parameters:
      max_iterations: 5
    metrics:
      - test_metric
    validation:
      require_tests: true
"""
    with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
        f.write(content)
        temp_path = Path(f.name)

    yield temp_path

    # Cleanup
    temp_path.unlink()


class TestAgentConfig:
    """Test AgentConfig dataclass"""

    def test_agent_config_creation(self):
        """Test creating an AgentConfig"""
        config = AgentConfig(
            name="test",
            model="test-model",
            description="Test agent"
        )

        assert config.name == "test"
        assert config.model == "test-model"
        assert config.description == "Test agent"
        assert config.enable_tools is True

    def test_agent_config_to_dict(self):
        """Test converting AgentConfig to dict"""
        config = AgentConfig(
            name="test",
            model="test-model",
            description="Test agent"
        )

        config_dict = config.to_dict()

        assert config_dict["name"] == "test"
        assert config_dict["model"] == "test-model"
        assert "enable_tools" in config_dict


class TestExperimentConfig:
    """Test ExperimentConfig dataclass"""

    def test_experiment_config_creation(self):
        """Test creating an ExperimentConfig"""
        config = ExperimentConfig(
            name="test_exp",
            type="test_type",
            description="Test experiment",
            agents=["alice", "bob"]
        )

        assert config.name == "test_exp"
        assert config.type == "test_type"
        assert len(config.agents) == 2

    def test_experiment_config_to_dict(self):
        """Test converting ExperimentConfig to dict"""
        config = ExperimentConfig(
            name="test_exp",
            type="test_type",
            description="Test experiment",
            agents=["alice"],
            parameters={"max_iterations": 10}
        )

        config_dict = config.to_dict()

        assert config_dict["name"] == "test_exp"
        assert config_dict["parameters"]["max_iterations"] == 10


class TestSystemConfig:
    """Test SystemConfig dataclass"""

    def test_system_config_defaults(self):
        """Test SystemConfig default values"""
        config = SystemConfig()

        assert config.log_level == "INFO"
        assert config.log_dir == "logs"
        assert config.metrics_dir == "metrics"

    def test_system_config_to_dict(self):
        """Test converting SystemConfig to dict"""
        config = SystemConfig(log_level="DEBUG")

        config_dict = config.to_dict()

        assert config_dict["log_level"] == "DEBUG"


class TestConfigManager:
    """Test ConfigManager class"""

    def test_config_manager_init(self):
        """Test ConfigManager initialization"""
        manager = ConfigManager()

        assert manager.system is not None
        assert isinstance(manager.agents, dict)
        assert isinstance(manager.experiments, dict)
        assert isinstance(manager.models, dict)

    def test_config_manager_load(self, sample_config_file):
        """Test loading config from file"""
        manager = ConfigManager(config_file=sample_config_file)

        # Check system config
        assert manager.system.log_level == "INFO"
        assert manager.system.log_dir == "logs"

        # Check models
        assert "test-model" in manager.models

        # Check agents
        assert "test_agent" in manager.agents
        agent = manager.agents["test_agent"]
        assert agent.model == "test-model"
        assert agent.enable_tools is True

        # Check experiments
        assert "test_experiment" in manager.experiments
        exp = manager.experiments["test_experiment"]
        assert exp.type == "test_type"
        assert "test_agent" in exp.agents

    def test_get_agent_config(self, sample_config_file):
        """Test getting agent config"""
        manager = ConfigManager(config_file=sample_config_file)

        agent = manager.get_agent_config("test_agent")
        assert agent is not None
        assert agent.name == "test_agent"

        # Test non-existent agent
        non_existent = manager.get_agent_config("non_existent")
        assert non_existent is None

    def test_get_experiment_config(self, sample_config_file):
        """Test getting experiment config"""
        manager = ConfigManager(config_file=sample_config_file)

        exp = manager.get_experiment_config("test_experiment")
        assert exp is not None
        assert exp.name == "test_experiment"

        # Test non-existent experiment
        non_existent = manager.get_experiment_config("non_existent")
        assert non_existent is None

    def test_add_agent(self):
        """Test adding an agent"""
        manager = ConfigManager()

        agent = AgentConfig(name="new_agent", model="test-model")
        manager.add_agent(agent)

        assert "new_agent" in manager.agents
        assert manager.agents["new_agent"].model == "test-model"

    def test_add_experiment(self):
        """Test adding an experiment"""
        manager = ConfigManager()

        exp = ExperimentConfig(
            name="new_exp",
            type="test",
            description="Test",
            agents=["alice"]
        )
        manager.add_experiment(exp)

        assert "new_exp" in manager.experiments
        assert manager.experiments["new_exp"].type == "test"

    def test_create_agent_from_template(self, sample_config_file):
        """Test creating agent from template"""
        manager = ConfigManager(config_file=sample_config_file)

        # Create from template
        new_agent = manager.create_agent_from_template(
            name="new_agent",
            model="new-model",
            template="test_agent",
            description="New agent"
        )

        assert new_agent.name == "new_agent"
        assert new_agent.model == "new-model"
        assert new_agent.description == "New agent"
        assert new_agent.enable_tools is True  # Copied from template

    def test_create_agent_without_template(self):
        """Test creating agent without template"""
        manager = ConfigManager()

        new_agent = manager.create_agent_from_template(
            name="new_agent",
            model="new-model",
            description="New agent"
        )

        assert new_agent.name == "new_agent"
        assert new_agent.model == "new-model"

    def test_create_experiment_template(self):
        """Test creating experiment from template"""
        manager = ConfigManager()

        exp = manager.create_experiment_template(
            name="test_exp",
            exp_type="bug_fixing",
            agents=["alice", "bob"],
            max_iterations=10,
            description="Test experiment"
        )

        assert exp.name == "test_exp"
        assert exp.type == "bug_fixing"
        assert exp.agents == ["alice", "bob"]
        assert exp.parameters["max_iterations"] == 10
        assert exp.description == "Test experiment"

    def test_validate_valid_config(self, sample_config_file):
        """Test validation of valid config"""
        manager = ConfigManager(config_file=sample_config_file)

        errors = manager.validate()

        assert len(errors) == 0

    def test_validate_invalid_agent_model(self):
        """Test validation catches invalid agent model"""
        manager = ConfigManager()

        # Add agent with non-existent model
        agent = AgentConfig(name="test", model="non-existent-model")
        manager.add_agent(agent)

        errors = manager.validate()

        assert len(errors) > 0
        assert "non-existent-model" in errors[0]

    def test_validate_invalid_experiment_agent(self):
        """Test validation catches invalid experiment agent"""
        manager = ConfigManager()

        # Add experiment with non-existent agent
        exp = ExperimentConfig(
            name="test",
            type="test",
            description="Test",
            agents=["non_existent_agent"]
        )
        manager.add_experiment(exp)

        errors = manager.validate()

        assert len(errors) > 0
        assert "non_existent_agent" in errors[0]


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
