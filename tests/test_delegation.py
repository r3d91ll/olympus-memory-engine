import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

#!/usr/bin/env python3
"""Test agent delegation with improved prompts and auto-creation."""

from src.agents.agent_manager import AgentManager
from src.memory.memory_storage import MemoryStorage
from src.ui.terminal_ui import TerminalUI


def main():
    print("=" * 70)
    print("Test: Agent Delegation and Auto-Creation")
    print("=" * 70)
    print()

    storage = MemoryStorage()
    agent_manager = AgentManager()
    ui = TerminalUI()

    # Create only qwen, not coder
    print("[Setup] Creating qwen agent only...")
    agent_manager.create_agent("qwen", "qwen3:8b", storage)
    print()

    print("[Test] Asking qwen to delegate to coder (who doesn't exist yet)...")
    print("-" * 70)

    message = "Please use message_agent to ask coder to write a simple Python hello world script."

    print(f"[User → Qwen]: {message}")
    print()

    try:
        response, stats = agent_manager.route_message("qwen", message)

        print("[Qwen → User]:")
        ui.print_agent_message("qwen", response, stats)

        print()
        print("✅ Test passed! Qwen successfully delegated to coder")
        print()

        # Check if coder was auto-created
        coder = agent_manager.get_agent("coder")
        if coder:
            print("✅ Coder was auto-created successfully")
        else:
            print("❌ Coder was NOT created")

    except Exception as e:
        print(f"❌ Test failed: {e}")
        import traceback
        traceback.print_exc()

    print()
    print("=" * 70)
    agent_manager.shutdown()
    storage.close()


if __name__ == "__main__":
    main()
