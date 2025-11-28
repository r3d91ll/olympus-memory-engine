"""Terminal UI with professional retro aesthetic.

Rich-based styling for green-on-black terminal with ASCII box borders.
"""

from typing import Any

from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

# Professional retro color scheme
RETRO_GREEN = "bright_green"
RETRO_DIM = "green"
RETRO_ACCENT = "cyan"
RETRO_WARNING = "yellow"
RETRO_ERROR = "red"


class TerminalUI:
    """Professional retro terminal interface."""

    def __init__(self) -> None:
        """Initialize terminal UI with Rich console."""
        self.console = Console(color_system="256")

    def print_banner(self) -> None:
        """Display Memory Engine startup banner."""
        banner = Text()
        banner.append("╔══════════════════════════════════════════╗\n", style=RETRO_GREEN)
        banner.append("║  ", style=RETRO_GREEN)
        banner.append("MEMORY ENGINE", style=f"bold {RETRO_GREEN}")
        banner.append(" v0.1.0                ║\n", style=RETRO_GREEN)
        banner.append("║  ", style=RETRO_GREEN)
        banner.append("Multi-Agent Terminal", style=RETRO_DIM)
        banner.append("                ║\n", style=RETRO_GREEN)
        banner.append("╚══════════════════════════════════════════╝", style=RETRO_GREEN)

        self.console.print(banner)

    def print_agent_message(
        self, agent_name: str, message: str, metrics: dict[str, Any] | None = None
    ) -> None:
        """Display agent message with optional metrics.

        Args:
            agent_name: Name of agent
            message: Agent's response
            metrics: Optional dict with agent metrics
        """
        # Format header
        if metrics:
            header = f"[{agent_name.upper()}]"
            if "archival_memories" in metrics:
                header += f"─[Memories: {metrics['archival_memories']}]"
        else:
            header = f"[{agent_name.upper()}]"

        # Create panel with custom border
        panel = Panel(
            message,
            title=header,
            title_align="left",
            border_style=RETRO_GREEN,
            padding=(0, 1),
        )

        self.console.print(panel)
        self.console.print()

    def print_user_message(self, message: str) -> None:
        """Display user message.

        Args:
            message: User's input
        """
        text = Text()
        text.append(">>> ", style=f"bold {RETRO_ACCENT}")
        text.append(message, style="white")
        self.console.print(text)
        self.console.print()

    def print_system(self, message: str, level: str = "info") -> None:
        """Display system message.

        Args:
            message: System message
            level: Message level (info, warning, error)
        """
        style_map = {
            "info": RETRO_DIM,
            "warning": RETRO_WARNING,
            "error": RETRO_ERROR,
        }
        style = style_map.get(level, RETRO_DIM)

        text = Text()
        text.append("[SYSTEM] ", style=f"bold {style}")
        text.append(message, style=style)
        self.console.print(text)

    def print_agents_table(self, agents: list[dict[str, Any]]) -> None:
        """Display table of active agents.

        Args:
            agents: List of agent info dicts with keys: name, model_id, message_count
        """
        if not agents:
            self.print_system("No active agents", level="warning")
            return

        table = Table(title="Active Agents", border_style=RETRO_GREEN, show_lines=True)
        table.add_column("Name", style=RETRO_GREEN, no_wrap=True)
        table.add_column("Model", style=RETRO_DIM)
        table.add_column("Messages", justify="right", style="white")
        table.add_column("Memories", justify="right", style=RETRO_ACCENT)

        for agent in agents:
            table.add_row(
                agent["name"],
                agent["model_id"],
                str(agent.get("message_count", 0)),
                str(agent.get("archival_memories", 0)),
            )

        self.console.print(table)
        self.console.print()

    def print_memory_stats(self, agent_name: str, stats: dict[str, Any]) -> None:
        """Display memory statistics for an agent.

        Args:
            agent_name: Agent name
            stats: Memory statistics dict
        """
        panel_content = Text()
        panel_content.append("Agent ID: ", style=RETRO_DIM)
        panel_content.append(f"{stats.get('agent_id', 'N/A')}\n", style="white")
        panel_content.append("Model: ", style=RETRO_DIM)
        panel_content.append(f"{stats.get('model_id', 'N/A')}\n", style="white")
        panel_content.append("Working Memory: ", style=RETRO_DIM)
        panel_content.append(f"{stats.get('working_memory_chars', 0)} chars\n", style="white")
        panel_content.append("FIFO Queue: ", style=RETRO_DIM)
        panel_content.append(f"{stats.get('fifo_size', 0)} messages\n", style="white")
        panel_content.append("Archival: ", style=RETRO_DIM)
        panel_content.append(
            f"{stats.get('archival_memories', 0)} memories\n", style="white"
        )
        panel_content.append("Conversation: ", style=RETRO_DIM)
        panel_content.append(
            f"{stats.get('conversation_messages', 0)} messages", style="white"
        )

        panel = Panel(
            panel_content,
            title=f"[{agent_name.upper()}] Memory Stats",
            border_style=RETRO_GREEN,
            padding=(0, 1),
        )

        self.console.print(panel)
        self.console.print()

    def print_help(self) -> None:
        """Display help information for commands."""
        help_text = Text()
        help_text.append("Commands:\n", style=f"bold {RETRO_GREEN}")
        help_text.append("  @<agent> <message>  ", style=RETRO_ACCENT)
        help_text.append("- Send message to specific agent\n", style=RETRO_DIM)
        help_text.append("  /agents             ", style=RETRO_ACCENT)
        help_text.append("- List all active agents\n", style=RETRO_DIM)
        help_text.append("  /memory <agent>     ", style=RETRO_ACCENT)
        help_text.append("- Show memory stats for agent\n", style=RETRO_DIM)
        help_text.append("  /create <name> <model>  ", style=RETRO_ACCENT)
        help_text.append("- Create new agent\n", style=RETRO_DIM)
        help_text.append("  /help               ", style=RETRO_ACCENT)
        help_text.append("- Show this help message\n", style=RETRO_DIM)
        help_text.append("  /exit               ", style=RETRO_ACCENT)
        help_text.append("- Exit Memory Engine", style=RETRO_DIM)

        panel = Panel(
            help_text,
            title="Help",
            border_style=RETRO_GREEN,
            padding=(0, 1),
        )

        self.console.print(panel)
        self.console.print()

    def prompt(self, prompt_text: str = ">>> ") -> str:
        """Display prompt and get user input.

        Args:
            prompt_text: Prompt string

        Returns:
            User input string
        """
        styled_prompt = Text()
        styled_prompt.append(prompt_text, style=f"bold {RETRO_ACCENT}")
        self.console.print(styled_prompt, end="")
        return input()

    def clear(self) -> None:
        """Clear the terminal screen."""
        self.console.clear()
