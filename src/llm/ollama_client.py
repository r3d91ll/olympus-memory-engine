"""Ollama LLM client implementation."""

import re

import ollama

from src.llm.client import LLMClient, LLMResponse


class OllamaClient(LLMClient):
    """Ollama-based LLM client.

    Provides standard chat and embedding functionality.
    Note: Ollama does NOT support logprobs, so chat_with_logprobs
    will raise NotImplementedError.
    """

    def __init__(self, model_id: str = "gpt-oss:20b", embedding_model: str = "nomic-embed-text"):
        super().__init__(model_id, embedding_model)
        print(f"[OllamaClient] Using model: {model_id}, embeddings: {embedding_model}")

    def chat(
        self, messages: list[dict], max_tokens: int = 2048, temperature: float = 0.7
    ) -> str:
        """Chat completion via Ollama.

        Args:
            messages: List of message dicts with 'role' and 'content'
            max_tokens: Maximum tokens to generate
            temperature: Sampling temperature

        Returns:
            Generated text response

        Raises:
            Exception: If generation fails
        """
        try:
            response = ollama.chat(  # type: ignore[call-overload]
                model=self.model_id,
                messages=messages,
                options={
                    "num_predict": max_tokens,
                    "temperature": temperature,
                },
            )
            # Strip <think> tags if present (reasoning tokens)
            content = response["message"]["content"]
            content = re.sub(r"<think>.*?</think>", "", content, flags=re.DOTALL | re.IGNORECASE)
            return content.strip()
        except Exception as e:
            # If response is too long or other error, return graceful message
            error_msg = str(e)
            if "parsing tool call" in error_msg or "unexpected end" in error_msg:
                return "I apologize, my response was too long. Let me give you a simpler version."
            raise

    def chat_with_logprobs(
        self, messages: list[dict], max_tokens: int = 2048, temperature: float = 0.7
    ) -> LLMResponse:
        """NOT SUPPORTED: Ollama does not expose log probabilities.

        Use VLLMClient for entropy measurement / analysis tasks that require logprobs.

        Raises:
            NotImplementedError: Always (Ollama limitation)
        """
        raise NotImplementedError(
            "Ollama does not support log probabilities. "
            "Use VLLMClient for entropy measurement tasks."
        )

    def embed(self, text: str) -> list[float]:
        """Generate embedding via Ollama.

        Args:
            text: Text to embed

        Returns:
            768-dim embedding vector (nomic-embed-text default)
        """
        response = ollama.embeddings(
            model=self.embedding_model,
            prompt=text,
        )
        return list(response["embedding"])  # type: ignore[return-value]
