"""
Centralized Logging Configuration for Multi-Agent System

Provides structured logging with:
- Agent-specific loggers
- Experiment tracking
- JSON formatting for log aggregation
- Multiple output handlers (file, console, structured)
"""

import json
import logging
import logging.handlers
import sys
import threading
from datetime import datetime
from pathlib import Path
from typing import Any, Optional

# Thread-local storage for context
_context = threading.local()


class AgentContextFilter(logging.Filter):
    """Add agent context to log records"""

    def filter(self, record):
        # Add context from thread-local storage
        record.agent_name = getattr(_context, 'agent_name', 'system')
        record.experiment_id = getattr(_context, 'experiment_id', None)
        record.session_id = getattr(_context, 'session_id', None)
        return True


class JSONFormatter(logging.Formatter):
    """Format logs as JSON for structured logging"""

    def format(self, record):
        log_data = {
            'timestamp': datetime.now().isoformat(),
            'level': record.levelname,
            'logger': record.name,
            'message': record.getMessage(),
            'agent_name': getattr(record, 'agent_name', None),
            'experiment_id': getattr(record, 'experiment_id', None),
            'session_id': getattr(record, 'session_id', None),
        }

        # Add exception info if present
        if record.exc_info:
            log_data['exception'] = self.formatException(record.exc_info)

        # Add extra fields
        if hasattr(record, 'extra_data'):
            log_data['extra'] = record.extra_data

        return json.dumps(log_data)


class LoggingManager:
    """Centralized logging management for the agent system"""

    def __init__(
        self,
        log_dir: Path = Path("logs"),
        console_level: int = logging.INFO,
        file_level: int = logging.DEBUG,
        json_logging: bool = True,
    ):
        self.log_dir = Path(log_dir)
        self.log_dir.mkdir(parents=True, exist_ok=True)

        self.console_level = console_level
        self.file_level = file_level
        self.json_logging = json_logging

        # Create session ID for this run
        self.session_id = datetime.now().strftime("%Y%m%d_%H%M%S")

        # Initialize loggers dict
        self.loggers: dict[str, logging.Logger] = {}

        # Setup root logger
        self._setup_root_logger()

    def _setup_root_logger(self):
        """Configure the root logger"""
        root_logger = logging.getLogger()
        root_logger.setLevel(logging.DEBUG)

        # Remove existing handlers
        root_logger.handlers.clear()

        # Add context filter to all loggers
        context_filter = AgentContextFilter()

        # Console handler (human-readable)
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setLevel(self.console_level)
        console_formatter = logging.Formatter(
            '%(asctime)s - %(name)s - [%(agent_name)s] - %(levelname)s - %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )
        console_handler.setFormatter(console_formatter)
        console_handler.addFilter(context_filter)
        root_logger.addHandler(console_handler)

        # File handler (detailed)
        file_handler = logging.handlers.RotatingFileHandler(
            self.log_dir / f"agent_system_{self.session_id}.log",
            maxBytes=10*1024*1024,  # 10MB
            backupCount=5
        )
        file_handler.setLevel(self.file_level)
        file_handler.setFormatter(console_formatter)
        file_handler.addFilter(context_filter)
        root_logger.addHandler(file_handler)

        # JSON handler (for log aggregation)
        if self.json_logging:
            json_handler = logging.handlers.RotatingFileHandler(
                self.log_dir / f"agent_system_{self.session_id}.jsonl",
                maxBytes=10*1024*1024,  # 10MB
                backupCount=5
            )
            json_handler.setLevel(self.file_level)
            json_handler.setFormatter(JSONFormatter())
            json_handler.addFilter(context_filter)
            root_logger.addHandler(json_handler)

    def get_logger(self, name: str) -> logging.Logger:
        """Get or create a logger for a specific component

        Args:
            name: Logger name (e.g., 'agents.alice', 'memory.storage', 'tools.file')

        Returns:
            Configured logger instance
        """
        if name not in self.loggers:
            logger = logging.getLogger(name)
            self.loggers[name] = logger

        return self.loggers[name]

    def get_agent_logger(self, agent_name: str) -> logging.Logger:
        """Get a logger for a specific agent

        Args:
            agent_name: Name of the agent

        Returns:
            Configured logger for the agent
        """
        return self.get_logger(f"agents.{agent_name}")

    def set_context(
        self,
        agent_name: Optional[str] = None,
        experiment_id: Optional[str] = None,
        session_id: Optional[str] = None,
    ):
        """Set logging context for current thread

        Args:
            agent_name: Current agent name
            experiment_id: Current experiment ID
            session_id: Current session ID
        """
        if agent_name is not None:
            _context.agent_name = agent_name
        if experiment_id is not None:
            _context.experiment_id = experiment_id
        if session_id is not None:
            _context.session_id = session_id

    def clear_context(self):
        """Clear logging context for current thread"""
        _context.agent_name = 'system'
        _context.experiment_id = None
        _context.session_id = None

    def log_agent_action(
        self,
        agent_name: str,
        action: str,
        details: Optional[dict[str, Any]] = None,
        level: int = logging.INFO
    ):
        """Log an agent action with structured data

        Args:
            agent_name: Name of the agent
            action: Action being performed
            details: Additional structured data
            level: Log level
        """
        logger = self.get_agent_logger(agent_name)
        self.set_context(agent_name=agent_name)

        extra = {'extra_data': details} if details else {}
        logger.log(level, f"Action: {action}", extra=extra)

    def log_function_call(
        self,
        agent_name: str,
        function_name: str,
        arguments: dict[str, Any],
        result: Optional[str] = None,
        error: Optional[str] = None
    ):
        """Log a function call by an agent

        Args:
            agent_name: Name of the agent
            function_name: Function being called
            arguments: Function arguments
            result: Function result (if successful)
            error: Error message (if failed)
        """
        logger = self.get_agent_logger(agent_name)
        self.set_context(agent_name=agent_name)

        details = {
            'function': function_name,
            'arguments': arguments,
        }

        if result:
            details['result'] = result[:200]  # Truncate long results
            logger.info(f"Function call: {function_name}", extra={'extra_data': details})
        elif error:
            details['error'] = error
            logger.error(f"Function call failed: {function_name}", extra={'extra_data': details})

    def log_agent_message(
        self,
        sender: str,
        recipient: str,
        message: str,
        message_id: Optional[str] = None
    ):
        """Log agent-to-agent message

        Args:
            sender: Sending agent name
            recipient: Receiving agent name
            message: Message content
            message_id: Optional message ID
        """
        logger = self.get_agent_logger(sender)
        self.set_context(agent_name=sender)

        details = {
            'sender': sender,
            'recipient': recipient,
            'message': message[:200],  # Truncate long messages
            'message_id': message_id,
        }

        logger.info(f"Message sent to {recipient}", extra={'extra_data': details})

    def log_experiment_event(
        self,
        experiment_id: str,
        event_type: str,
        event_data: dict[str, Any]
    ):
        """Log an experiment event

        Args:
            experiment_id: Experiment identifier
            event_type: Type of event (e.g., 'start', 'end', 'milestone')
            event_data: Event-specific data
        """
        logger = self.get_logger("experiments")
        self.set_context(experiment_id=experiment_id)

        details = {
            'event_type': event_type,
            **event_data
        }

        logger.info(f"Experiment event: {event_type}", extra={'extra_data': details})


# Global logging manager instance
_logging_manager: Optional[LoggingManager] = None


def get_logging_manager() -> LoggingManager:
    """Get the global logging manager instance"""
    global _logging_manager
    if _logging_manager is None:
        _logging_manager = LoggingManager()
    return _logging_manager


def init_logging(
    log_dir: Path = Path("logs"),
    console_level: int = logging.INFO,
    file_level: int = logging.DEBUG,
    json_logging: bool = True,
) -> LoggingManager:
    """Initialize the global logging system

    Args:
        log_dir: Directory for log files
        console_level: Console output level
        file_level: File output level
        json_logging: Enable JSON structured logging

    Returns:
        LoggingManager instance
    """
    global _logging_manager
    _logging_manager = LoggingManager(
        log_dir=log_dir,
        console_level=console_level,
        file_level=file_level,
        json_logging=json_logging
    )
    return _logging_manager


# Convenience functions
def get_logger(name: str) -> logging.Logger:
    """Get a logger instance"""
    return get_logging_manager().get_logger(name)


def set_context(**kwargs):
    """Set logging context"""
    get_logging_manager().set_context(**kwargs)


def log_agent_action(agent_name: str, action: str, details: Optional[dict[str, Any]] = None):
    """Log an agent action"""
    get_logging_manager().log_agent_action(agent_name, action, details)


def log_function_call(agent_name: str, function_name: str, arguments: dict[str, Any], **kwargs):
    """Log a function call"""
    get_logging_manager().log_function_call(agent_name, function_name, arguments, **kwargs)


def log_agent_message(sender: str, recipient: str, message: str, **kwargs):
    """Log an agent message"""
    get_logging_manager().log_agent_message(sender, recipient, message, **kwargs)


def log_experiment_event(experiment_id: str, event_type: str, event_data: dict[str, Any]):
    """Log an experiment event"""
    get_logging_manager().log_experiment_event(experiment_id, event_type, event_data)
