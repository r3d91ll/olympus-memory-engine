"""Integration tests for external actor system.

Tests the complete flow of external actor joining, agent interactions,
and context window updates.
"""

import pytest

from src.agents.agent_manager import AgentManager
from src.memory.memory_storage import MemoryStorage


@pytest.mark.integration
def test_external_actor_join_announcement(temp_db):
    """Test that all agents receive join announcement."""
    manager = AgentManager()
    storage = MemoryStorage()

    # Create internal agents
    manager.create_agent("alice", "llama3.1:8b", storage=storage)
    manager.create_agent("bob", "llama3.1:8b", storage=storage)

    # External actor joins
    manager.connect_external_actor(
        actor_id="todd",
        actor_type="human",
        description="human user, primary",
    )

    # Check alice's conversation history
    alice = manager.get_agent("alice")
    assert alice is not None

    alice_history = storage.get_conversation_history(alice.agent_id, limit=10)
    system_messages = [
        msg for msg in alice_history
        if msg["role"] == "system" and "todd" in msg["content"]
    ]
    assert len(system_messages) > 0
    assert "joined" in system_messages[0]["content"].lower()

    # Check bob's conversation history
    bob = manager.get_agent("bob")
    assert bob is not None

    bob_history = storage.get_conversation_history(bob.agent_id, limit=10)
    system_messages = [
        msg for msg in bob_history
        if msg["role"] == "system" and "todd" in msg["content"]
    ]
    assert len(system_messages) > 0
    assert "joined" in system_messages[0]["content"].lower()

    storage.close()


@pytest.mark.integration
def test_agent_context_includes_participants(temp_db):
    """Test that agent context window includes participant list."""
    manager = AgentManager()
    storage = MemoryStorage()

    # Connect external actor
    manager.connect_external_actor(
        actor_id="todd",
        actor_type="human",
        description="human user, primary",
    )

    # Create agent
    manager.create_agent("alice", "llama3.1:8b", storage=storage)
    alice = manager.get_agent("alice")

    assert alice is not None

    # Get context window
    context = alice.get_context_window()

    # Should mention external actors
    assert "CURRENT PARTICIPANTS" in context or "External:" in context
    assert "todd" in context

    # Should mention internal agents
    assert "INTERNAL" in context or "Internal:" in context
    assert "alice" in context

    storage.close()


@pytest.mark.integration
def test_agent_system_prompt_explains_participants(temp_db):
    """Test that agent system prompt explains internal vs external."""
    manager = AgentManager()
    storage = MemoryStorage()

    # Create agent
    manager.create_agent("alice", "llama3.1:8b", storage=storage)
    alice = manager.get_agent("alice")

    assert alice is not None

    # Check system memory includes participant explanation
    system_memory = alice.system_memory

    assert "EXTERNAL ACTORS" in system_memory
    assert "INTERNAL AGENTS" in system_memory
    assert "NEVER use message_agent" in system_memory or "DO NOT use message_agent" in system_memory
    assert "Respond DIRECTLY" in system_memory

    storage.close()


@pytest.mark.integration
def test_leave_announcement_broadcast(temp_db):
    """Test that leave announcement is broadcast to all agents."""
    manager = AgentManager()
    storage = MemoryStorage()

    # Create agents
    manager.create_agent("alice", "llama3.1:8b", storage=storage)
    manager.create_agent("bob", "llama3.1:8b", storage=storage)

    # External actor joins
    manager.connect_external_actor(
        actor_id="todd",
        actor_type="human",
        description="test user",
    )

    # Clear FIFO queues to isolate leave message
    alice = manager.get_agent("alice")
    bob = manager.get_agent("bob")
    assert alice is not None
    assert bob is not None

    alice.fifo_queue.clear()
    bob.fifo_queue.clear()

    # External actor leaves
    manager.disconnect_external_actor("todd")

    # Check both agents received leave message
    assert len(alice.fifo_queue) == 1
    assert "[SYSTEM]" in alice.fifo_queue[0]["content"]
    assert "todd" in alice.fifo_queue[0]["content"]
    assert "left" in alice.fifo_queue[0]["content"].lower()

    assert len(bob.fifo_queue) == 1
    assert "[SYSTEM]" in bob.fifo_queue[0]["content"]
    assert "todd" in bob.fifo_queue[0]["content"]
    assert "left" in bob.fifo_queue[0]["content"].lower()

    storage.close()


@pytest.mark.integration
def test_participant_list_in_every_context(temp_db):
    """Test that participant list appears in context for every message."""
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

    # Get context multiple times
    context1 = alice.get_context_window()
    context2 = alice.get_context_window()

    # Both should include participant list
    assert "todd" in context1
    assert "alice" in context1
    assert "todd" in context2
    assert "alice" in context2

    # Connect another external actor
    manager.connect_external_actor(
        actor_id="claude",
        actor_type="ai_assistant",
        description="AI assistant",
    )

    # Get context again
    context3 = alice.get_context_window()

    # Should now include both external actors
    assert "todd" in context3
    assert "claude" in context3
    assert "alice" in context3

    storage.close()
