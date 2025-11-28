import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

#!/usr/bin/env python3
"""Simple test for agent collaboration."""

from src.agents.agent_manager import AgentManager
from src.memory.memory_storage import MemoryStorage
from src.ui.terminal_ui import TerminalUI


def main():
    print("=" * 70)
    print("Simple Agent Collaboration Test")
    print("=" * 70)
    print()

    storage = MemoryStorage()
    agent_manager = AgentManager()
    ui = TerminalUI()

    # Create two agents
    print("[Setup] Creating agents...")
    agent_manager.create_agent("alice", "llama3.1:8b", storage)
    agent_manager.create_agent("bob", "llama3.1:8b", storage)
    print()

    # Test 1: Direct command to test if message_agent works
    print("Test: Alice messages Bob directly")
    print("-" * 70)

    # Give alice a very explicit instruction
    message = """Please use the message_agent function to send this exact message to bob: "Hello Bob, can you respond with your name?"

Use this format exactly:
message_agent("bob", "Hello Bob, can you respond with your name?")
"""

    print("[User → Alice]")
    print(message)
    print()

    response, stats = agent_manager.route_message("alice", message)

    print("[Alice → User]")
    ui.print_agent_message("alice", response, stats)

    # Cleanup
    print()
    agent_manager.shutdown()
    storage.close()
    print("[✓] Test complete")


if __name__ == "__main__":
    main()
