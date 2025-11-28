#!/usr/bin/env python3
"""Test agent-to-agent communication."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.agents.agent_manager import AgentManager
from src.memory.memory_storage import MemoryStorage
from src.ui.terminal_ui import TerminalUI


def test_agent_to_agent():
    """Test agents messaging each other."""
    print("=" * 70)
    print("Testing Agent-to-Agent Communication")
    print("=" * 70)
    print()

    # Create storage and agent manager
    storage = MemoryStorage()
    agent_manager = AgentManager()
    ui = TerminalUI()

    print("[Setup] Creating agents...")

    # Create two agents
    info1 = agent_manager.create_agent(
        name="alice",
        model_id="llama3.1:8b",
        storage=storage,
    )
    print(f"  ✓ alice (ID: {info1.agent_id})")

    info2 = agent_manager.create_agent(
        name="bob",
        model_id="llama3.1:8b",
        storage=storage,
    )
    print(f"  ✓ bob (ID: {info2.agent_id})")

    print()
    print("=" * 70)
    print("Test 1: Alice asks Bob to create a file")
    print("=" * 70)
    print()

    # User asks alice to ask bob to create a file
    user_message = "Can you ask bob to create a simple hello.txt file with the text 'Hello from Bob!'?"

    print(f"[User → Alice]: {user_message}")
    print()

    response, stats = agent_manager.route_message("alice", user_message)

    print("[Alice → User]:")
    ui.print_agent_message("alice", response, stats)

    print()
    print("=" * 70)
    print("Test 2: Check if file was created")
    print("=" * 70)
    print()

    check_message = "Can you check if the hello.txt file exists and read its contents?"

    print(f"[User → Alice]: {check_message}")
    print()

    response, stats = agent_manager.route_message("alice", check_message)

    print("[Alice → User]:")
    ui.print_agent_message("alice", response, stats)

    print()
    print("=" * 70)
    print("Test 3: Bob confirms what he created")
    print("=" * 70)
    print()

    bob_message = "What files have you created?"

    print(f"[User → Bob]: {bob_message}")
    print()

    response, stats = agent_manager.route_message("bob", bob_message)

    print("[Bob → User]:")
    ui.print_agent_message("bob", response, stats)

    # Cleanup
    print()
    print("=" * 70)
    print("[Cleanup] Shutting down...")
    agent_manager.shutdown()
    storage.close()
    print("[✓] Test complete!")
    print("=" * 70)


if __name__ == "__main__":
    test_agent_to_agent()
