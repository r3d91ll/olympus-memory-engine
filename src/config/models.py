"""Pydantic configuration models for Olympus Memory Engine.

These models provide:
- Type safety at runtime and for static analysis
- Validation of configuration values
- Clear documentation of configuration structure
- Easy serialization/deserialization
- Future C++/Mojo portability (all types explicitly defined)

Architecture:
    OllamaModelConfig (base LLM config)
    └── HarmonyFormatConfig (GPT-OSS specific format)

    AgentConfig (per-agent settings)
    └── uses OllamaModelConfig + optional HarmonyFormatConfig

    OMEConfig (root config)
    └── contains all agent configs, memory settings, etc.
"""

from pathlib import Path
from typing import Literal

import yaml
from pydantic import BaseModel, ConfigDict, Field, field_validator


class HarmonyFormatConfig(BaseModel):
    """Configuration for Harmony format (GPT-OSS models).

    Harmony format uses structured channels for model output:
    - analysis: Internal reasoning/thinking
    - commentary: Meta-commentary on the task
    - final: The actual response to return

    Special tokens delimit these channels in the raw output.
    """

    enabled: bool = True

    # Channel configuration
    channels: list[str] = Field(
        default=["analysis", "commentary", "final"],
        description="Output channels supported by the model"
    )
    default_channel: str = Field(
        default="final",
        description="Channel to extract for response if not specified"
    )

    # Special tokens used by Harmony format
    start_token: str = Field(default="<|start|>", description="Start of message")
    end_token: str = Field(default="<|end|>", description="End of message")
    channel_token: str = Field(default="<|channel|>", description="Channel delimiter")
    message_token: str = Field(default="<|message|>", description="Message content delimiter")
    call_token: str = Field(default="<|call|>", description="Function call delimiter")
    result_token: str = Field(default="<|result|>", description="Function result delimiter")

    # Tool calling behavior
    supports_native_tools: bool = Field(
        default=True,
        description="Whether model uses Ollama's native tool_calls field"
    )

    @property
    def special_tokens(self) -> dict[str, str]:
        """Get all special tokens as a dictionary."""
        return {
            "start": self.start_token,
            "end": self.end_token,
            "channel": self.channel_token,
            "message": self.message_token,
            "call": self.call_token,
            "result": self.result_token,
        }


class OllamaModelConfig(BaseModel):
    """Configuration for an Ollama-served LLM.

    This is the base model configuration used by all Ollama models.
    Format-specific configs (like HarmonyFormatConfig) compose with this.
    """

    model_config = ConfigDict(populate_by_name=True)

    model_id: str = Field(
        alias="id",
        description="Ollama model identifier (e.g., 'gpt-oss:20b', 'llama3.1:8b')"
    )
    name: str = Field(
        default="",
        description="Human-readable model name"
    )
    description: str = Field(
        default="",
        description="Model description"
    )

    # Generation parameters
    temperature: float = Field(
        default=0.7,
        ge=0.0,
        le=2.0,
        description="Sampling temperature (0=deterministic, higher=more random)"
    )
    max_tokens: int = Field(
        default=2048,
        ge=1,
        le=32768,
        description="Maximum tokens to generate per response"
    )
    top_p: float = Field(
        default=0.9,
        ge=0.0,
        le=1.0,
        description="Nucleus sampling threshold"
    )
    top_k: int = Field(
        default=40,
        ge=0,
        description="Top-k sampling (0=disabled)"
    )

    # Format configuration (optional, for models like GPT-OSS)
    harmony_format: HarmonyFormatConfig | None = Field(
        default=None,
        description="Harmony format config for GPT-OSS models"
    )

    @field_validator("model_id")
    @classmethod
    def validate_model_id(cls, v: str) -> str:
        """Ensure model_id is not empty."""
        if not v or not v.strip():
            raise ValueError("model_id cannot be empty")
        return v.strip()

    def uses_harmony_format(self) -> bool:
        """Check if this model uses Harmony format."""
        if self.harmony_format is not None and self.harmony_format.enabled:
            return True
        # Auto-detect based on model name
        harmony_models = ["gpt-oss", "gpt-oss:20b", "gpt-oss:120b"]
        return any(m in self.model_id.lower() for m in harmony_models)


class MemoryConfig(BaseModel):
    """Configuration for the hierarchical memory system."""

    fifo_queue_size: int = Field(
        default=10,
        ge=1,
        le=100,
        description="Number of recent messages to keep in FIFO queue"
    )
    archival_search_limit: int = Field(
        default=5,
        ge=1,
        le=50,
        description="Maximum memories to return from archival search"
    )
    embedding_model: str = Field(
        default="nomic-embed-text",
        description="Ollama model for generating embeddings"
    )
    embedding_dim: int = Field(
        default=768,
        description="Dimension of embedding vectors"
    )


class AgentConfig(BaseModel):
    """Configuration for a single agent."""

    name: str = Field(description="Unique agent name")
    model: str = Field(description="Ollama model ID for this agent")
    description: str = Field(default="", description="Agent description")
    enable_tools: bool = Field(default=True, description="Enable tool usage")
    workspace_dir: str | None = Field(
        default=None,
        description="Custom workspace directory (None = use default)"
    )

    # Optional format override (if not set, auto-detected from model)
    harmony_format: HarmonyFormatConfig | None = None

    @field_validator("name")
    @classmethod
    def validate_name(cls, v: str) -> str:
        """Ensure name is valid identifier."""
        if not v or not v.strip():
            raise ValueError("Agent name cannot be empty")
        v = v.strip()
        if not v.replace("_", "").replace("-", "").isalnum():
            raise ValueError("Agent name must be alphanumeric (with _ or -)")
        return v


class OMEConfig(BaseModel):
    """Root configuration for Olympus Memory Engine.

    This is the top-level config loaded from config.yaml.
    """

    # Default model for new agents
    default_model: str = Field(
        default="llama3.1:8b",
        description="Default Ollama model for agents"
    )
    default_agent: str = Field(
        default="assistant",
        description="Default agent to route messages to"
    )

    # Memory configuration
    memory: MemoryConfig = Field(default_factory=MemoryConfig)

    # Embedding model (separate from LLM)
    embedding_model: str = Field(
        default="nomic-embed-text",
        description="Model for generating embeddings"
    )

    # Agent configurations
    agents: list[AgentConfig] = Field(
        default_factory=list,
        description="Pre-configured agents"
    )

    # Model registry (available models)
    models: list[OllamaModelConfig] = Field(
        default_factory=list,
        description="Available model configurations"
    )

    def get_agent_config(self, name: str) -> AgentConfig | None:
        """Get agent config by name."""
        for agent in self.agents:
            if agent.name == name:
                return agent
        return None

    def get_model_config(self, model_id: str) -> OllamaModelConfig | None:
        """Get model config by ID."""
        for model in self.models:
            if model.model_id == model_id:
                return model
        return None


def load_config(config_path: Path | str = Path("config.yaml")) -> OMEConfig:
    """Load and validate configuration from YAML file.

    Args:
        config_path: Path to config.yaml

    Returns:
        Validated OMEConfig instance

    Raises:
        FileNotFoundError: If config file doesn't exist
        pydantic.ValidationError: If config is invalid
    """
    if isinstance(config_path, str):
        config_path = Path(config_path)

    with open(config_path, "r", encoding="utf-8") as f:
        raw_config = yaml.safe_load(f)

    # Handle empty config file
    if raw_config is None:
        raw_config = {}

    # Handle legacy config format where agents is a list of dicts
    if "agents" in raw_config and isinstance(raw_config["agents"], list):
        agents = []
        for agent in raw_config["agents"]:
            if isinstance(agent, dict):
                agents.append(AgentConfig(**agent))
        raw_config["agents"] = agents

    # Remove external_actors if present (no longer used)
    raw_config.pop("external_actors", None)

    return OMEConfig(**raw_config)
