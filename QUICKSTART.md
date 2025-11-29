# Quick Start Guide

Get up and running with the Olympus Memory Engine in 5 minutes.

## Prerequisites Check

```bash
# Check Python version (need 3.12+)
python3 --version

# Check PostgreSQL (need 14+)
psql --version

# Check Ollama
ollama --version
```

## Installation (5 Steps)

### 1. Install Dependencies

```bash
cd olympus-memory-engine
poetry install
```

### 2. Setup Database

```bash
# Create database
createdb olympus_memory

# Install pgvector extension
psql olympus_memory -c "CREATE EXTENSION IF NOT EXISTS vector;"

# Initialize schema
poetry run python scripts/init_database.py
```

### 3. Setup Ollama Models

```bash
ollama pull gpt-oss:20b
ollama pull nomic-embed-text
```

### 4. Run Interactive Chat

```bash
poetry run ome
```

You'll see:
```
╭──────────────────────────────────────────────────────╮
│               Olympus Memory Engine                  │
│ Agent: assistant | Model: gpt-oss:20b | Context: 32k│
╰──────────────────────────────────────────────────────╯
Connected to PostgreSQL
Agent ready (ID: 8ae88392-35fb-4256-b912-8b19cd788a63)

Type 'quit' or 'exit' to stop. Ctrl+C to interrupt.

You:
```

### 5. Try Some Commands

```
You: Remember that I prefer Python for scripting
assistant: ✓ Saved to archival memory: User prefers Python for scripting...
LLM: 234ms | 45.2 tok/s | save: 12ms | total: 312ms

You: What do you remember about me?
assistant: Found 1 memories:
1. User prefers Python for scripting (similarity: 0.892)
LLM: 198ms | 52.1 tok/s | search: 8ms | total: 245ms

You: Create a file called hello.py with a simple greeting
assistant: ✓ Created file: hello.py
LLM: 312ms | 38.4 tok/s | tools: 1x/15ms | total: 412ms

You: /stats
╭─────────────────────────────────╮
│          Agent Stats            │
│ Agent: assistant                │
│ Archival memories: 1            │
│ Conversation messages: 4        │
│ FIFO queue size: 4              │
│ Working memory: 256 chars       │
╰─────────────────────────────────╯
```

## CLI Options

```bash
# Use a different model
poetry run ome --model llama3.1:8b

# Custom agent name
poetry run ome --agent researcher

# Set workspace directory
poetry run ome --workspace ~/projects/myproject

# Larger context window (up to 128k)
poetry run ome --context 131072

# All options
poetry run ome --help
```

## Common Commands

```bash
# Run tests
poetry run pytest

# Type checking
poetry run mypy src --pretty

# Format code
poetry run ruff format src tests
```

## Troubleshooting

**"Connection refused" error:**
```bash
# Start PostgreSQL
sudo systemctl start postgresql
```

**"Model not found" error:**
```bash
# Pull models
ollama pull gpt-oss:20b
ollama pull nomic-embed-text
```

**Import errors:**
```bash
# Use poetry to run
poetry run ome
```

## Performance Metrics

Every response shows performance metrics:
```
LLM: 234ms | 45.2 tok/s | search: 8ms | save: 12ms | tools: 2x/45ms | total: 312ms
```

- **LLM**: Time for model inference
- **tok/s**: Tokens generated per second
- **search**: Memory search latency
- **save**: Memory save latency
- **tools**: Number of tool calls and total tool time
- **total**: End-to-end response time

## Next Steps

1. **Read the full README:** [README.md](README.md)
2. **Learn about the architecture:** Memory tiers, tool system, security
3. **Customize your agent:** Edit system prompts and working memory
