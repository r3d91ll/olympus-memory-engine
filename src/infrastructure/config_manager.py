"""
Enhanced Configuration Management for Experiments

Provides:
- Easy agent configuration via YAML
- Experiment templates
- Config validation
- Environment-specific overrides
"""

import os
from copy import deepcopy
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Optional

import yaml


@dataclass
class AgentConfig:
    """Configuration for a single agent"""
    name: str
    model: str
    description: str = ""
    enable_tools: bool = True
    workspace_dir: Optional[str] = None
    memory_config: dict[str, Any] = field(default_factory=dict)
    system_prompt_override: Optional[str] = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class ExperimentConfig:
    """Configuration for an experiment"""
    name: str
    type: str  # e.g., 'bug_fixing', 'api_learning', 'navigation'
    description: str
    agents: list[str]  # List of agent names involved
    parameters: dict[str, Any] = field(default_factory=dict)
    metrics: list[str] = field(default_factory=list)
    validation: dict[str, Any] = field(default_factory=dict)
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class SystemConfig:
    """System-wide configuration"""
    log_level: str = "INFO"
    log_dir: str = "logs"
    metrics_dir: str = "metrics"
    output_dir: str = "output"
    database: dict[str, Any] = field(default_factory=dict)
    monitoring: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class ConfigManager:
    """Centralized configuration management"""

    def __init__(self, config_file: Path = Path("config.yaml")):
        self.config_file = Path(config_file)
        self._raw_config: dict[str, Any] = {}
        self.system: SystemConfig = SystemConfig()
        self.agents: dict[str, AgentConfig] = {}
        self.experiments: dict[str, ExperimentConfig] = {}
        self.models: dict[str, dict[str, str]] = {}

        if self.config_file.exists():
            self.load()

    def load(self):
        """Load configuration from YAML file"""
        with open(self.config_file) as f:
            self._raw_config = yaml.safe_load(f) or {}

        # Load system config
        self._load_system_config()

        # Load models
        self._load_models()

        # Load agent configs
        self._load_agents()

        # Load experiment configs
        self._load_experiments()

    def _load_system_config(self):
        """Load system configuration"""
        system_data = self._raw_config.get('system', {})

        self.system = SystemConfig(
            log_level=system_data.get('log_level', 'INFO'),
            log_dir=system_data.get('log_dir', 'logs'),
            metrics_dir=system_data.get('metrics_dir', 'metrics'),
            output_dir=system_data.get('output_dir', 'output'),
            database=self._raw_config.get('database', {}),
            monitoring=self._raw_config.get('monitoring', {})
        )

    def _load_models(self):
        """Load model definitions"""
        models_list = self._raw_config.get('models', [])
        for model in models_list:
            model_id = model.get('id')
            if model_id:
                self.models[model_id] = model

    def _load_agents(self):
        """Load agent configurations"""
        agents_list = self._raw_config.get('agents', [])
        for agent_data in agents_list:
            agent = AgentConfig(
                name=agent_data['name'],
                model=agent_data.get('model', self._raw_config.get('default_model', 'llama3.1:8b')),
                description=agent_data.get('description', ''),
                enable_tools=agent_data.get('enable_tools', True),
                workspace_dir=agent_data.get('workspace_dir'),
                memory_config=agent_data.get('memory', {}),
                system_prompt_override=agent_data.get('system_prompt'),
                metadata=agent_data.get('metadata', {})
            )
            self.agents[agent.name] = agent

    def _load_experiments(self):
        """Load experiment configurations"""
        experiments_list = self._raw_config.get('experiments', [])
        for exp_data in experiments_list:
            experiment = ExperimentConfig(
                name=exp_data['name'],
                type=exp_data['type'],
                description=exp_data.get('description', ''),
                agents=exp_data.get('agents', []),
                parameters=exp_data.get('parameters', {}),
                metrics=exp_data.get('metrics', []),
                validation=exp_data.get('validation', {}),
                metadata=exp_data.get('metadata', {})
            )
            self.experiments[experiment.name] = experiment

    def save(self):
        """Save current configuration to YAML file"""
        config_data = {
            'system': self.system.to_dict(),
            'models': list(self.models.values()),
            'agents': [agent.to_dict() for agent in self.agents.values()],
            'experiments': [exp.to_dict() for exp in self.experiments.values()],
        }

        # Preserve other fields from raw config
        for key, value in self._raw_config.items():
            if key not in config_data:
                config_data[key] = value

        with open(self.config_file, 'w') as f:
            yaml.dump(config_data, f, default_flow_style=False, sort_keys=False)

    def get_agent_config(self, name: str) -> Optional[AgentConfig]:
        """Get configuration for a specific agent"""
        return self.agents.get(name)

    def get_experiment_config(self, name: str) -> Optional[ExperimentConfig]:
        """Get configuration for a specific experiment"""
        return self.experiments.get(name)

    def add_agent(self, agent: AgentConfig):
        """Add a new agent configuration"""
        self.agents[agent.name] = agent

    def add_experiment(self, experiment: ExperimentConfig):
        """Add a new experiment configuration"""
        self.experiments[experiment.name] = experiment

    def create_agent_from_template(
        self,
        name: str,
        model: str,
        template: Optional[str] = None,
        **overrides
    ) -> AgentConfig:
        """Create a new agent from a template

        Args:
            name: Agent name
            model: Model to use
            template: Template agent to copy from
            **overrides: Override any AgentConfig fields

        Returns:
            New AgentConfig instance
        """
        if template and template in self.agents:
            # Copy from template
            agent = deepcopy(self.agents[template])
            agent.name = name
            agent.model = model
        else:
            # Create new
            agent = AgentConfig(name=name, model=model)

        # Apply overrides
        for key, value in overrides.items():
            if hasattr(agent, key):
                setattr(agent, key, value)

        return agent

    def create_experiment_template(
        self,
        name: str,
        exp_type: str,
        agents: list[str],
        **parameters
    ) -> ExperimentConfig:
        """Create an experiment configuration from template

        Args:
            name: Experiment name
            exp_type: Experiment type
            agents: List of agent names
            **parameters: Experiment parameters

        Returns:
            New ExperimentConfig instance
        """
        return ExperimentConfig(
            name=name,
            type=exp_type,
            description=parameters.pop('description', ''),
            agents=agents,
            parameters=parameters
        )

    def validate(self) -> list[str]:
        """Validate configuration

        Returns:
            List of validation errors (empty if valid)
        """
        errors = []

        # Check that all agent models exist
        for agent_name, agent in self.agents.items():
            if agent.model not in self.models:
                errors.append(f"Agent '{agent_name}' uses undefined model '{agent.model}'")

        # Check that all experiment agents exist
        for exp_name, exp in self.experiments.items():
            for agent_name in exp.agents:
                if agent_name not in self.agents:
                    errors.append(f"Experiment '{exp_name}' references undefined agent '{agent_name}'")

        return errors

    def get_env_override(self, key: str, default: Any = None) -> Any:
        """Get configuration value with environment variable override

        Args:
            key: Config key (dot-separated path, e.g., 'system.log_level')
            default: Default value if not found

        Returns:
            Configuration value
        """
        # Convert key to environment variable name
        env_key = f"AGENT_{key.upper().replace('.', '_')}"

        # Check environment
        env_value = os.getenv(env_key)
        if env_value is not None:
            return env_value

        # Navigate config dict
        parts = key.split('.')
        value = self._raw_config
        for part in parts:
            if isinstance(value, dict):
                value = value.get(part)
            else:
                return default

        return value if value is not None else default


# Global config manager instance
_config_manager: Optional[ConfigManager] = None


def get_config() -> ConfigManager:
    """Get the global config manager instance"""
    global _config_manager
    if _config_manager is None:
        _config_manager = ConfigManager()
    return _config_manager


def init_config(config_file: Path = Path("config.yaml")) -> ConfigManager:
    """Initialize the global config manager"""
    global _config_manager
    _config_manager = ConfigManager(config_file=config_file)
    return _config_manager


def reload_config():
    """Reload configuration from file"""
    get_config().load()
