#!/usr/bin/env python3
"""
Test Infrastructure Integration

Tests the integration of logging, metrics, and config systems.
"""

import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.infrastructure.config_manager import init_config
from src.infrastructure.logging_config import get_logger, init_logging
from src.infrastructure.metrics import init_metrics


def test_logging():
    """Test logging system initialization and usage"""
    print("\n=== Testing Logging System ===")

    # Initialize logging
    log_manager = init_logging(log_dir=Path("logs"))

    # Get logger
    logger = get_logger("test")

    # Test logging
    logger.info("Test info message")
    logger.warning("Test warning message")
    logger.error("Test error message")

    # Test agent logger
    agent_logger = log_manager.get_agent_logger("test_agent")
    agent_logger.info("Test agent message")

    # Test context
    log_manager.set_context(agent_name="alice", experiment_id="exp_001")
    logger.info("Message with context")

    # Test structured logging
    log_manager.log_agent_action(
        agent_name="alice",
        action="test_action",
        details={"param1": "value1", "param2": 42}
    )

    log_manager.log_function_call(
        agent_name="alice",
        function_name="test_function",
        arguments={"arg1": "value"},
        result="success"
    )

    log_manager.log_agent_message(
        sender="alice",
        recipient="bob",
        message="Test message"
    )

    print("✓ Logging system working")
    return True


def test_metrics():
    """Test metrics system initialization and usage"""
    print("\n=== Testing Metrics System ===")

    # Initialize metrics
    metrics = init_metrics(metrics_dir=Path("metrics"))

    # Test message recording
    metrics.record_message(sender="alice", recipient="bob")
    metrics.record_message(sender="bob", recipient="alice")

    # Test function call recording
    metrics.record_function_call(
        agent="alice",
        function="test_function",
        success=True,
        duration=0.5
    )

    metrics.record_function_call(
        agent="alice",
        function="test_function",
        success=False,
        duration=0.1
    )

    # Test memory operations
    metrics.record_memory_operation(agent="alice", operation="save")
    metrics.record_memory_operation(agent="alice", operation="search", results=5)

    # Test LLM tracking
    metrics.record_llm_request(
        agent="alice",
        model="llama3.1:8b",
        latency=1.5,
        input_tokens=100,
        output_tokens=50
    )

    # Test tool usage
    metrics.record_tool_use(
        agent="alice",
        tool="read_file",
        success=True,
        duration=0.2
    )

    # Test experiment tracking
    start_time = metrics.start_experiment("bug_fixing")
    metrics.end_experiment("bug_fixing", start_time, success=True)

    # Export metrics
    metrics.export_to_file()

    print("✓ Metrics system working")
    return True


def test_config():
    """Test config system initialization and usage"""
    print("\n=== Testing Config System ===")

    # Initialize config
    config_file = Path(__file__).parent.parent / "config.yaml"
    config = init_config(config_file)

    # Test system config
    print(f"  Log level: {config.system.log_level}")
    print(f"  Log dir: {config.system.log_dir}")
    print(f"  Metrics dir: {config.system.metrics_dir}")

    # Test models
    print(f"\n  Available models: {len(config.models)}")
    for model_id, model in list(config.models.items())[:3]:
        print(f"    - {model_id}: {model.get('name', 'N/A')}")

    # Test agents
    print(f"\n  Configured agents: {len(config.agents)}")
    for agent_name in list(config.agents.keys())[:3]:
        agent = config.agents[agent_name]
        print(f"    - {agent.name}: {agent.model}")

    # Test experiments
    print(f"\n  Experiment templates: {len(config.experiments)}")
    for exp_name in list(config.experiments.keys())[:3]:
        exp = config.experiments[exp_name]
        print(f"    - {exp.name}: {exp.type}")
        print(f"      Agents: {', '.join(exp.agents)}")

    # Test agent retrieval
    alice_config = config.get_agent_config("alice")
    if alice_config:
        print("\n  Alice agent config:")
        print(f"    Model: {alice_config.model}")
        print(f"    Description: {alice_config.description}")

    # Test experiment retrieval
    bug_fix_exp = config.get_experiment_config("collaborative_bug_fixing")
    if bug_fix_exp:
        print("\n  Bug fixing experiment config:")
        print(f"    Type: {bug_fix_exp.type}")
        print(f"    Agents: {bug_fix_exp.agents}")
        print(f"    Metrics: {bug_fix_exp.metrics}")

    # Test validation
    errors = config.validate()
    if errors:
        print(f"\n  ⚠ Validation errors: {errors}")
    else:
        print("\n  ✓ Config validation passed")

    print("✓ Config system working")
    return True


def test_integration():
    """Test integration of all systems"""
    print("\n=== Testing System Integration ===")

    # Initialize all systems
    log_manager = init_logging(log_dir=Path("logs"))
    metrics = init_metrics(metrics_dir=Path("metrics"))
    config_file = Path(__file__).parent.parent / "config.yaml"
    config = init_config(config_file)

    # Simulate agent interaction
    logger = get_logger("integration_test")

    # Set context
    log_manager.set_context(agent_name="alice", experiment_id="test_001")

    # Log and record an action
    logger.info("Starting integration test")
    metrics.update_active_agents(2)

    # Simulate agent message
    log_manager.log_agent_message(
        sender="alice",
        recipient="bob",
        message="Test message"
    )
    metrics.record_message(sender="alice", recipient="bob")

    # Simulate function call
    log_manager.log_function_call(
        agent_name="alice",
        function_name="test_function",
        arguments={"arg": "value"},
        result="success"
    )
    metrics.record_function_call(
        agent="alice",
        function="test_function",
        success=True,
        duration=0.3
    )

    logger.info("Integration test complete")

    print("✓ Integration working")
    return True


def main():
    """Run all tests"""
    print("=" * 70)
    print("Infrastructure Integration Tests")
    print("=" * 70)

    try:
        # Run tests
        test_logging()
        test_metrics()
        test_config()
        test_integration()

        print("\n" + "=" * 70)
        print("✓ All infrastructure tests passed!")
        print("=" * 70)

        print("\nGenerated files:")
        print("  - Logs: logs/")
        print("  - Metrics: metrics/agent_metrics.prom")

        return 0

    except Exception as e:
        print(f"\n✗ Test failed: {e}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(main())
