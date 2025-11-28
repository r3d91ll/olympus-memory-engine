"""Abstract base class for LLM clients."""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Optional


@dataclass
class LLMResponse:
    """Response from LLM generation."""

    text: str
    """Generated text"""

    logprobs: Optional[list[float]] = None
    """Token-level log probabilities (for entropy calculation)"""

    metadata: Optional[dict] = None
    """Additional metadata (model, tokens used, etc.)"""


class LLMClient(ABC):
    """Abstract base class for LLM inference clients.

    Supports both standard generation (for production chat) and
    generation with logprobs (for entropy measurement/analysis).
    """

    def __init__(self, model_id: str, embedding_model: str = "nomic-embed-text"):
        self.model_id = model_id
        self.embedding_model = embedding_model

    @abstractmethod
    def chat(
        self, messages: list[dict], max_tokens: int = 2048, temperature: float = 0.7
    ) -> str:
        """Standard chat completion (production use).

        Args:
            messages: List of message dicts with 'role' and 'content'
            max_tokens: Maximum tokens to generate
            temperature: Sampling temperature

        Returns:
            Generated text response
        """
        pass

    @abstractmethod
    def chat_with_logprobs(
        self, messages: list[dict], max_tokens: int = 2048, temperature: float = 0.7
    ) -> LLMResponse:
        """Chat completion with log probabilities (analysis use).

        Args:
            messages: List of message dicts with 'role' and 'content'
            max_tokens: Maximum tokens to generate
            temperature: Sampling temperature

        Returns:
            LLMResponse with text and logprobs
        """
        pass

    @abstractmethod
    def embed(self, text: str) -> list[float]:
        """Generate embedding vector.

        Args:
            text: Text to embed

        Returns:
            Embedding vector (typically 768-dim for nomic-embed-text)
        """
        pass
