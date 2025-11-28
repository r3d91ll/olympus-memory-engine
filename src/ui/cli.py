"""CLI entry point for Olympus Memory Engine.

This module provides the main CLI command accessible via:
    poetry run olympus
    poetry run olympus --identity todd

It wraps the multi-agent chat functionality from scripts/multi_agent_chat.py
with proper module structure.
"""

import argparse
import sys
from pathlib import Path

import yaml
from rich.console import Console
from rich.panel import Panel
from rich.prompt import Prompt

from src.agents.agent_manager import AgentManager, ExternalActorInfo
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


def prompt_for_identity(config: dict, console: Console) -> tuple[str, str, str]:
    """Prompt user to select their identity.

    Args:
        config: Configuration dictionary
        console: Rich console for output

    Returns:
        Tuple of (actor_id, actor_type, description)
    """
    external_actors_config = config.get("external_actors", [])

    # Build list of predefined actors
    predefined_actors = []
    if isinstance(external_actors_config, list):
        for actor in external_actors_config:
            if isinstance(actor, dict) and "actor_id" in actor:
                predefined_actors.append(actor)

    if not predefined_actors:
        # No predefined actors, prompt for name
        console.print("\n[yellow]No predefined external actors found in config.[/yellow]")
        actor_id = Prompt.ask("Enter your name/identifier")
        actor_type = "human"  # Default to human
        description = f"user ({actor_id})"
        return actor_id, actor_type, description

    # Show predefined options
    console.print("\n[bold cyan]Who are you?[/bold cyan]\n")
    for idx, actor in enumerate(predefined_actors, 1):
        console.print(
            f"  {idx}. [green]{actor['actor_id']}[/green] - {actor.get('description', 'N/A')}"
        )
    console.print(f"  {len(predefined_actors) + 1}. [yellow]Other (enter name)[/yellow]\n")

    # Get choice
    while True:
        try:
            choice = Prompt.ask("Enter choice", default="1")
            choice_num = int(choice)

            if 1 <= choice_num <= len(predefined_actors):
                # Selected predefined actor
                selected = predefined_actors[choice_num - 1]
                return (
                    selected["actor_id"],
                    selected.get("type", "human"),
                    selected.get("description", f"user ({selected['actor_id']})"),
                )
            elif choice_num == len(predefined_actors) + 1:
                # Enter custom name
                actor_id = Prompt.ask("Enter your name/identifier")
                actor_type = "human"
                description = f"user ({actor_id})"
                return actor_id, actor_type, description
            else:
                console.print(f"[red]Invalid choice. Please enter 1-{len(predefined_actors) + 1}[/red]")
        except ValueError:
            console.print("[red]Invalid input. Please enter a number.[/red]")
        except KeyboardInterrupt:
            console.print("\n[red]Cancelled[/red]")
            sys.exit(0)


def main() -> None:
    """Main entry point for Olympus Memory Engine CLI.

    This function:
    1. Loads configuration from config.yaml
    2. Prompts for external actor identity (or uses --identity flag)
    3. Initializes PostgreSQL storage backend
    4. Creates AgentManager and loads configured agents
    5. Connects external actor and broadcasts join announcement
    6. Starts interactive shell for multi-agent chat

    Example:
        $ poetry run olympus
        $ poetry run olympus --identity todd
        > @alice create a file called hello.txt
        > @bob read the hello.txt file
    """
    # Parse CLI arguments
    parser = argparse.ArgumentParser(
        description="Olympus Memory Engine - Multi-Agent Chat"
    )
    parser.add_argument(
        "--identity",
        type=str,
        help="External actor identity (skips prompt if provided)",
    )
    args = parser.parse_args()

    print("=" * 70)
    print("Olympus Memory Engine - Multi-Agent Chat")
    print("=" * 70)
    print()

    # Load configuration
    try:
        config = load_config()
        print(f"[Config] Loaded from config.yaml")
    except FileNotFoundError:
        print("[Error] config.yaml not found in current directory")
        print("[Info] Please run from project root or create config.yaml")
        sys.exit(1)
    except Exception as e:
        print(f"[Error] Failed to load config: {e}")
        sys.exit(1)

    # Create shared storage
    try:
        storage = MemoryStorage()
        print(f"[Storage] Connected to PostgreSQL")
    except Exception as e:
        print(f"[Error] Failed to connect to database: {e}")
        print("[Info] Ensure PostgreSQL is running and olympus_memory database exists")
        print("[Info] Run: poetry run python scripts/init_database.py")
        sys.exit(1)

    # Initialize components
    agent_manager = AgentManager()
    ui = TerminalUI()
    console = Console()

    # Determine external actor identity
    if args.identity:
        # Use identity from CLI flag
        actor_id = args.identity
        actor_type = "human"  # Default type
        description = f"user ({actor_id})"

        # Check if this identity is in config
        external_actors_config = config.get("external_actors", [])
        if isinstance(external_actors_config, list):
            for actor in external_actors_config:
                if isinstance(actor, dict) and actor.get("actor_id") == actor_id:
                    actor_type = actor.get("type", "human")
                    description = actor.get("description", description)
                    break

        print(f"[Identity] Using --identity flag: {actor_id}")
    else:
        # Prompt for identity
        actor_id, actor_type, description = prompt_for_identity(config, console)

    print()

    # Load or create agents from config
    agents_config = config.get("agents", [])
    if not agents_config:
        print("[Warning] No agents configured in config.yaml")
        print("[Info] Add agents to config.yaml under 'agents:' section")
    else:
        print(f"[Agents] Loading {len(agents_config)} configured agents...")
        for idx, agent_config in enumerate(agents_config):
            # Validate agent_config structure
            if not isinstance(agent_config, dict):
                print(
                    f"  ✗ Agent config at index {idx} is not a dict: {type(agent_config).__name__}"
                )
                continue

            name = agent_config.get("name")
            model = agent_config.get("model")

            # Validate required fields
            if not name or not isinstance(name, str) or not name.strip():
                print(
                    f"  ✗ Agent config at index {idx} missing or invalid 'name' field"
                )
                continue
            if not model or not isinstance(model, str) or not model.strip():
                print(
                    f"  ✗ Agent '{name}' at index {idx} missing or invalid 'model' field"
                )
                continue

            try:
                # Try to create new agent or register existing
                info = agent_manager.create_agent(
                    name=name,
                    model_id=model,
                    storage=storage,
                )
                print(f"  ✓ {name} ({model}) - {info.agent_id}")
            except ValueError:
                # Agent already exists in database
                print(f"  ✓ {name} (already exists)")
            except Exception as e:
                print(f"  ✗ {name} - Error: {e}")

    print()
    print("=" * 70)
    print()

    # Connect external actor and broadcast join announcement
    try:
        actor_info = agent_manager.connect_external_actor(
            actor_id=actor_id,
            actor_type=actor_type,
            description=description,
            connection_type="local_terminal",
        )
        # Display join announcement
        console.print(Panel(
            f"[SYSTEM] {actor_id} ({description}) has joined the conversation",
            style="bold green",
        ))
        print()
    except ValueError as e:
        print(f"[Error] Failed to connect as '{actor_id}': {e}")
        print("[Info] This name may be reserved for an internal agent")
        agent_manager.shutdown()
        storage.close()
        sys.exit(1)

    # Start interactive shell
    try:
        shell = InteractiveShell(agent_manager=agent_manager, ui=ui)
        shell.start()
    except KeyboardInterrupt:
        print("\n\n[Interrupted] Shutting down...")
    except Exception as e:
        print(f"\n[Error] Unexpected error: {e}")
        import traceback
        traceback.print_exc()
    finally:
        # Disconnect external actor and broadcast leave announcement
        if actor_id in agent_manager.external_actors:
            agent_manager.disconnect_external_actor(actor_id)
            console.print(Panel(
                f"[SYSTEM] {actor_id} has left the conversation",
                style="bold yellow",
            ))

        # Cleanup
        print("\n[Shutdown] Closing connections...")
        agent_manager.shutdown()
        storage.close()
        print("[Shutdown] Complete")


if __name__ == "__main__":
    main()
