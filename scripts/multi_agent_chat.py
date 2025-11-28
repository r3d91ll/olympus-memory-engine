#!/usr/bin/env python3
"""Multi-Agent Chat - Interactive terminal for multiple AI agents.

Loads pre-configured agents from config.yaml and provides a Slack-like
interface with @mention routing and persistent memory.
"""

import yaml
import sys
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.agents.agent_manager import AgentManager
from src.memory.memory_storage import MemoryStorage
from src.ui.shell import InteractiveShell
from src.ui.terminal_ui import TerminalUI


def load_config(config_path: Path = Path("config.yaml")) -> dict:
    """Load configuration from YAML file.

    Args:
        config_path: Path to config file

    Returns:
        Configuration dictionary
    """
    with open(config_path, "r") as f:
        return yaml.safe_load(f)


def main():
    """Main entry point for multi-agent chat."""
    print("=" * 70)
    print("Multi-Agent Chat - Starting up...")
    print("=" * 70)
    print()

    # Load configuration
    config = load_config()
    print(f"[Config] Loaded from config.yaml")

    # Create shared storage
    storage = MemoryStorage()
    print(f"[Storage] Connected to PostgreSQL")

    # Initialize components
    agent_manager = AgentManager()
    ui = TerminalUI()

    # Load or create agents from config
    agents_config = config.get("agents", [])
    if not agents_config:
        print("[Warning] No agents configured in config.yaml")
        print("[Info] You can create agents interactively with /create <name> <model>")
    else:
        print(f"[Agents] Loading {len(agents_config)} configured agents...")
        for agent_config in agents_config:
            name = agent_config["name"]
            model = agent_config["model"]

            try:
                # Try to register existing agent or create new one
                info = agent_manager.create_agent(
                    name=name,
                    model_id=model,
                    storage=storage,
                )
                print(f"  ✓ {name} ({model}) - {info.agent_id}")
            except ValueError:
                # Agent already exists (loaded from database)
                print(f"  ✓ {name} (already exists)")
            except Exception as e:
                print(f"  ✗ {name} - Error: {e}")

    print()
    print("=" * 70)
    print()

    # Start interactive shell
    try:
        shell = InteractiveShell(agent_manager=agent_manager, ui=ui)
        shell.start()
    except KeyboardInterrupt:
        print("\n\nInterrupted by user")
    finally:
        # Cleanup
        print("\n[Shutdown] Closing connections...")
        agent_manager.shutdown()
        storage.close()
        print("[Shutdown] Complete")


if __name__ == "__main__":
    main()
