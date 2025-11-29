# Olympus Memory Engine - Simplification Plan

## Problem Statement

The repository has scope creep. It started as a memory storage engine but grew to include:
- Multi-agent orchestration (`AgentManager`, `@mention` routing)
- External actor connections (humans joining/leaving)
- Interactive multi-agent shell

This is **out of scope** for a memory engine library.

## What We Keep (Core Memory Engine)

### Memory Storage (`src/memory/`)
- `memory_storage.py` - PostgreSQL + pgvector backend
- `schema.sql` - Database schema
- `memory_manager.py` - FIFO queue, working memory management

### Single MemGPT Agent (`src/agents/`)
- `memgpt_agent.py` - **Simplified** (remove agent-to-agent messaging)
- Hierarchical memory (system, working, FIFO, archival)
- Tool execution for memory operations

### Tools (`src/tools/`)
- `tools.py` - File ops, commands, Python REPL, web fetch
- Essential for agents to interact with the world

### LLM Integration (`src/llm/`)
- `ollama_client.py` - Ollama inference
- `client.py`, `vllm_client.py` - Alternative backends

### Infrastructure (`src/infrastructure/`)
- `logging_config.py` - Structured logging
- `metrics.py` - Prometheus metrics

### Configuration (`src/config/`)
- `models.py` - Pydantic config models

### Scripts
- `scripts/init_database.py` - DB setup
- `scripts/export_traces.py` - SFT training data export

## What We Remove (Multi-Agent Orchestration)

### Delete Entirely
- `src/agents/agent_manager.py` - Multi-agent coordinator
- `src/ui/shell.py` - Multi-agent interactive shell
- `src/ui/terminal_ui.py` - Multi-agent terminal display

### Simplify
- `src/ui/cli.py` - Rewrite as single-agent CLI
- `src/agents/memgpt_agent.py` - Remove:
  - `message_agent()` function
  - `agent_manager` parameter
  - `_message_depth` recursion tracking
  - External actor awareness in system prompt

## New Single-Agent CLI

The simplified `cli.py` will:
1. Load config for a single agent (or use defaults)
2. Initialize MemGPTAgent with memory storage
3. Run a simple REPL loop:
   ```
   You: <user input>
   Agent: <response with tool use>
   ```
4. No @mentions, no routing, no multi-agent features

## Updated pyproject.toml

```toml
name = "olympus-memory-engine"
description = "MemGPT-style hierarchical memory for LLM agents"

[tool.poetry.scripts]
ome = "src.ui.cli:main"  # Simple single-agent CLI
```

## Implementation Steps

1. **Delete multi-agent files:**
   - `rm src/agents/agent_manager.py`
   - `rm src/ui/shell.py`
   - `rm src/ui/terminal_ui.py`

2. **Simplify memgpt_agent.py:**
   - Remove `agent_manager` parameter
   - Remove `message_agent()` method
   - Remove `_message_depth` tracking
   - Simplify system prompt (no external actor awareness)

3. **Rewrite cli.py:**
   - Single agent initialization
   - Simple input/output loop
   - Clean shutdown

4. **Update config:**
   - Simplify `config.yaml` (single agent)
   - Remove `external_actors` from Pydantic models

5. **Update tests:**
   - Remove multi-agent tests
   - Keep memory and tool tests

6. **Update pyproject.toml:**
   - Change name to `olympus-memory-engine`
   - Update description
   - Change script entry point

## Result

A focused library that provides:
- **MemGPT-style hierarchical memory** (system, working, FIFO, archival)
- **Semantic search** via PostgreSQL + pgvector
- **Tool execution** for file ops, commands, memory management
- **Single-agent CLI** for testing and demonstration
- **Clean API** for integration into other systems
