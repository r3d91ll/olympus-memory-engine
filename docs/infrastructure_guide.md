# Infrastructure Guide

## Overview

The Olympus Memory Engine includes a comprehensive infrastructure stack for logging, metrics collection, and configuration management. This makes experiments easier to run, track, and reproduce.

## Components

### 1. Centralized Logging (`src/infrastructure/logging_config.py`)

Provides structured logging with agent context tracking, multiple output formats, and experiment session management.

**Features:**
- Agent-specific loggers with context tracking
- Console, file, and JSON output formats
- Automatic session IDs for experiment runs
- Thread-safe context management
- Rotating file handlers (10MB max, 5 backups)

**Usage:**

```python
from src.infrastructure.logging_config import init_logging, get_logger, set_context

# Initialize logging system
log_manager = init_logging(
    log_dir=Path("logs"),
    console_level=logging.INFO,
    file_level=logging.DEBUG,
    json_logging=True
)

# Get a logger
logger = get_logger("my_module")
logger.info("This is a log message")

# Set context for current thread
set_context(agent_name="alice", experiment_id="exp_001")

# Log agent actions
log_manager.log_agent_action(
    agent_name="alice",
    action="solving_bug",
    details={"bug_id": "bug_001", "difficulty": "hard"}
)

# Log function calls
log_manager.log_function_call(
    agent_name="alice",
    function_name="edit_file",
    arguments={"path": "main.py", "old_string": "bug", "new_string": "fix"},
    result="File edited successfully"
)

# Log agent-to-agent messages
log_manager.log_agent_message(
    sender="alice",
    recipient="bob",
    message="Please review this fix"
)
```

**Output Locations:**
- Console: stdout (human-readable)
- File: `logs/agent_system_YYYYMMDD_HHMMSS.log` (detailed, rotating)
- JSON: `logs/agent_system_YYYYMMDD_HHMMSS.jsonl` (for log aggregation)

### 2. Prometheus Metrics (`src/infrastructure/metrics.py`)

Collects metrics for agent behavior, LLM usage, and experiment outcomes using Prometheus format.

**Metrics Collected:**
- `agent_messages_sent_total`: Messages between agents
- `agent_function_calls_total`: Function calls by success/failure
- `agent_function_duration_seconds`: Function execution time
- `agent_memory_operations_total`: Memory saves/searches/updates
- `agent_llm_requests_total`: LLM inference requests
- `agent_llm_latency_seconds`: LLM response time
- `agent_tool_calls_total`: Tool usage by agents
- `experiments_run_total`: Number of experiments run
- `experiment_duration_seconds`: Experiment completion time
- `agents_active`: Current number of active agents

**Usage:**

```python
from src.infrastructure.metrics import init_metrics, get_metrics

# Initialize metrics
metrics = init_metrics(metrics_dir=Path("metrics"))

# Record agent message
metrics.record_message(sender="alice", recipient="bob")

# Record function call
metrics.record_function_call(
    agent="alice",
    function="edit_file",
    success=True,
    duration=0.5  # seconds
)

# Record memory operation
metrics.record_memory_operation(
    agent="alice",
    operation="search",
    results=5  # number of results
)

# Record LLM request
metrics.record_llm_request(
    agent="alice",
    model="llama3.1:8b",
    latency=1.5,  # seconds
    input_tokens=100,
    output_tokens=50
)

# Track experiment
start_time = metrics.start_experiment("bug_fixing")
# ... run experiment ...
metrics.end_experiment("bug_fixing", start_time, success=True)

# Export metrics to file (for Prometheus node-exporter)
metrics.export_to_file()  # Creates metrics/agent_metrics.prom
```

**Integration with Monitoring Stack:**

The metrics can be integrated with the existing Olympus monitoring infrastructure at `/home/todd/olympus/infrastructure/monitoring/ladon/`:

1. Export metrics to file: `metrics/agent_metrics.prom`
2. Configure Prometheus node-exporter to read from this directory
3. Metrics will appear in Grafana dashboards

### 3. Configuration Management (`src/infrastructure/config_manager.py`)

YAML-based configuration for agents, experiments, and system settings.

**Configuration Structure:**

```yaml
# config.yaml

# System settings
system:
  log_level: INFO
  log_dir: logs
  metrics_dir: metrics
  output_dir: output

# Database
database:
  host: localhost
  port: 5432
  database: olympus_memory

# Monitoring
monitoring:
  prometheus_enabled: true
  metrics_export_interval: 60
  export_to_file: true

# Available models
models:
  - id: llama3.1:8b
    name: Llama 3.1 8B
    description: General purpose model

# Agent definitions
agents:
  - name: alice
    model: llama3.1:8b
    description: Collaborative agent
    enable_tools: true

  - name: bob
    model: llama3.1:8b
    description: Collaborative agent
    enable_tools: true

# Experiment templates
experiments:
  - name: collaborative_bug_fixing
    type: bug_fixing
    description: Two agents collaborate to fix bugs
    agents:
      - alice
      - bob
    parameters:
      max_iterations: 10
      require_tests: true
    metrics:
      - function_calls_per_agent
      - messages_exchanged
      - time_to_solution
    validation:
      require_passing_tests: true
```

**Usage:**

```python
from src.infrastructure.config_manager import init_config, get_config

# Initialize config
config = init_config(config_file=Path("config.yaml"))

# Access system settings
print(config.system.log_level)
print(config.system.log_dir)

# Get agent configuration
alice_config = config.get_agent_config("alice")
print(f"Alice uses model: {alice_config.model}")

# Get experiment configuration
exp_config = config.get_experiment_config("collaborative_bug_fixing")
print(f"Experiment type: {exp_config.type}")
print(f"Agents involved: {exp_config.agents}")
print(f"Metrics to track: {exp_config.metrics}")

# Validate configuration
errors = config.validate()
if errors:
    print(f"Config errors: {errors}")

# Create agent from template
new_agent = config.create_agent_from_template(
    name="charlie",
    model="llama3.1:8b",
    template="alice",  # Copy settings from alice
    description="New collaborative agent"
)

# Environment variable overrides
# You can override any config value with environment variables:
# AGENT_SYSTEM_LOG_LEVEL=DEBUG
log_level = config.get_env_override("system.log_level", "INFO")
```

### 4. Agent Manager with Config Support (`src/agents/agent_manager.py`)

The AgentManager now supports creating agents from configuration:

```python
from src.agents.agent_manager import AgentManager
from pathlib import Path

# Initialize with config file
manager = AgentManager(config_file=Path("config.yaml"))

# Create agent from config
info = manager.create_agent_from_config("alice")
print(f"Created {info.name} with model {info.model_id}")

# Auto-create from config when messaging
# If alice tries to message bob and bob doesn't exist,
# the system will automatically create bob from config
response, stats = manager.route_message("bob", "Hello!")
```

## Running Experiments

### Example: Collaborative Bug Fixing

```python
from pathlib import Path
from src.agents.agent_manager import AgentManager
from src.infrastructure.logging_config import init_logging
from src.infrastructure.metrics import init_metrics, get_metrics
from src.infrastructure.config_manager import init_config, get_config

# Initialize infrastructure
init_logging(log_dir=Path("logs"))
init_metrics(metrics_dir=Path("metrics"))
config = init_config(Path("config.yaml"))
metrics = get_metrics()

# Get experiment config
exp_config = config.get_experiment_config("collaborative_bug_fixing")

# Create agent manager
manager = AgentManager(config_file=Path("config.yaml"))

# Create agents from config
for agent_name in exp_config.agents:
    manager.create_agent_from_config(agent_name)

# Start experiment tracking
exp_start = metrics.start_experiment(exp_config.type)

# Run experiment
# ... your experiment code here ...

# Alice and Bob will automatically log and record metrics
response, stats = manager.route_message("alice", "Help Bob fix the bug in main.py")

# End experiment tracking
metrics.end_experiment(exp_config.type, exp_start, success=True)

# Export metrics
metrics.export_to_file()

print(f"Logs saved to: logs/")
print(f"Metrics saved to: metrics/agent_metrics.prom")
```

## Monitoring Integration

### Connecting to Ladon Monitoring Stack

1. **Export metrics to file:**
   ```python
   metrics.export_to_file("metrics/agent_metrics.prom")
   ```

2. **Configure Prometheus to scrape:**
   Add to `/home/todd/olympus/infrastructure/monitoring/ladon/prometheus/prometheus.yml`:
   ```yaml
   scrape_configs:
     - job_name: 'memory-engine'
       static_configs:
         - targets: ['localhost:9090']
       file_sd_configs:
         - files:
           - '/path/to/prototype/metrics/*.prom'
   ```

3. **Create Grafana dashboard:**
   - Agent activity metrics
   - LLM latency trends
   - Function call success rates
   - Experiment duration and success rates

## Best Practices

### 1. Always Initialize Infrastructure

At the start of any script or experiment:

```python
from src.infrastructure.logging_config import init_logging
from src.infrastructure.metrics import init_metrics
from src.infrastructure.config_manager import init_config

init_logging()
init_metrics()
init_config()
```

### 2. Use Context for Multi-threaded Experiments

```python
from src.infrastructure.logging_config import set_context

# In each thread
set_context(agent_name="alice", experiment_id="exp_001", session_id="session_123")
```

### 3. Track All Experiments

```python
metrics = get_metrics()
start_time = metrics.start_experiment("my_experiment")
try:
    # Run experiment
    success = True
finally:
    metrics.end_experiment("my_experiment", start_time, success)
    metrics.export_to_file()
```

### 4. Validate Configuration

```python
config = get_config()
errors = config.validate()
if errors:
    raise ValueError(f"Invalid configuration: {errors}")
```

### 5. Use Experiment Templates

Define reusable experiment templates in config.yaml:

```yaml
experiments:
  - name: my_experiment
    type: custom
    agents: [alice, bob]
    parameters:
      max_iterations: 10
    metrics:
      - success_rate
      - time_to_completion
    validation:
      require_passing_tests: true
```

## Troubleshooting

### No logs appearing
- Check that `init_logging()` was called
- Verify log directory exists and is writable
- Check console log level setting

### Metrics not exported
- Call `metrics.export_to_file()` explicitly
- Check metrics directory exists and is writable
- Verify prometheus-client is installed

### Config validation errors
- Run `config.validate()` to see specific errors
- Check that all agent models are defined in models section
- Verify experiment agents are defined in agents section

### Agent creation fails
- Check that agent config exists in config.yaml
- Verify model is available in Ollama
- Check database connection settings

## Testing

Run the infrastructure test suite:

```bash
python3 tests/test_infrastructure.py
```

This will verify:
- Logging system initialization and output
- Metrics collection and export
- Config loading and validation
- Integration of all components

## Next Steps

1. **Run your first experiment:** See `collaborative_bug_fixing` template in config.yaml
2. **Create custom metrics:** Add new metrics to `AgentMetrics` class
3. **Build Grafana dashboards:** Visualize agent behavior over time
4. **Export to monitoring stack:** Integrate with Ladon for centralized monitoring
