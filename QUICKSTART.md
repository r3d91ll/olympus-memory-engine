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
cd ~/olympus/systems/memory-engine/prototype
pip3 install -r requirements.txt
```

### 2. Setup Database

```bash
# Create database
createdb olympus_memory

# Install pgvector extension
psql olympus_memory -c "CREATE EXTENSION IF NOT EXISTS vector;"

# Run schema
psql olympus_memory < sql/schema.sql
```

### 3. Setup Ollama Models

```bash
ollama pull llama3.1:8b
ollama pull qwen2.5-coder:latest
ollama pull nomic-embed-text
```

### 4. Configure Environment

```bash
export POSTGRES_USER=your_username
export POSTGRES_PASSWORD=your_password
```

### 5. Verify Installation

```bash
# Run infrastructure test
python3 tests/test_infrastructure.py

# Should see: "✓ All infrastructure tests passed!"
```

## First Run

### Option 1: Interactive Multi-Agent Chat

```bash
python3 scripts/multi_agent_chat.py
```

Then try:
```
> alice: tell bob to create a hello.txt file
> bob: read the hello.txt file
```

### Option 2: Bug Fixing Experiment

```bash
python3 scripts/run_bug_fixing_experiment.py
```

Watch Alice and Bob collaborate to fix bugs!

### Option 3: Python REPL

```python
from src.agents.agent_manager import AgentManager
from pathlib import Path

# Create manager and agents
manager = AgentManager(config_file=Path("config.yaml"))
manager.create_agent_from_config("alice")

# Chat
response, stats = manager.route_message("alice", "Hello! What can you do?")
print(response)
```

## Common Commands

```bash
# Run tests
pytest tests/test_*.py -v

# Check types
mypy src/

# Run experiment
python3 scripts/run_bug_fixing_experiment.py

# View logs
tail -f logs/agent_system_*.log

# View metrics
cat metrics/agent_metrics.prom
```

## Next Steps

1. **Read the full README:** [README.md](README.md)
2. **Learn about infrastructure:** [docs/infrastructure_guide.md](docs/infrastructure_guide.md)
3. **Design experiments:** [docs/bug_fixing_experiment.md](docs/bug_fixing_experiment.md)
4. **Modify config:** Edit `config.yaml` to add agents or experiments

## Troubleshooting

**"Connection refused" error:**
```bash
# Start PostgreSQL
sudo systemctl start postgresql
```

**"Model not found" error:**
```bash
# Pull models
ollama pull llama3.1:8b
ollama pull nomic-embed-text
```

**Import errors:**
```bash
# Ensure in correct directory
cd ~/olympus/systems/memory-engine/prototype

# Add to PYTHONPATH
export PYTHONPATH="${PYTHONPATH}:$(pwd)"
```

**Permission denied:**
```bash
# Check database user
psql -l

# Update environment variables
export POSTGRES_USER=your_username
export POSTGRES_PASSWORD=your_password
```

## Help

- Full documentation: [README.md](README.md)
- Testing guide: [docs/testing_guide.md](docs/testing_guide.md)
- Infrastructure guide: [docs/infrastructure_guide.md](docs/infrastructure_guide.md)
