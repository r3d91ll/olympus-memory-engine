"""Olympus Memory Engine - MemGPT-style hierarchical memory for LLM agents.

A fast, local implementation of MemGPT with PostgreSQL + pgvector backend.

Example:
    from src import MemGPTAgent, MemoryStorage

    storage = MemoryStorage()
    agent = MemGPTAgent(name="assistant", storage=storage)
    response, metrics = agent.chat("Remember that I prefer Python")
    print(metrics.summary())  # LLM: 234ms | 45.2 tok/s | total: 312ms
"""

__version__ = "0.1.0"

from src.agents.memgpt_agent import MemGPTAgent, OllamaClient, ResponseMetrics
from src.memory.memory_storage import MemoryStorage

__all__ = [
    "__version__",
    "MemGPTAgent",
    "MemoryStorage",
    "OllamaClient",
    "ResponseMetrics",
]
