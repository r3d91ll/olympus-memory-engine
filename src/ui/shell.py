"""Interactive shell with command routing and @ mention parsing.

Uses prompt_toolkit for advanced readline capabilities.
"""

import re

from prompt_toolkit import PromptSession
from prompt_toolkit.formatted_text import HTML
from prompt_toolkit.history import InMemoryHistory
from prompt_toolkit.styles import Style

from src.agents.agent_manager import AgentManager
from src.ui.terminal_ui import TerminalUI

# Prompt styling
PROMPT_STYLE = Style.from_dict(
    {
        "prompt": "#00ff00 bold",  # Bright green
    }
)


class InteractiveShell:
    """Interactive shell for multi-agent conversations."""

    def __init__(self, agent_manager: AgentManager, ui: TerminalUI) -> None:
        """Initialize interactive shell.

        Args:
            agent_manager: Agent manager instance
            ui: Terminal UI instance
        """
        self.agent_manager = agent_manager
        self.ui = ui
        self.session: PromptSession[str] = PromptSession(
            history=InMemoryHistory(),
            style=PROMPT_STYLE,
        )
        self.running = False

    def start(self) -> None:
        """Start interactive shell loop."""
        self.ui.print_banner()
        self.ui.print_system("Type /help for commands or @<agent> to message an agent")
        self.ui.print_system("Type /exit to quit")
        self.ui.console.print()

        self.running = True

        while self.running:
            try:
                # Get user input with styled prompt
                user_input = self.session.prompt(HTML("<prompt>>>> </prompt>"))

                if not user_input.strip():
                    continue

                # Parse and execute command
                self._handle_input(user_input.strip())

            except KeyboardInterrupt:
                # Ctrl+C - cancel current line
                continue
            except EOFError:
                # Ctrl+D - exit
                self.running = False
                self.ui.print_system("Shutting down...")
            except Exception as e:
                self.ui.print_system(f"Error: {e}", level="error")

    def _handle_input(self, user_input: str) -> None:
        """Parse and handle user input.

        Args:
            user_input: User's input string
        """
        # Check for slash commands
        if user_input.startswith("/"):
            self._handle_slash_command(user_input)
            return

        # Check for @ mentions
        mention_match = re.match(r"^@(\w+)\s+(.+)$", user_input)
        if mention_match:
            agent_name = mention_match.group(1)
            message = mention_match.group(2)
            self._handle_agent_message(agent_name, message)
            return

        # No valid command format
        self.ui.print_system(
            "Invalid format. Use @<agent> <message> or /command", level="warning"
        )

    def _handle_slash_command(self, command: str) -> None:
        """Handle slash commands.

        Args:
            command: Command string starting with /
        """
        parts = command[1:].split(maxsplit=1)
        cmd = parts[0].lower()
        args = parts[1] if len(parts) > 1 else ""

        if cmd == "exit" or cmd == "quit":
            self.running = False
            self.ui.print_system("Shutting down...")

        elif cmd == "help":
            self.ui.print_help()

        elif cmd == "agents":
            agents = self.agent_manager.list_agents_dict()
            self.ui.print_agents_table(agents)

        elif cmd == "memory":
            if not args:
                self.ui.print_system("Usage: /memory <agent_name>", level="warning")
                return
            self._show_memory_stats(args.strip())

        elif cmd == "create":
            if not args:
                self.ui.print_system(
                    "Usage: /create <agent_name> <model_id>", level="warning"
                )
                return
            self._create_agent(args.strip())

        else:
            self.ui.print_system(f"Unknown command: /{cmd}", level="warning")
            self.ui.print_system("Type /help for available commands")

    def _handle_agent_message(self, agent_name: str, message: str) -> None:
        """Route message to specific agent and display response.

        Args:
            agent_name: Target agent name
            message: User message
        """
        try:
            # Route to agent
            response, stats = self.agent_manager.route_message(agent_name, message)

            # Display agent response with stats
            self.ui.print_agent_message(agent_name, response, stats)

        except ValueError as e:
            self.ui.print_system(str(e), level="error")
            self.ui.print_system("Use /agents to see available agents")

    def _show_memory_stats(self, agent_name: str) -> None:
        """Display memory statistics for an agent.

        Args:
            agent_name: Agent name
        """
        agent = self.agent_manager.get_agent(agent_name)
        if not agent:
            self.ui.print_system(f"Agent '{agent_name}' not found", level="error")
            return

        # Get memory stats from agent
        stats = agent.get_stats()
        stats["model_id"] = agent.model_id  # Add model_id for display
        self.ui.print_memory_stats(agent_name, stats)

    def _create_agent(self, args: str) -> None:
        """Create a new agent.

        Args:
            args: Arguments string with format "<name> <model_id>"
        """
        parts = args.split(maxsplit=1)
        if len(parts) != 2:
            self.ui.print_system(
                "Usage: /create <agent_name> <model_id>", level="warning"
            )
            return

        name, model_id = parts

        try:
            info = self.agent_manager.create_agent(name, model_id)
            self.ui.print_system(
                f"Created agent '{name}' with model {model_id} (ID: {info.agent_id})"
            )
        except ValueError as e:
            self.ui.print_system(str(e), level="error")
        except Exception as e:
            self.ui.print_system(f"Error creating agent: {e}", level="error")
