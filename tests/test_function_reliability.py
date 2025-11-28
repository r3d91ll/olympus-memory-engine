import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

#!/usr/bin/env python3
"""Test function calling reliability improvements."""

from src.agents.agent_manager import AgentManager
from src.memory.memory_storage import MemoryStorage


def test_message_agent():
    """Test agent-to-agent messaging with hint-engineering."""
    print("=" * 70)
    print("Test: Function Calling Reliability")
    print("=" * 70)
    print()

    storage = MemoryStorage()
    agent_manager = AgentManager()

    # Create agents
    print("[Setup] Creating agents...")
    agent_manager.create_agent("alice", "llama3.1:8b", storage)
    agent_manager.create_agent("bob", "llama3.1:8b", storage)
    print()

    # Test 1: Simple agent messaging
    print("Test 1: Alice tells Bob hello")
    print("-" * 70)
    message = "Tell bob hello"
    print(f"User → alice: {message}")

    response, stats = agent_manager.route_message("alice", message)
    print(f"alice → User: {response}")
    print()

    # Test 2: Memory save
    print("Test 2: Save to memory")
    print("-" * 70)
    message = "Remember that I prefer Python programming"
    print(f"User → alice: {message}")

    response, stats = agent_manager.route_message("alice", message)
    print(f"alice → User: {response}")
    print()

    # Test 3: Memory search
    print("Test 3: Search memory")
    print("-" * 70)
    message = "What do you remember about my preferences?"
    print(f"User → alice: {message}")

    response, stats = agent_manager.route_message("alice", message)
    print(f"alice → User: {response}")
    print()

    # Cleanup
    agent_manager.shutdown()
    storage.close()
    print("[✓] All tests complete")


def test_context_bleeding():
    """Test that context bleeding is resolved."""
    print("\n" + "=" * 70)
    print("Test: Context Bleeding Resolution")
    print("=" * 70)
    print()

    storage = MemoryStorage()
    agent_manager = AgentManager()

    # Create agents
    print("[Setup] Creating agents...")
    agent_manager.create_agent("alice", "llama3.1:8b", storage)
    agent_manager.create_agent("bob", "llama3.1:8b", storage)
    print()

    # Test: Check that Bob's response is clean
    print("Test: Bob's response should not contain context markers")
    print("-" * 70)
    message = "Ask bob what his name is"
    print(f"User → alice: {message}")

    response, stats = agent_manager.route_message("alice", message)
    print(f"alice → User: {response}")
    print()

    # Check for context bleeding
    has_bleeding = any(marker in response for marker in [
        '=== SYSTEM MEMORY ===',
        '=== WORKING MEMORY ===',
        '=== RECENT CONVERSATION ==='
    ])

    if has_bleeding:
        print("❌ FAILED: Context bleeding detected")
    else:
        print("✅ PASSED: No context bleeding")
    print()

    # Cleanup
    agent_manager.shutdown()
    storage.close()


if __name__ == "__main__":
    test_message_agent()
    test_context_bleeding()
