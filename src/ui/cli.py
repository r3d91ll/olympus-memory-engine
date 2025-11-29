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

from rich.console import Console
from rich.panel import Panel
from rich.prompt import Prompt

from src.agents.agent_manager import AgentManager, ExternalActorInfo
from src.config import OMEConfig, load_config
from src.memory.memory_storage import MemoryStorage
from src.ui.shell import InteractiveShell
from src.ui.terminal_ui import TerminalUI


def prompt_for_identity(config: OMEConfig, console: Console) -> tuple[str, str, str]:
    """Prompt user to select their identity.

    Args:
        config: Typed OME configuration
        console: Rich console for output

    Returns:
        Tuple of (actor_id, actor_type, description)
    """
    predefined_actors = config.external_actors

    if not predefined_actors:
        # No predefined actors, prompt for name
        console.print("\n[yellow]No predefined external actors found in config.[/yellow]")
        actor_id = Prompt.ask("Enter your name/identifier")
        actor_type = "human"
        description = f"user ({actor_id})"
        return actor_id, actor_type, description

    # Show predefined options
    console.print("\n[bold cyan]Who are you?[/bold cyan]\n")
    for idx, actor in enumerate(predefined_actors, 1):
        desc = actor.description or "N/A"
        console.print(f"  {idx}. [green]{actor.actor_id}[/green] - {desc}")
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
                    selected.actor_id,
                    selected.actor_type,
                    selected.description or f"user ({selected.actor_id})",
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
        print("[Config] Loaded from config.yaml")
    except FileNotFoundError:
        print("[Error] config.yaml not found in current directory")
        print("[Info] Please run from project root or create config.yaml")
        sys.exit(1)
    except ValueError as e:
        # Pydantic validation error
        print(f"[Error] Invalid config: {e}")
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
        for actor in config.external_actors:
            if actor.actor_id == actor_id:
                actor_type = actor.actor_type
                description = actor.description or description
                break

        print(f"[Identity] Using --identity flag: {actor_id}")
    else:
        # Prompt for identity
        actor_id, actor_type, description = prompt_for_identity(config, console)

    print()

    # Load or create agents from config
    if not config.agents:
        print("[Warning] No agents configured in config.yaml")
        print("[Info] Add agents to config.yaml under 'agents:' section")
    else:
        print(f"[Agents] Loading {len(config.agents)} configured agents...")
        for agent_cfg in config.agents:
            try:
                # Try to create new agent or register existing
                info = agent_manager.create_agent(
                    name=agent_cfg.name,
                    model_id=agent_cfg.model,
                    storage=storage,
                )
                print(f"  ✓ {agent_cfg.name} ({agent_cfg.model}) - {info.agent_id}")
            except ValueError:
                # Agent already exists in database
                print(f"  ✓ {agent_cfg.name} (already exists)")
            except Exception as e:
                print(f"  ✗ {agent_cfg.name} - Error: {e}")

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

        # Stop Ollama models to free GPU memory
        print("[Shutdown] Stopping Ollama models...")
        stopped_models = set()
        for agent_name, agent in agent_manager._agents.items():
            if hasattr(agent, 'ollama') and agent.ollama is not None:
                model_id = agent.ollama.model_id
                if model_id not in stopped_models:
                    agent.ollama.stop()
                    stopped_models.add(model_id)
                    print(f"[Shutdown] Stopped model: {model_id}")

        agent_manager.shutdown()
        storage.close()
        print("[Shutdown] Complete")


if __name__ == "__main__":
    main()
