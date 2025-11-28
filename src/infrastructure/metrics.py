"""
Prometheus Metrics for Multi-Agent System

Exposes metrics for:
- Agent actions and interactions
- Function call success/failure rates
- Message passing metrics
- Memory operations
- Experiment tracking
"""

import time
from contextlib import contextmanager
from pathlib import Path
from typing import Optional

from prometheus_client import (
    CollectorRegistry,
    Counter,
    Gauge,
    Histogram,
    Info,
    push_to_gateway,
    write_to_textfile,
)


class AgentMetrics:
    """Prometheus metrics for the agent system"""

    def __init__(self, registry: Optional[CollectorRegistry] = None, metrics_dir: Path = Path("metrics")):
        self.registry = registry or CollectorRegistry()
        self.metrics_dir = Path(metrics_dir)
        self.metrics_dir.mkdir(parents=True, exist_ok=True)

        # Agent interaction metrics
        self.messages_sent = Counter(
            'agent_messages_sent_total',
            'Total messages sent between agents',
            ['sender', 'recipient'],
            registry=self.registry
        )

        self.messages_received = Counter(
            'agent_messages_received_total',
            'Total messages received by agents',
            ['agent'],
            registry=self.registry
        )

        # Function call metrics
        self.function_calls = Counter(
            'agent_function_calls_total',
            'Total function calls by agents',
            ['agent', 'function', 'status'],  # status: success|error
            registry=self.registry
        )

        self.function_duration = Histogram(
            'agent_function_duration_seconds',
            'Time spent executing functions',
            ['agent', 'function'],
            registry=self.registry
        )

        # Memory operation metrics
        self.memory_operations = Counter(
            'agent_memory_operations_total',
            'Total memory operations',
            ['agent', 'operation'],  # operation: save|search|update
            registry=self.registry
        )

        self.memory_search_results = Histogram(
            'agent_memory_search_results',
            'Number of results from memory searches',
            ['agent'],
            registry=self.registry
        )

        # LLM interaction metrics
        self.llm_requests = Counter(
            'agent_llm_requests_total',
            'Total LLM inference requests',
            ['agent', 'model'],
            registry=self.registry
        )

        self.llm_tokens = Counter(
            'agent_llm_tokens_total',
            'Total tokens processed',
            ['agent', 'model', 'type'],  # token type: input|output
            registry=self.registry
        )

        self.llm_latency = Histogram(
            'agent_llm_latency_seconds',
            'LLM response latency',
            ['agent', 'model'],
            registry=self.registry
        )

        # Tool usage metrics
        self.tool_calls = Counter(
            'agent_tool_calls_total',
            'Tool usage by agents',
            ['agent', 'tool', 'status'],
            registry=self.registry
        )

        self.tool_duration = Histogram(
            'agent_tool_duration_seconds',
            'Time spent using tools',
            ['agent', 'tool'],
            registry=self.registry
        )

        # Experiment metrics
        self.experiment_runs = Counter(
            'experiments_run_total',
            'Total experiments run',
            ['experiment_type'],
            registry=self.registry
        )

        self.experiment_duration = Histogram(
            'experiment_duration_seconds',
            'Time to complete experiments',
            ['experiment_type'],
            registry=self.registry
        )

        self.experiment_success_rate = Gauge(
            'experiment_success_rate',
            'Success rate of experiments',
            ['experiment_type'],
            registry=self.registry
        )

        # Agent state metrics
        self.active_agents = Gauge(
            'agents_active',
            'Number of currently active agents',
            registry=self.registry
        )

        self.agent_info = Info(
            'agent',
            'Agent metadata',
            registry=self.registry
        )

        # Context tracking
        self._current_agent: Optional[str] = None
        self._current_experiment: Optional[str] = None

    def set_context(self, agent: Optional[str] = None, experiment: Optional[str] = None):
        """Set current metrics context"""
        if agent is not None:
            self._current_agent = agent
        if experiment is not None:
            self._current_experiment = experiment

    def record_message(self, sender: str, recipient: str):
        """Record a message between agents"""
        self.messages_sent.labels(sender=sender, recipient=recipient).inc()
        self.messages_received.labels(agent=recipient).inc()

    def record_function_call(self, agent: str, function: str, success: bool, duration: float):
        """Record a function call"""
        status = 'success' if success else 'error'
        self.function_calls.labels(agent=agent, function=function, status=status).inc()
        self.function_duration.labels(agent=agent, function=function).observe(duration)

    def record_memory_operation(self, agent: str, operation: str, results: Optional[int] = None):
        """Record a memory operation"""
        self.memory_operations.labels(agent=agent, operation=operation).inc()
        if operation == 'search' and results is not None:
            self.memory_search_results.labels(agent=agent).observe(results)

    def record_llm_request(self, agent: str, model: str, latency: float, input_tokens: int, output_tokens: int):
        """Record an LLM request"""
        self.llm_requests.labels(agent=agent, model=model).inc()
        self.llm_latency.labels(agent=agent, model=model).observe(latency)
        self.llm_tokens.labels(agent=agent, model=model, type='input').inc(input_tokens)
        self.llm_tokens.labels(agent=agent, model=model, type='output').inc(output_tokens)

    def record_tool_use(self, agent: str, tool: str, success: bool, duration: float):
        """Record tool usage"""
        status = 'success' if success else 'error'
        self.tool_calls.labels(agent=agent, tool=tool, status=status).inc()
        self.tool_duration.labels(agent=agent, tool=tool).observe(duration)

    @contextmanager
    def track_function(self, agent: str, function: str):
        """Context manager to track function execution"""
        start = time.time()
        success = False
        try:
            yield
            success = True
        finally:
            duration = time.time() - start
            self.record_function_call(agent, function, success, duration)

    @contextmanager
    def track_tool(self, agent: str, tool: str):
        """Context manager to track tool usage"""
        start = time.time()
        success = False
        try:
            yield
            success = True
        finally:
            duration = time.time() - start
            self.record_tool_use(agent, tool, success, duration)

    @contextmanager
    def track_llm(self, agent: str, model: str):
        """Context manager to track LLM calls"""
        start = time.time()
        try:
            yield
        finally:
            latency = time.time() - start
            # Note: tokens need to be recorded separately by caller
            self.llm_latency.labels(agent=agent, model=model).observe(latency)

    def update_active_agents(self, count: int):
        """Update the number of active agents"""
        self.active_agents.set(count)

    def register_agent(self, name: str, model: str, **metadata):
        """Register agent metadata"""
        info = {
            'name': name,
            'model': model,
            **{k: str(v) for k, v in metadata.items()}
        }
        self.agent_info.info(info)

    def start_experiment(self, experiment_type: str):
        """Mark the start of an experiment"""
        self.experiment_runs.labels(experiment_type=experiment_type).inc()
        return time.time()

    def end_experiment(self, experiment_type: str, start_time: float, success: bool):
        """Mark the end of an experiment"""
        duration = time.time() - start_time
        self.experiment_duration.labels(experiment_type=experiment_type).observe(duration)

    def export_to_file(self, filename: Optional[str] = None):
        """Export metrics to a file for node-exporter textfile collector"""
        if filename is None:
            filename = str(self.metrics_dir / "agent_metrics.prom")
        write_to_textfile(str(filename), self.registry)

    def push_to_gateway(self, gateway: str, job: str = 'agent_system'):
        """Push metrics to Prometheus pushgateway"""
        push_to_gateway(gateway, job=job, registry=self.registry)


# Global metrics instance
_metrics: Optional[AgentMetrics] = None


def get_metrics() -> AgentMetrics:
    """Get the global metrics instance"""
    global _metrics
    if _metrics is None:
        _metrics = AgentMetrics()
    return _metrics


def init_metrics(metrics_dir: Path = Path("metrics"), registry: Optional[CollectorRegistry] = None) -> AgentMetrics:
    """Initialize the global metrics system"""
    global _metrics
    _metrics = AgentMetrics(registry=registry, metrics_dir=metrics_dir)
    return _metrics


# Convenience functions
def record_message(sender: str, recipient: str):
    """Record an agent message"""
    get_metrics().record_message(sender, recipient)


def record_function_call(agent: str, function: str, success: bool, duration: float):
    """Record a function call"""
    get_metrics().record_function_call(agent, function, success, duration)


def track_function(agent: str, function: str):
    """Context manager to track function execution"""
    return get_metrics().track_function(agent, function)


def track_tool(agent: str, tool: str):
    """Context manager to track tool usage"""
    return get_metrics().track_tool(agent, tool)
