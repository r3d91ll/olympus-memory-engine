#!/usr/bin/env python3
"""CLI entry point for Olympus Memory Engine.

This module provides a simple single-agent CLI:
    poetry run ome
    poetry run ome --agent alice --model gpt-oss:20b

The CLI starts a MemGPT-style agent with hierarchical memory and tool access.
"""

import argparse
import sys

from rich.console import Console
from rich.panel import Panel

from src.agents.memgpt_agent import MemGPTAgent
from src.memory.memory_storage import MemoryStorage


def main() -> None:
    """Main entry point for Olympus Memory Engine CLI.

    Starts a single MemGPT agent with:
    - Hierarchical memory (system, working, FIFO, archival)
    - PostgreSQL + pgvector storage
    - Tool access (files, commands, Python, web)

    Example:
        $ poetry run ome
        $ poetry run ome --agent alice --model llama3.1:8b
        You: Save that I prefer Python
        Agent: ✓ Saved to archival memory: User prefers Python...
    """
    parser = argparse.ArgumentParser(
        description="Olympus Memory Engine - Single Agent CLI"
    )
    parser.add_argument(
        "--agent", "-a",
        type=str,
        default="assistant",
        help="Agent name (default: assistant)",
    )
    parser.add_argument(
        "--model", "-m",
        type=str,
        default="gpt-oss:20b",
        help="Ollama model ID (default: gpt-oss:20b)",
    )
    parser.add_argument(
        "--workspace", "-w",
        type=str,
        default=None,
        help="Workspace directory for file operations",
    )
    parser.add_argument(
        "--context", "-c",
        type=int,
        default=32768,
        help="Context window size in tokens (default: 32768)",
    )
    args = parser.parse_args()

    console = Console()

    context_k = args.context // 1024
    console.print(Panel(
        "[bold cyan]Olympus Memory Engine[/bold cyan]\n"
        f"Agent: [green]{args.agent}[/green] | Model: [yellow]{args.model}[/yellow] | Context: [magenta]{context_k}k[/magenta]",
        title="OME",
        border_style="blue",
    ))

    # Initialize storage
    try:
        storage = MemoryStorage()
        console.print("[dim]Connected to PostgreSQL[/dim]")
    except Exception as e:
        console.print(f"[red]Failed to connect to database: {e}[/red]")
        console.print("[dim]Run: poetry run python scripts/init_database.py[/dim]")
        sys.exit(1)

    # Initialize agent
    try:
        agent = MemGPTAgent(
            name=args.agent,
            model_id=args.model,
            storage=storage,
            enable_tools=True,
            workspace=args.workspace,
            context_size=args.context,
        )
        console.print(f"[dim]Agent ready (ID: {agent.agent_id})[/dim]\n")
    except Exception as e:
        console.print(f"[red]Failed to initialize agent: {e}[/red]")
        storage.close()
        sys.exit(1)

    # Show stats if agent has memories
    stats = agent.get_stats()
    if stats["archival_memories"] > 0 or stats["conversation_messages"] > 0:
        console.print(f"[dim]Loaded {stats['archival_memories']} memories, "
                     f"{stats['conversation_messages']} conversation messages[/dim]\n")

    console.print("[dim]Type 'quit' or 'exit' to stop. Ctrl+C to interrupt.[/dim]\n")

    # Main chat loop
    try:
        while True:
            try:
                user_input = console.input("[bold green]You:[/bold green] ")
            except EOFError:
                break

            user_input = user_input.strip()
            if not user_input:
                continue

            if user_input.lower() in ("quit", "exit", "/quit", "/exit"):
                break

            # Special commands
            if user_input.lower() in ("/stats", "/status"):
                stats = agent.get_stats()
                console.print(Panel(
                    f"Agent: {stats['name']}\n"
                    f"Archival memories: {stats['archival_memories']}\n"
                    f"Conversation messages: {stats['conversation_messages']}\n"
                    f"FIFO queue size: {stats['fifo_size']}\n"
                    f"Working memory: {stats['working_memory_chars']} chars",
                    title="Agent Stats",
                    border_style="cyan",
                ))
                continue

            if user_input.lower() in ("/help", "/?"):
                console.print(Panel(
                    "[bold]Commands:[/bold]\n"
                    "  /stats  - Show agent statistics\n"
                    "  /help   - Show this help\n"
                    "  quit    - Exit the CLI\n\n"
                    "[bold]Memory Functions:[/bold]\n"
                    "  The agent can save and search memories automatically.\n"
                    "  Try: 'Remember that I like coffee'\n"
                    "  Or:  'What do you know about me?'\n\n"
                    "[bold]Tools:[/bold]\n"
                    "  File operations, Python execution, web fetch, etc.",
                    title="Help",
                    border_style="green",
                ))
                continue

            # Get response from agent
            try:
                response, metrics = agent.chat(user_input)
                console.print(f"\n[bold blue]{args.agent}:[/bold blue] {response}")
                console.print(f"[dim]{metrics.summary()}[/dim]\n")
            except KeyboardInterrupt:
                console.print("\n[yellow]Interrupted[/yellow]\n")
                continue
            except Exception as e:
                console.print(f"\n[red]Error: {e}[/red]\n")
                continue

    except KeyboardInterrupt:
        console.print("\n[yellow]Interrupted[/yellow]")

    # Cleanup
    console.print("\n[dim]Shutting down...[/dim]")

    # Stop Ollama model to free GPU memory
    if hasattr(agent, 'ollama') and agent.ollama is not None:
        agent.ollama.stop()
        console.print(f"[dim]Stopped model: {agent.ollama.model_id}[/dim]")

    storage.close()
    console.print("[dim]Goodbye![/dim]")


if __name__ == "__main__":
    main()
