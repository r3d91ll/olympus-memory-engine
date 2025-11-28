#!/usr/bin/env python3
"""
Unit tests for LoggingManager
"""

import logging
import sys
import tempfile
from pathlib import Path

import pytest

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.infrastructure.logging_config import (
    AgentContextFilter,
    JSONFormatter,
    LoggingManager,
    get_logging_manager,
    init_logging,
)


@pytest.fixture
def temp_log_dir():
    """Create a temporary log directory"""
    with tempfile.TemporaryDirectory() as temp_dir:
        yield Path(temp_dir)


class TestAgentContextFilter:
    """Test AgentContextFilter"""

    def test_filter_adds_context(self):
        """Test that filter adds agent context to log records"""
        filter_obj = AgentContextFilter()

        # Create a log record
        record = logging.LogRecord(
            name="test",
            level=logging.INFO,
            pathname="",
            lineno=0,
            msg="Test message",
            args=(),
            exc_info=None
        )

        # Apply filter
        result = filter_obj.filter(record)

        assert result is True
        assert hasattr(record, 'agent_name')
        assert hasattr(record, 'experiment_id')
        assert hasattr(record, 'session_id')


class TestJSONFormatter:
    """Test JSONFormatter"""

    def test_json_formatter_output(self):
        """Test that formatter outputs valid JSON"""
        import json

        formatter = JSONFormatter()

        record = logging.LogRecord(
            name="test",
            level=logging.INFO,
            pathname="",
            lineno=0,
            msg="Test message",
            args=(),
            exc_info=None
        )

        # Add agent context
        record.agent_name = "test_agent"
        record.experiment_id = "exp_001"
        record.session_id = "session_001"

        # Format
        output = formatter.format(record)

        # Should be valid JSON
        data = json.loads(output)

        assert data['level'] == 'INFO'
        assert data['message'] == 'Test message'
        assert data['agent_name'] == 'test_agent'
        assert data['experiment_id'] == 'exp_001'

    def test_json_formatter_with_exception(self):
        """Test formatter with exception info"""
        import json

        formatter = JSONFormatter()

        try:
            raise ValueError("Test error")
        except ValueError:
            import sys
            exc_info = sys.exc_info()

        record = logging.LogRecord(
            name="test",
            level=logging.ERROR,
            pathname="",
            lineno=0,
            msg="Error occurred",
            args=(),
            exc_info=exc_info
        )
        record.agent_name = "test_agent"

        output = formatter.format(record)
        data = json.loads(output)

        assert data['level'] == 'ERROR'
        assert 'exception' in data
        assert 'Test error' in data['exception']


class TestLoggingManager:
    """Test LoggingManager"""

    def test_logging_manager_init(self, temp_log_dir):
        """Test LoggingManager initialization"""
        manager = LoggingManager(log_dir=temp_log_dir)

        assert manager.log_dir == temp_log_dir
        assert manager.console_level == logging.INFO
        assert manager.file_level == logging.DEBUG
        assert manager.json_logging is True
        assert len(manager.session_id) > 0

    def test_get_logger(self, temp_log_dir):
        """Test getting a logger"""
        manager = LoggingManager(log_dir=temp_log_dir)

        logger = manager.get_logger("test_module")

        assert logger is not None
        assert logger.name == "test_module"
        assert "test_module" in manager.loggers

    def test_get_agent_logger(self, temp_log_dir):
        """Test getting an agent-specific logger"""
        manager = LoggingManager(log_dir=temp_log_dir)

        logger = manager.get_agent_logger("alice")

        assert logger is not None
        assert logger.name == "agents.alice"

    def test_set_context(self, temp_log_dir):
        """Test setting logging context"""
        manager = LoggingManager(log_dir=temp_log_dir)

        # Set context
        manager.set_context(
            agent_name="alice",
            experiment_id="exp_001",
            session_id="session_001"
        )

        # Context should be set (we can't directly check thread-local storage,
        # but we can verify the method doesn't raise)
        assert True

    def test_clear_context(self, temp_log_dir):
        """Test clearing logging context"""
        manager = LoggingManager(log_dir=temp_log_dir)

        manager.set_context(agent_name="alice")
        manager.clear_context()

        # Should not raise
        assert True

    def test_log_agent_action(self, temp_log_dir):
        """Test logging agent action"""
        manager = LoggingManager(log_dir=temp_log_dir)

        # Should not raise
        manager.log_agent_action(
            agent_name="alice",
            action="test_action",
            details={"key": "value"}
        )

        assert True

    def test_log_function_call_success(self, temp_log_dir):
        """Test logging successful function call"""
        manager = LoggingManager(log_dir=temp_log_dir)

        manager.log_function_call(
            agent_name="alice",
            function_name="test_function",
            arguments={"arg": "value"},
            result="Success"
        )

        assert True

    def test_log_function_call_error(self, temp_log_dir):
        """Test logging failed function call"""
        manager = LoggingManager(log_dir=temp_log_dir)

        manager.log_function_call(
            agent_name="alice",
            function_name="test_function",
            arguments={"arg": "value"},
            error="Error occurred"
        )

        assert True

    def test_log_agent_message(self, temp_log_dir):
        """Test logging agent-to-agent message"""
        manager = LoggingManager(log_dir=temp_log_dir)

        manager.log_agent_message(
            sender="alice",
            recipient="bob",
            message="Test message"
        )

        assert True

    def test_log_experiment_event(self, temp_log_dir):
        """Test logging experiment event"""
        manager = LoggingManager(log_dir=temp_log_dir)

        manager.log_experiment_event(
            experiment_id="exp_001",
            event_type="start",
            event_data={"param": "value"}
        )

        assert True

    def test_log_files_created(self, temp_log_dir):
        """Test that log files are created"""
        manager = LoggingManager(log_dir=temp_log_dir)

        logger = manager.get_logger("test")
        logger.info("Test message")

        # Check that log files exist
        log_files = list(temp_log_dir.glob("agent_system_*.log"))
        assert len(log_files) > 0

        if manager.json_logging:
            json_files = list(temp_log_dir.glob("agent_system_*.jsonl"))
            assert len(json_files) > 0


class TestGlobalFunctions:
    """Test global helper functions"""

    def test_get_logging_manager(self):
        """Test get_logging_manager"""
        manager = get_logging_manager()

        assert manager is not None
        assert isinstance(manager, LoggingManager)

    def test_init_logging(self, temp_log_dir):
        """Test init_logging"""
        manager = init_logging(log_dir=temp_log_dir)

        assert manager is not None
        assert isinstance(manager, LoggingManager)
        assert manager.log_dir == temp_log_dir


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
