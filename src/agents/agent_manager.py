"""Multi-agent coordination and management.

Handles creation, routing, and lifecycle management of multiple agent instances.
Each agent = LLM + Memory System with isolated memory space.
"""

from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Optional
from uuid import UUID

from src.agents.memgpt_agent import MemGPTAgent
from src.infrastructure.config_manager import get_config, init_config
from src.infrastructure.logging_config import get_logger
from src.infrastructure.metrics import get_metrics
from src.memory.memory_storage import MemoryStorage


@dataclass
class AgentInfo:
    """Information about a registered agent."""

    agent_id: UUID
    name: str
    model_id: str
    created_at: str
    message_count: int = 0
    archival_memories: int = 0


@dataclass
class ExternalActorInfo:
    """Information about an external actor (user/system outside Olympus)."""

    actor_id: str
    actor_type: str  # "human", "ai_assistant", "external_agent", "other"
    display_name: str
    description: str
    connected_at: datetime
    connection_type: str = "local_terminal"
    metadata: dict[str, Any] | None = None


class AgentManager:
    """Manages multiple agent instances with isolated memory spaces."""

    def __init__(self, config_file: Optional[Path] = None) -> None:
        """Initialize agent manager.

        Args:
            config_file: Optional path to config.yaml file
        """
        self._agents: dict[str, MemGPTAgent] = {}  # name -> agent instance
        self._storage: MemoryStorage | None = None  # shared storage connection
        self._agent_info: dict[str, AgentInfo] = {}  # name -> agent info

        # External actor tracking (users/systems outside Olympus)
        self.external_actors: dict[str, ExternalActorInfo] = {}  # actor_id -> external actor info

        # Participant list caching (for context windows)
        self._participant_list_cache: Optional[str] = None
        self._cache_dirty: bool = True

        # Initialize infrastructure
        self.logger = get_logger("agent_manager")
        self.metrics = get_metrics()

        # Initialize config if provided
        if config_file:
            init_config(config_file)
        self.config = get_config()

        self.logger.info("Agent manager initialized")
        print("[AgentManager] Initialized")

    def create_agent(
        self,
        name: str,
        model_id: str,
        storage: MemoryStorage | None = None,
        workspace: str | None = None,
    ) -> AgentInfo:
        """Create a new agent.

        Args:
            name: Agent name
            model_id: Model identifier (e.g., "llama3.1:8b")
            storage: Optional shared storage instance
            workspace: Optional workspace directory for agent tools

        Returns:
            AgentInfo with agent details

        Raises:
            ValueError: If agent name already exists or collides with external actor
        """
        if name in self._agents:
            raise ValueError(f"Agent '{name}' already exists")

        # Check for collision with external actor names
        if name in self.external_actors:
            raise ValueError(
                f"Name '{name}' is already used by an external actor. "
                f"Please choose a different agent name."
            )

        # Use provided storage or create new one
        if storage is None and self._storage is None:
            self._storage = MemoryStorage()
            storage = self._storage
        elif storage is None:
            storage = self._storage

        # Create agent instance with reference to this manager
        agent = MemGPTAgent(
            name=name,
            model_id=model_id,
            storage=storage,
            enable_tools=True,
            agent_manager=self,
            workspace=workspace,
        )

        # Get agent stats
        stats = agent.get_stats()

        # Store agent info
        info = AgentInfo(
            agent_id=agent.agent_id,
            name=name,
            model_id=model_id,
            created_at=datetime.now().isoformat(),
            archival_memories=stats.get("archival_memories", 0),
        )

        self._agents[name] = agent
        self._agent_info[name] = info

        print(
            f"[AgentManager] Created agent: {name} "
            f"(model: {model_id}, id: {agent.agent_id})"
        )
        self.logger.info(f"Created agent: {name}", extra={
            'extra_data': {'model': model_id, 'agent_id': str(agent.agent_id)}
        })

        return info

    def create_agent_from_config(
        self,
        agent_name: str,
        storage: MemoryStorage | None = None,
    ) -> AgentInfo:
        """Create an agent from config file.

        Args:
            agent_name: Name of agent defined in config
            storage: Optional shared storage instance

        Returns:
            AgentInfo with agent details

        Raises:
            ValueError: If agent config not found or agent already exists
        """
        # Get agent config
        agent_config = self.config.get_agent_config(agent_name)
        if not agent_config:
            raise ValueError(f"No config found for agent '{agent_name}'. Check config.yaml.")

        # Create agent using config
        return self.create_agent(
            name=agent_config.name,
            model_id=agent_config.model,
            storage=storage,
        )

    def register_existing_agent(
        self, agent: MemGPTAgent
    ) -> AgentInfo:
        """Register an existing loaded agent.

        Args:
            agent: Loaded MemGPTAgent instance

        Returns:
            AgentInfo with agent details

        Raises:
            ValueError: If agent name already registered
        """
        if agent.name in self._agents:
            raise ValueError(f"Agent '{agent.name}' already registered")

        # Get agent stats
        stats = agent.get_stats()

        # Store agent info
        info = AgentInfo(
            agent_id=agent.agent_id,
            name=agent.name,
            model_id=agent.model_id,
            created_at=datetime.now().isoformat(),
            archival_memories=stats.get("archival_memories", 0),
        )

        self._agents[agent.name] = agent
        self._agent_info[agent.name] = info

        print(
            f"[AgentManager] Registered agent: {agent.name} "
            f"(model: {agent.model_id}, id: {agent.agent_id})"
        )

        return info

    def get_agent(self, name: str) -> MemGPTAgent | None:
        """Get agent instance by name.

        Args:
            name: Agent name

        Returns:
            Agent instance or None if not found
        """
        return self._agents.get(name)

    def get_agent_info(self, name: str) -> AgentInfo | None:
        """Get agent information by name.

        Args:
            name: Agent name

        Returns:
            AgentInfo or None if not found
        """
        return self._agent_info.get(name)

    def list_agents(self) -> list[AgentInfo]:
        """List all registered agents.

        Returns:
            List of AgentInfo objects
        """
        return list(self._agent_info.values())

    def list_agents_dict(self) -> list[dict[str, Any]]:
        """List all agents as dictionaries for UI display.

        Returns:
            List of agent info dicts
        """
        result = []
        for info in self._agent_info.values():
            # Get fresh stats
            agent = self._agents.get(info.name)
            if agent:
                stats = agent.get_stats()
                result.append({
                    "name": info.name,
                    "model_id": info.model_id,
                    "message_count": info.message_count,
                    "archival_memories": stats.get("archival_memories", 0),
                    "agent_id": str(info.agent_id),
                })
            else:
                result.append({
                    "name": info.name,
                    "model_id": info.model_id,
                    "message_count": info.message_count,
                    "archival_memories": info.archival_memories,
                    "agent_id": str(info.agent_id),
                })
        return result

    def delete_agent(self, name: str) -> bool:
        """Delete an agent (note: this does NOT delete agent's database records).

        Args:
            name: Agent name

        Returns:
            True if deleted, False if not found
        """
        if name not in self._agents:
            return False

        agent = self._agents[name]

        # Remove from internal tracking
        del self._agents[name]
        del self._agent_info[name]

        print(f"[AgentManager] Deleted agent: {name} (id: {agent.agent_id})")
        return True

    def route_message(self, agent_name: str, message: str, auto_create: bool = True) -> tuple[str, dict[str, Any]]:
        """Route message to specific agent and get response.

        Args:
            agent_name: Target agent name
            message: User message
            auto_create: If True, try to create agent on-demand if not found

        Returns:
            Tuple of (response_text, stats_dict)

        Raises:
            ValueError: If target is external actor or agent not found and auto_create is False
        """
        # Check if target is an external actor (cannot route to external actors)
        if agent_name in self.external_actors:
            raise ValueError(
                f"Cannot route to external actor '{agent_name}'. "
                f"External actors are outside the agent network. "
                f"Respond directly to them instead."
            )

        agent = self.get_agent(agent_name)

        # If agent not found, try to auto-create from existing DB record or config
        if not agent and auto_create:
            print(f"[AgentManager] Agent '{agent_name}' not in registry, attempting to load...")
            try:
                # First, try to create from config
                agent_config = self.config.get_agent_config(agent_name)
                if agent_config:
                    print(f"[AgentManager] Found config for '{agent_name}', creating from config...")
                    info = self.create_agent_from_config(
                        agent_name=agent_name,
                        storage=self._storage,
                    )
                    agent = self.get_agent(agent_name)
                    print(f"[AgentManager] Created agent '{agent_name}' from config")
                elif self._storage:
                    # Fall back to default model if no config found
                    print("[AgentManager] No config found, attempting to load from database...")
                    info = self.create_agent(
                        name=agent_name,
                        model_id="llama3.1:8b",  # fallback model
                        storage=self._storage,
                    )
                    agent = self.get_agent(agent_name)
                    print(f"[AgentManager] Loaded agent '{agent_name}' from database")
                else:
                    raise ValueError(f"No config or storage available for agent '{agent_name}'")
            except Exception as e:
                print(f"[AgentManager] Failed to auto-create agent '{agent_name}': {e}")
                self.logger.error(f"Failed to auto-create agent: {agent_name}", exc_info=True)
                raise ValueError(f"Agent '{agent_name}' not found and could not be created")

        if not agent:
            raise ValueError(f"Agent '{agent_name}' not found. Available agents: {list(self._agents.keys())}")

        # Process message through agent
        response = agent.chat(message)

        # Update message count
        if agent_name in self._agent_info:
            self._agent_info[agent_name].message_count += 1

        # Get fresh stats
        stats = agent.get_stats()

        print(
            f"[AgentManager] Routed message to {agent_name} "
            f"(message: {len(message)} chars, response: {len(response)} chars)"
        )

        return response, stats

    def connect_external_actor(
        self,
        actor_id: str,
        actor_type: str,
        description: str,
        connection_type: str = "local_terminal",
        metadata: dict[str, Any] | None = None,
    ) -> ExternalActorInfo:
        """Register an external actor (user/system outside Olympus).

        Args:
            actor_id: Unique identifier for the external actor
            actor_type: Type of actor ("human", "ai_assistant", "external_agent", "other")
            description: Human-readable description
            connection_type: How they're connecting (default: "local_terminal")
            metadata: Optional additional metadata

        Returns:
            ExternalActorInfo with actor details

        Raises:
            ValueError: If actor_id collides with internal agent name
        """
        # Check for collision with internal agent names
        if actor_id in self._agents:
            raise ValueError(
                f"Name '{actor_id}' is reserved for internal agent. "
                f"Please choose a different name."
            )

        # Create external actor info
        actor_info = ExternalActorInfo(
            actor_id=actor_id,
            actor_type=actor_type,
            display_name=actor_id,
            description=description,
            connected_at=datetime.now(),
            connection_type=connection_type,
            metadata=metadata,
        )

        self.external_actors[actor_id] = actor_info

        # Invalidate participant list cache
        self._invalidate_participant_cache()

        # Broadcast join announcement to all internal agents
        self.broadcast_system_message(
            f"{actor_id} ({description}) has joined the conversation"
        )

        self.logger.info(f"External actor connected: {actor_id}", extra={
            'extra_data': {'type': actor_type, 'description': description}
        })

        return actor_info

    def disconnect_external_actor(self, actor_id: str) -> bool:
        """Disconnect an external actor.

        Args:
            actor_id: External actor identifier

        Returns:
            True if disconnected, False if not found
        """
        if actor_id not in self.external_actors:
            return False

        actor_info = self.external_actors[actor_id]

        # Remove from tracking
        del self.external_actors[actor_id]

        # Invalidate participant list cache
        self._invalidate_participant_cache()

        # Broadcast leave announcement
        self.broadcast_system_message(
            f"{actor_id} has left the conversation"
        )

        self.logger.info(f"External actor disconnected: {actor_id}")

        return True

    def broadcast_system_message(self, message: str) -> None:
        """Broadcast a system message to all internal agents.

        System messages (e.g., join/leave announcements) are added to each
        agent's FIFO queue and conversation history for context.

        Args:
            message: System message content
        """
        system_msg = f"[SYSTEM] {message}"

        # Broadcast to all agents
        for agent_name, agent in self._agents.items():
            # Add to FIFO queue
            agent.fifo_queue.append({
                "role": "system",
                "content": system_msg
            })

            # Save to conversation history
            agent.storage.insert_conversation(
                agent_id=agent.agent_id,
                role="system",
                content=system_msg,
            )

        self.logger.info(f"Broadcast system message to {len(self._agents)} agents: {message}")

    def get_participant_list(self) -> str:
        """Get current participant list for agent context windows (cached).

        Returns:
            Formatted participant list string
        """
        if self._cache_dirty or self._participant_list_cache is None:
            self._participant_list_cache = self._build_participant_list()
            self._cache_dirty = False
        return self._participant_list_cache

    def _build_participant_list(self) -> str:
        """Build participant list string.

        Returns:
            Formatted string with external actors and internal agents
        """
        parts = ["=== CURRENT PARTICIPANTS ===", ""]

        # External actors
        if self.external_actors:
            parts.append("External Actors (outside Olympus):")
            for actor_id, actor_info in self.external_actors.items():
                parts.append(f"  - {actor_id} ({actor_info.description})")
            parts.append("")
        else:
            parts.append("External Actors: None currently connected")
            parts.append("")

        # Internal agents
        if self._agents:
            parts.append("Internal Agents (inside Olympus):")
            agent_names = ", ".join(self._agents.keys())
            parts.append(f"  {agent_names}")
        else:
            parts.append("Internal Agents: None")

        return "\n".join(parts)

    def _invalidate_participant_cache(self) -> None:
        """Mark participant list cache as needing refresh."""
        self._cache_dirty = True

    def shutdown(self) -> None:
        """Clean shutdown of all agents."""
        print(f"[AgentManager] Shutting down {len(self._agents)} agents")

        # Close storage connection
        if self._storage:
            self._storage.close()

        self._agents.clear()
        self._agent_info.clear()
