# Multi-Agent Chat System

A Slack-like interactive terminal for multiple AI agents with persistent memory, ported from the bilateral-experiment project.

## Features

- **Multiple Agents**: Create and manage multiple agents, each with isolated memory
- **@mention Routing**: Send messages to specific agents using `@agentname message`
- **Persistent Memory**: Each agent has hierarchical memory (System, Working, FIFO, Archival)
- **Rich Terminal UI**: Retro green-on-black terminal with ASCII borders
- **Agent Tools**: File manipulation and code execution capabilities
- **Model Persistence**: Agent-model associations are stored in PostgreSQL

## Quick Start

### 1. Prerequisites

Ensure you have:
- PostgreSQL running with `olympus_memory` database
- Ollama running locally
- Python 3.12+
- Required packages (rich, prompt-toolkit, psycopg, pgvector, ollama, pyyaml, numpy)

### 2. Run Non-Interactive Test

```bash
cd /home/todd/olympus/systems/memory-engine/prototype
python3 test_multi_agent.py
```

This will:
- Load configuration
- Create test agents
- Send a test message
- Display agent response and memory stats

### 3. Run Interactive Chat

```bash
python3 multi_agent_chat.py
```

This will:
- Load agents from `config.yaml`
- Start the interactive shell
- Display the Memory Engine banner

## Usage

### Commands

- `@<agent> <message>` - Send message to specific agent
  - Example: `@assistant what is python?`
  - Example: `@coder write a hello world script`

- `/agents` - List all active agents with stats

- `/memory <agent>` - Show memory statistics for an agent
  - Example: `/memory assistant`

- `/create <name> <model>` - Create a new agent
  - Example: `/create helper llama3.1:8b`

- `/help` - Show help message with all commands

- `/exit` or `/quit` - Exit the shell

### Example Session

```
╔══════════════════════════════════════════╗
║  MEMORY ENGINE v0.1.0                ║
║  Multi-Agent Terminal                ║
╚══════════════════════════════════════════╝

>>> @assistant Hello! What's your name?

╭─[ASSISTANT]─[Memories: 0]──────────────────╮
│ Hi! I'm assistant, a MemGPT agent with    │
│ hierarchical memory. I can help you with  │
│ various tasks!                             │
╰────────────────────────────────────────────╯

>>> @coder write a hello world in python

╭─[CODER]─[Memories: 0]──────────────────────╮
│ write_file('hello.py', 'print("Hello,     │
│ World!")')                                  │
│ ✓ Wrote 22 bytes to hello.py              │
╰────────────────────────────────────────────╯

>>> /agents

                  Active Agents
┏━━━━━━━━━━━┳━━━━━━━━━━━━━┳━━━━━━━━━━┳━━━━━━━━━━┓
┃ Name      ┃ Model       ┃ Messages ┃ Memories ┃
┡━━━━━━━━━━━╇━━━━━━━━━━━━━╇━━━━━━━━━━╇━━━━━━━━━━┩
│ assistant │ llama3.1:8b │        1 │        0 │
├───────────┼─────────────┼──────────┼──────────┤
│ coder     │ llama3.1:8b │        1 │        0 │
└───────────┴─────────────┴──────────┴──────────┘

>>> /exit
```

## Configuration

Edit `config.yaml` to customize:

```yaml
# Pre-configured agents (will be created on startup if they don't exist)
agents:
  - name: assistant
    model: llama3.1:8b
    description: General purpose assistant agent

  - name: coder
    model: qwen2.5-coder:latest
    description: Specialized coding agent

  - name: qwen
    model: qwen3:8b
    description: Qwen agent for reasoning tasks
```

## Architecture

### Components

- **`multi_agent_chat.py`** - Main entry point
- **`shell.py`** - Interactive shell with @mention parsing
- **`agent_manager.py`** - Multi-agent coordination
- **`terminal_ui.py`** - Rich-based retro terminal UI
- **`memgpt_agent.py`** - MemGPT agent with hierarchical memory
- **`memory_storage.py`** - PostgreSQL + pgvector backend
- **`tools.py`** - Agent filesystem and CLI tools

### Memory Hierarchy

Each agent has:

1. **System Memory**: Static instructions (read-only)
2. **Working Memory**: Editable facts about agent/conversation
3. **FIFO Queue**: Last 10 messages (in-memory)
4. **Archival Memory**: Long-term searchable storage (PostgreSQL + pgvector)

### Database Schema

- `agents` - Agent metadata (name, model_id, system/working memory)
- `memory_entries` - Archival memories with 768-dim embeddings
- `conversation_history` - Full conversation log
- `geometric_metrics` - Reserved for conveyance experiments

## Memory Persistence

- **Agent Configuration**: Model associations stored in PostgreSQL
- **Memories**: Embedded with nomic-embed-text (768-dim) and stored in pgvector
- **Conversations**: Full history persisted
- **Agent Reload**: When restarting, agents load their stored model and recent memories

## Agent Tools

Agents have access to filesystem operations:

- `read_file(path)` - Read file contents
- `write_file(path, content)` - Write to file
- `append_file(path, content)` - Append to file
- `list_files(path)` - List directory contents
- `delete_file(path)` - Delete file
- `run_python(code)` - Execute Python code
- `run_command(cmd)` - Run safe shell commands
- `get_workspace_info()` - Get workspace statistics

Workspace: `/home/todd/olympus/agent-workspace`

## Integration with Conveyance Experiments

This system is designed to support conveyance experiments from the bilateral-experiment project:

- Each agent has isolated memory space
- Agent interactions can be tracked
- Ready for geometric metrics integration (D_eff, β, R-score)
- Foundation for measuring information transfer between agents

## Troubleshooting

### PostgreSQL Connection Error

```bash
# Check PostgreSQL is running
systemctl status postgresql

# Test connection
psql -h /var/run/postgresql -U todd -d olympus_memory -c "SELECT version();"
```

### Ollama Connection Error

```bash
# Check Ollama is running
systemctl status ollama

# Test API
curl http://localhost:11434/api/tags
```

### Import Errors

```bash
# Install missing packages
pip3 install --break-system-packages rich prompt-toolkit psycopg pgvector ollama pyyaml numpy
```

## Differences from bilateral-experiment

1. **Simplified**: No MI_User system - agents are created directly
2. **No Metrics**: Geometric metrics (R, β, D_eff) not yet integrated
3. **Shared Storage**: Agents share a connection pool (not isolated databases)
4. **Tools Enabled**: All agents have CLI tools by default
5. **No API Keys**: No authentication system (local use only)

## Future Enhancements

- [ ] Add geometric metrics display (R, β, D_eff)
- [ ] Implement MI_User-style database isolation
- [ ] Add experiment session tracking
- [ ] Integrate with Conveyance Framework validation
- [ ] Add agent-to-agent communication
- [ ] Implement boundary object extraction
