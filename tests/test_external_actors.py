"""Tests for external actor system.

Tests the ability to distinguish between internal agents (part of Olympus) and
external actors (users/systems outside Olympus).
"""

import pytest

from src.agents.agent_manager import AgentManager, ExternalActorInfo
from src.memory.memory_storage import MemoryStorage


def test_register_external_actor():
    """Test registering an external actor."""
    manager = AgentManager()

    actor_info = manager.connect_external_actor(
        actor_id="todd",
        actor_type="human",
        description="human user, primary",
    )

    assert isinstance(actor_info, ExternalActorInfo)
    assert actor_info.actor_id == "todd"
    assert actor_info.actor_type == "human"
    assert actor_info.description == "human user, primary"
    assert "todd" in manager.external_actors


def test_disconnect_external_actor():
    """Test disconnecting an external actor."""
    manager = AgentManager()

    # Connect actor
    manager.connect_external_actor(
        actor_id="todd",
        actor_type="human",
        description="test user",
    )

    assert "todd" in manager.external_actors

    # Disconnect actor
    result = manager.disconnect_external_actor("todd")

    assert result is True
    assert "todd" not in manager.external_actors

    # Try to disconnect again (should return False)
    result = manager.disconnect_external_actor("todd")
    assert result is False


def test_external_actor_name_collision_with_agent():
    """Test that external actor name cannot collide with internal agent."""
    manager = AgentManager()
    storage = MemoryStorage()

    # Create internal agent
    manager.create_agent("alice", "llama3.1:8b", storage=storage)

    # Try to connect external actor with same name
    with pytest.raises(ValueError, match="reserved for internal agent"):
        manager.connect_external_actor(
            actor_id="alice",
            actor_type="human",
            description="test",
        )

    storage.close()


def test_agent_name_collision_with_external_actor():
    """Test that internal agent name cannot collide with external actor."""
    manager = AgentManager()
    storage = MemoryStorage()

    # Connect external actor
    manager.connect_external_actor(
        actor_id="todd",
        actor_type="human",
        description="test user",
    )

    # Try to create agent with same name
    with pytest.raises(ValueError, match="already used by an external actor"):
        manager.create_agent("todd", "llama3.1:8b", storage=storage)

    storage.close()


def test_route_message_to_external_actor_rejected():
    """Test that routing to external actor raises error."""
    manager = AgentManager()

    # Connect external actor
    manager.connect_external_actor(
        actor_id="todd",
        actor_type="human",
        description="test user",
    )

    # Try to route message to external actor
    with pytest.raises(ValueError, match="Cannot route to external actor"):
        manager.route_message("todd", "hello")


def test_broadcast_system_message(temp_db):
    """Test broadcasting system message to all agents."""
    manager = AgentManager()
    storage = MemoryStorage()

    # Create two agents
    manager.create_agent("alice", "llama3.1:8b", storage=storage)
    manager.create_agent("bob", "llama3.1:8b", storage=storage)

    # Broadcast message
    manager.broadcast_system_message("todd has joined")

    # Verify both agents received message in FIFO
    alice = manager.get_agent("alice")
    bob = manager.get_agent("bob")

    assert alice is not None
    assert bob is not None

    # Check FIFO queues
    assert len(alice.fifo_queue) == 1
    assert "[SYSTEM]" in alice.fifo_queue[0]["content"]
    assert "todd" in alice.fifo_queue[0]["content"]

    assert len(bob.fifo_queue) == 1
    assert "[SYSTEM]" in bob.fifo_queue[0]["content"]
    assert "todd" in bob.fifo_queue[0]["content"]

    storage.close()


def test_participant_list_cache_invalidation():
    """Test that participant list cache updates on join/leave."""
    manager = AgentManager()
    storage = MemoryStorage()

    # Create agent
    manager.create_agent("alice", "llama3.1:8b", storage=storage)

    # Get initial participant list
    list1 = manager.get_participant_list()
    assert "alice" in list1
    assert "External Actors: None currently connected" in list1

    # Connect external actor
    manager.connect_external_actor(
        actor_id="todd",
        actor_type="human",
        description="test user",
    )

    # Get updated participant list
    list2 = manager.get_participant_list()
    assert "todd" in list2
    assert "alice" in list2
    assert "External Actors: None currently connected" not in list2

    # Disconnect external actor
    manager.disconnect_external_actor("todd")

    # Get updated participant list
    list3 = manager.get_participant_list()
    assert "todd" not in list3
    assert "alice" in list3

    storage.close()


def test_agent_message_external_actor_rejected():
    """Test that agent cannot message external actor."""
    manager = AgentManager()
    storage = MemoryStorage()

    # Connect external actor
    manager.connect_external_actor(
        actor_id="todd",
        actor_type="human",
        description="test user",
    )

    # Create agent
    manager.create_agent("alice", "llama3.1:8b", storage=storage)
    alice = manager.get_agent("alice")

    assert alice is not None

    # Try to message external actor
    result = alice.message_agent("todd", "Hello!")

    # Should get helpful error, not exception
    assert "ERROR" in result
    assert "external actor" in result.lower()
    assert "respond directly" in result.lower()

    storage.close()


def test_multiple_external_actors():
    """Test multiple external actors can be connected simultaneously."""
    manager = AgentManager()

    # Connect multiple external actors
    manager.connect_external_actor(
        actor_id="todd",
        actor_type="human",
        description="user 1",
    )
    manager.connect_external_actor(
        actor_id="claude",
        actor_type="ai_assistant",
        description="AI assistant",
    )

    assert len(manager.external_actors) == 2
    assert "todd" in manager.external_actors
    assert "claude" in manager.external_actors

    # Check participant list includes both
    participant_list = manager.get_participant_list()
    assert "todd" in participant_list
    assert "claude" in participant_list
