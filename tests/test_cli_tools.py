import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

#!/usr/bin/env python3
"""
Quick test to demonstrate agent CLI capabilities
"""

from src.agents.agent_manager import AgentManager
from src.memory.memory_storage import MemoryStorage


def main():
    print("=" * 70)
    print("Agent CLI Tools Demonstration")
    print("=" * 70)
    print()

    storage = MemoryStorage()
    agent_manager = AgentManager()

    # Create a coding agent
    print("[Setup] Creating 'coder' agent...")
    agent_manager.create_agent("coder", "llama3.1:8b", storage)
    print()

    # Test 1: Create a Python script
    print("Test 1: Ask agent to create a Python script")
    print("-" * 70)
    message = "Create a file called hello.py that prints 'Hello from agent CLI!'"
    print(f"User → coder: {message}")
    response, _ = agent_manager.route_message("coder", message)
    print(f"coder → User: {response}")
    print()

    # Test 2: List workspace files
    print("Test 2: Ask agent to list files")
    print("-" * 70)
    message = "Show me what files are in the workspace"
    print(f"User → coder: {message}")
    response, _ = agent_manager.route_message("coder", message)
    print(f"coder → User: {response}")
    print()

    # Test 3: Run Python code
    print("Test 3: Ask agent to run Python code")
    print("-" * 70)
    message = "Run this Python code: print('2 + 2 =', 2 + 2)"
    print(f"User → coder: {message}")
    response, _ = agent_manager.route_message("coder", message)
    print(f"coder → User: {response}")
    print()

    # Test 4: Get workspace info
    print("Test 4: Ask agent for workspace statistics")
    print("-" * 70)
    message = "Tell me about the workspace"
    print(f"User → coder: {message}")
    response, _ = agent_manager.route_message("coder", message)
    print(f"coder → User: {response}")
    print()

    # Cleanup
    agent_manager.shutdown()
    storage.close()
    print("[✓] CLI tools test complete")


if __name__ == "__main__":
    main()
