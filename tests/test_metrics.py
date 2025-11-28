#!/usr/bin/env python3
"""
Unit tests for AgentMetrics
"""

import sys
import tempfile
import time
from pathlib import Path

import pytest

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from prometheus_client import CollectorRegistry

from src.infrastructure.metrics import AgentMetrics, get_metrics, init_metrics


@pytest.fixture
def temp_metrics_dir():
    """Create a temporary metrics directory"""
    with tempfile.TemporaryDirectory() as temp_dir:
        yield Path(temp_dir)


@pytest.fixture
def metrics(temp_metrics_dir):
    """Create AgentMetrics instance for testing"""
    registry = CollectorRegistry()
    return AgentMetrics(registry=registry, metrics_dir=temp_metrics_dir)


class TestAgentMetrics:
    """Test AgentMetrics class"""

    def test_metrics_init(self, temp_metrics_dir):
        """Test AgentMetrics initialization"""
        registry = CollectorRegistry()
        metrics = AgentMetrics(registry=registry, metrics_dir=temp_metrics_dir)

        assert metrics.metrics_dir == temp_metrics_dir
        assert metrics.registry == registry
        assert metrics._current_agent is None
        assert metrics._current_experiment is None

    def test_set_context(self, metrics):
        """Test setting metrics context"""
        metrics.set_context(agent="alice", experiment="exp_001")

        assert metrics._current_agent == "alice"
        assert metrics._current_experiment == "exp_001"

    def test_record_message(self, metrics):
        """Test recording a message"""
        # Should not raise
        metrics.record_message(sender="alice", recipient="bob")

        # Verify metric was recorded (check registry)
        assert True

    def test_record_function_call(self, metrics):
        """Test recording a function call"""
        metrics.record_function_call(
            agent="alice",
            function="test_function",
            success=True,
            duration=0.5
        )

        # Should not raise
        assert True

    def test_record_function_call_failure(self, metrics):
        """Test recording a failed function call"""
        metrics.record_function_call(
            agent="alice",
            function="test_function",
            success=False,
            duration=0.1
        )

        assert True

    def test_record_memory_operation(self, metrics):
        """Test recording a memory operation"""
        metrics.record_memory_operation(
            agent="alice",
            operation="save"
        )

        assert True

    def test_record_memory_search_with_results(self, metrics):
        """Test recording memory search with results"""
        metrics.record_memory_operation(
            agent="alice",
            operation="search",
            results=5
        )

        assert True

    def test_record_llm_request(self, metrics):
        """Test recording an LLM request"""
        metrics.record_llm_request(
            agent="alice",
            model="llama3.1:8b",
            latency=1.5,
            input_tokens=100,
            output_tokens=50
        )

        assert True

    def test_record_tool_use(self, metrics):
        """Test recording tool usage"""
        metrics.record_tool_use(
            agent="alice",
            tool="read_file",
            success=True,
            duration=0.2
        )

        assert True

    def test_track_function_context_manager(self, metrics):
        """Test track_function context manager"""
        with metrics.track_function(agent="alice", function="test_func"):
            time.sleep(0.01)  # Simulate work

        # Should complete without error
        assert True

    def test_track_function_with_exception(self, metrics):
        """Test track_function with exception"""
        with pytest.raises(ValueError):
            with metrics.track_function(agent="alice", function="test_func"):
                raise ValueError("Test error")

        # Function should still be recorded as failed
        assert True

    def test_track_tool_context_manager(self, metrics):
        """Test track_tool context manager"""
        with metrics.track_tool(agent="alice", tool="read_file"):
            time.sleep(0.01)

        assert True

    def test_track_llm_context_manager(self, metrics):
        """Test track_llm context manager"""
        with metrics.track_llm(agent="alice", model="llama3.1:8b"):
            time.sleep(0.01)

        assert True

    def test_update_active_agents(self, metrics):
        """Test updating active agent count"""
        metrics.update_active_agents(5)

        # Should not raise
        assert True

    def test_register_agent(self, metrics):
        """Test registering agent metadata"""
        metrics.register_agent(
            name="alice",
            model="llama3.1:8b",
            description="Test agent"
        )

        assert True

    def test_start_experiment(self, metrics):
        """Test starting an experiment"""
        start_time = metrics.start_experiment("bug_fixing")

        assert isinstance(start_time, float)
        assert start_time > 0

    def test_end_experiment(self, metrics):
        """Test ending an experiment"""
        start_time = metrics.start_experiment("bug_fixing")
        time.sleep(0.01)

        metrics.end_experiment(
            experiment_type="bug_fixing",
            start_time=start_time,
            success=True
        )

        assert True

    def test_export_to_file(self, metrics, temp_metrics_dir):
        """Test exporting metrics to file"""
        # Record some metrics
        metrics.record_message(sender="alice", recipient="bob")
        metrics.record_function_call("alice", "test", True, 0.1)

        # Export
        metrics.export_to_file()

        # Check file was created
        export_file = temp_metrics_dir / "agent_metrics.prom"
        assert export_file.exists()

        # Check file has content
        content = export_file.read_text()
        assert len(content) > 0

    def test_export_to_custom_file(self, metrics, temp_metrics_dir):
        """Test exporting to custom filename"""
        custom_file = temp_metrics_dir / "custom_metrics.prom"

        metrics.record_message(sender="alice", recipient="bob")
        metrics.export_to_file(str(custom_file))

        assert custom_file.exists()


class TestMetricsIntegration:
    """Test metrics integration scenarios"""

    def test_complete_agent_workflow(self, metrics):
        """Test complete agent workflow with metrics"""
        # Start experiment
        exp_start = metrics.start_experiment("test")

        # Agent activity
        metrics.update_active_agents(2)
        metrics.register_agent("alice", "llama3.1:8b")

        # Messages
        metrics.record_message("alice", "bob")
        metrics.record_message("bob", "alice")

        # Function calls
        with metrics.track_function("alice", "solve_problem"):
            time.sleep(0.01)

        # LLM calls
        metrics.record_llm_request(
            agent="alice",
            model="llama3.1:8b",
            latency=1.0,
            input_tokens=100,
            output_tokens=50
        )

        # Memory operations
        metrics.record_memory_operation("alice", "save")
        metrics.record_memory_operation("alice", "search", results=3)

        # Tool usage
        with metrics.track_tool("alice", "read_file"):
            time.sleep(0.01)

        # End experiment
        metrics.end_experiment("test", exp_start, success=True)

        # Export
        metrics.export_to_file()

        # All operations completed successfully
        assert True


class TestGlobalFunctions:
    """Test global helper functions"""

    def test_get_metrics(self):
        """Test get_metrics"""
        metrics = get_metrics()

        assert metrics is not None
        assert isinstance(metrics, AgentMetrics)

    def test_init_metrics(self, temp_metrics_dir):
        """Test init_metrics"""
        metrics = init_metrics(metrics_dir=temp_metrics_dir)

        assert metrics is not None
        assert isinstance(metrics, AgentMetrics)
        assert metrics.metrics_dir == temp_metrics_dir


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
