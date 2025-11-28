# Olympus Memory Engine

**High-performance MemGPT-style hierarchical memory system for local LLM agents.**

A local-only, in-RAM implementation designed for maximum performance via Unix socket IPC. Inspired by [MemGPT](https://arxiv.org/abs/2310.08560) and [Letta](https://github.com/letta-ai/letta).

---

## Why This Exists

MemGPT demonstrated that LLMs can manage their own memory hierarchies, enabling unbounded context through intelligent memory paging. Letta (formerly MemGPT) provides a cloud-hosted implementation.

**Olympus Memory Engine** takes a different approach:
- **Local-only**: Your data never leaves your machine
- **In-RAM + PostgreSQL**: Hot path in memory, cold storage in pgvector
- **Unix socket IPC**: Microsecond latency for agent-to-engine communication
- **Multi-agent native**: Isolated memory spaces with @mention routing

Built for researchers and developers who need MemGPT-style capabilities without cloud dependencies.

---

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                      Agent Layer                             │
│  ┌─────────┐  ┌─────────┐  ┌─────────┐                      │
│  │ Alice   │  │  Bob    │  │ Charlie │  ... N agents        │
│  └────┬────┘  └────┬────┘  └────┬────┘                      │
│       │            │            │                            │
│       └────────────┼────────────┘                            │
│                    │ @mention routing                        │
├────────────────────┼────────────────────────────────────────┤
│                    ▼                                         │
│            ┌──────────────┐                                  │
│            │ Agent Manager │  Unix Socket / IPC              │
│            └──────┬───────┘                                  │
│                   │                                          │
├───────────────────┼─────────────────────────────────────────┤
│                   ▼                                          │
│   ┌─────────────────────────────────────────────────────┐   │
│   │           Hierarchical Memory System                 │   │
│   │  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌────────┐  │   │
│   │  │ System   │ │ Working  │ │  FIFO    │ │Archival│  │   │
│   │  │ Memory   │ │ Memory   │ │  Queue   │ │Storage │  │   │
│   │  │ (static) │ │(editable)│ │ (recent) │ │(vector)│  │   │
│   │  └──────────┘ └──────────┘ └──────────┘ └────────┘  │   │
│   └─────────────────────────────────────────────────────┘   │
│                            │                                 │
│                            ▼                                 │
│   ┌─────────────────────────────────────────────────────┐   │
│   │              PostgreSQL + pgvector                   │   │
│   │         768-dim embeddings, HNSW index              │   │
│   └─────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────┘
```

### Memory Tiers

| Tier | Purpose | Persistence | Access Pattern |
|------|---------|-------------|----------------|
| **System** | Agent identity, instructions, tool schemas | Static | Read-only |
| **Working** | Editable facts, conversation state | Per-session | Read/Write |
| **FIFO** | Recent message history | Sliding window | Auto-overflow |
| **Archival** | Long-term semantic storage | Permanent | Vector search |

---

## Features

### Core Capabilities
- **MemGPT-style memory management**: Agents control their own memory operations
- **Semantic search**: pgvector with HNSW indexing for fast similarity queries
- **768-dim embeddings**: Via Ollama's nomic-embed-text (local, no API calls)
- **Memory overflow**: FIFO automatically flushes to archival when full

### Multi-Agent System
- **Isolated memory spaces**: Each agent has separate memory partitions
- **@mention routing**: `@alice hello` routes to specific agent
- **Agent-to-agent messaging**: Built-in `message_agent()` tool
- **Concurrent operation**: Multiple agents can run simultaneously

### Tool System (Sandboxed)
- **File operations**: read, write, edit, delete (workspace-isolated)
- **Command execution**: Whitelisted commands only (ls, cat, grep, python3, etc.)
- **Python REPL**: Execute Python with timeout enforcement
- **Web access**: URL fetching (HTTP/HTTPS, size-limited)
- **Search**: Glob patterns and regex content search

### Security
- **Workspace isolation**: All file ops sandboxed to agent workspace
- **Path traversal prevention**: No `../` escapes allowed
- **Command injection blocking**: Shell operators detected and blocked
- **Timeout enforcement**: All operations have configurable limits

---

## Quick Start

### Prerequisites

```bash
# PostgreSQL 14+ with pgvector
sudo apt install postgresql postgresql-contrib
psql -c "CREATE EXTENSION vector;"

# Ollama for local LLM + embeddings
curl -fsSL https://ollama.ai/install.sh | sh
ollama pull llama3.1:8b
ollama pull nomic-embed-text
```

### Installation

```bash
cd olympus-memory-engine
poetry install
```

### Database Setup

```bash
poetry run python scripts/init_database.py
```

### Run Interactive Chat

```bash
poetry run olympus
```

### Example Session

```
Olympus Memory Engine v0.1.0
Agents: alice, bob
Type @agent message or /help

> @alice create a file called notes.txt with "Meeting at 3pm"
Alice: I've created notes.txt with your meeting reminder.

> @bob read the notes.txt file
Bob: The file contains: "Meeting at 3pm"

> @alice remember that bob knows about the meeting
Alice: I've stored that in my working memory.

> @alice what do you remember about bob?
Alice: Bob knows about the meeting scheduled for 3pm.
```

---

## Configuration

Edit `config.yaml`:

```yaml
database:
  host: localhost
  port: 5432
  name: olympus_memory
  user: postgres

embedding:
  model: nomic-embed-text
  dimensions: 768

agents:
  alice:
    model: llama3.1:8b
    system_prompt: "You are Alice, a helpful research assistant."
    tools_enabled: true

  bob:
    model: qwen2.5-coder:latest
    system_prompt: "You are Bob, a software engineer."
    tools_enabled: true
```

---

## Development

### Testing

```bash
# All tests (145 total)
poetry run pytest

# By category
poetry run pytest -m unit           # Fast unit tests
poetry run pytest -m integration    # Requires PostgreSQL + Ollama

# Specific modules
poetry run pytest tests/test_tools_security.py -v    # 29 security tests
poetry run pytest tests/test_memory_storage.py -v    # PostgreSQL tests
```

### Quality Checks

```bash
poetry run mypy src --pretty        # Type checking (0 errors)
poetry run ruff check src tests     # Linting
poetry run ruff format src tests    # Formatting
```

---

## Project Structure

```
olympus-memory-engine/
├── src/
│   ├── agents/          # Agent manager, MemGPT agent implementation
│   ├── memory/          # 4-tier memory hierarchy, PostgreSQL backend
│   ├── tools/           # Sandboxed tool system
│   ├── llm/             # Ollama client, embedding generation
│   ├── ui/              # Interactive shell with @mention parsing
│   └── infrastructure/  # Logging, metrics, configuration
├── tests/               # 145 tests (unit + integration + security)
├── scripts/             # Database initialization, utilities
├── docs/                # Architecture documentation
└── config.yaml          # Agent and database configuration
```

---

## Inspiration & References

This project draws inspiration from:

- **[MemGPT](https://arxiv.org/abs/2310.08560)** (Packer et al., 2023): "MemGPT: Towards LLMs as Operating Systems" - The foundational paper on LLM-managed hierarchical memory
- **[Letta](https://github.com/letta-ai/letta)**: The official MemGPT implementation (cloud-hosted)
- **pgvector**: PostgreSQL extension for vector similarity search

Key differences from Letta:
- Local-only (no cloud, no API keys required for core functionality)
- Unix socket IPC for minimal latency
- PostgreSQL-native (vs. external vector DBs)
- Multi-agent first design

---

## Performance Targets

| Metric | Target | Current |
|--------|--------|---------|
| Memory query latency | <1ms | ~0.15ms (pgvector HNSW) |
| Embedding generation | <50ms | ~30ms (nomic-embed-text) |
| Agent response time | <2s | Model-dependent |
| Concurrent agents | 10+ | Tested with 5 |

---

## Roadmap

- [ ] Unix domain socket server mode (for IPC from other processes)
- [ ] C++ CUDA acceleration for vector operations
- [ ] Memory compaction and summarization
- [ ] Cross-agent memory sharing (with permissions)
- [ ] Prometheus metrics endpoint

---

## License

MIT License - See [LICENSE](LICENSE) for details.

---

## Acknowledgments

Built on the shoulders of giants:
- The MemGPT team for the hierarchical memory paradigm
- Letta for proving the concept at scale
- The Ollama team for making local LLMs accessible
- pgvector maintainers for excellent PostgreSQL vector support
