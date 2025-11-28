#!/usr/bin/env python3
"""Test script for multi-agent chat system."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import yaml

from src.agents.agent_manager import AgentManager
from src.memory.memory_storage import MemoryStorage
from src.ui.terminal_ui import TerminalUI


def test_multi_agent():
    """Test multi-agent system without interactive shell."""
    print("=" * 70)
    print("Testing Multi-Agent System")
    print("=" * 70)
    print()

    # Load configuration
    with open("config.yaml") as f:
        config = yaml.safe_load(f)
    print("[✓] Config loaded")

    # Create storage
    storage = MemoryStorage()
    print("[✓] Storage connected")

    # Create agent manager
    agent_manager = AgentManager()
    print("[✓] Agent manager created")

    # Create UI (for display)
    ui = TerminalUI()
    print("[✓] Terminal UI initialized")
    print()

    # Create test agents
    print("Creating test agents...")
    try:
        # Create assistant agent
        info1 = agent_manager.create_agent(
            name="assistant",
            model_id="llama3.1:8b",
            storage=storage,
        )
        print(f"[✓] Created assistant (ID: {info1.agent_id})")

        # Create coder agent
        info2 = agent_manager.create_agent(
            name="coder",
            model_id="llama3.1:8b",  # Using same model for faster testing
            storage=storage,
        )
        print(f"[✓] Created coder (ID: {info2.agent_id})")

    except ValueError as e:
        print(f"[!] Agent already exists: {e}")
        print("[!] This is fine - agents were loaded from database")

    print()

    # List all agents
    print("Listing all agents:")
    agents = agent_manager.list_agents_dict()
    ui.print_agents_table(agents)

    # Test message routing
    print("Testing message routing...")
    test_message = "Hello! Can you tell me your name and what you do?"

    try:
        response, stats = agent_manager.route_message("assistant", test_message)
        print("[✓] Message routed to assistant")
        ui.print_agent_message("assistant", response, stats)

    except Exception as e:
        print(f"[✗] Error: {e}")
        import traceback
        traceback.print_exc()

    # Test memory stats
    print("Testing memory stats...")
    agent = agent_manager.get_agent("assistant")
    if agent:
        stats = agent.get_stats()
        stats["model_id"] = agent.model_id
        ui.print_memory_stats("assistant", stats)
    else:
        print("[✗] Could not get agent")

    # Cleanup
    print()
    print("=" * 70)
    print("Cleaning up...")
    agent_manager.shutdown()
    storage.close()
    print("[✓] Test complete!")
    print("=" * 70)


if __name__ == "__main__":
    test_multi_agent()
