"""vLLM client implementation with logprobs support."""

import re
from typing import Optional

import ollama

try:
    from vllm import LLM, SamplingParams
    from vllm.outputs import RequestOutput

    VLLM_AVAILABLE = True
except ImportError:
    VLLM_AVAILABLE = False
    LLM = None  # type: ignore
    SamplingParams = None  # type: ignore
    RequestOutput = None  # type: ignore

from src.llm.client import LLMClient, LLMResponse


class VLLMClient(LLMClient):
    """vLLM-based LLM client with log probability support.

    vLLM provides efficient inference with access to token-level log probabilities,
    enabling entropy measurement for IF-Track analysis.

    Note: Embeddings still use Ollama (nomic-embed-text) for consistency.
    """

    def __init__(
        self,
        model_id: str = "Qwen/Qwen2-VL-7B-Instruct",
        embedding_model: str = "nomic-embed-text",
        gpu_memory_utilization: float = 0.9,
        max_model_len: Optional[int] = None,
        tensor_parallel_size: int = 1,
    ):
        """Initialize vLLM client.

        Args:
            model_id: HuggingFace model ID (e.g., "Qwen/Qwen2-VL-7B-Instruct")
            embedding_model: Ollama embedding model for consistency
            gpu_memory_utilization: GPU memory fraction to use (0.0-1.0)
            max_model_len: Maximum sequence length (None = model default)
            tensor_parallel_size: Number of GPUs to use for tensor parallelism

        Raises:
            ImportError: If vLLM is not installed
        """
        if not VLLM_AVAILABLE:
            raise ImportError(
                "vLLM is not installed. Install with: poetry add vllm\n"
                "Note: vLLM requires CUDA-capable GPU."
            )

        super().__init__(model_id, embedding_model)

        print(f"[VLLMClient] Loading model: {model_id}")
        print(f"[VLLMClient] GPU memory utilization: {gpu_memory_utilization}")
        print(f"[VLLMClient] Tensor parallel size: {tensor_parallel_size}")

        # Initialize vLLM engine
        self.llm = LLM(
            model=model_id,
            gpu_memory_utilization=gpu_memory_utilization,
            max_model_len=max_model_len,
            trust_remote_code=True,  # Required for some models like Qwen
            tensor_parallel_size=tensor_parallel_size,
        )

        print("[VLLMClient] Model loaded successfully")
        print(f"[VLLMClient] Using Ollama for embeddings: {embedding_model}")

    def chat(
        self, messages: list[dict], max_tokens: int = 2048, temperature: float = 0.7
    ) -> str:
        """Standard chat completion without logprobs.

        Args:
            messages: List of message dicts with 'role' and 'content'
            max_tokens: Maximum tokens to generate
            temperature: Sampling temperature

        Returns:
            Generated text response
        """
        # Format messages into prompt (simple concatenation for now)
        # TODO: Use proper chat template from tokenizer
        prompt = self._format_messages(messages)

        # Generate without logprobs for efficiency
        sampling_params = SamplingParams(
            temperature=temperature,
            max_tokens=max_tokens,
            top_p=0.9,
        )

        outputs = self.llm.generate([prompt], sampling_params)
        text = outputs[0].outputs[0].text

        # Strip <think> tags if present (reasoning tokens)
        text = re.sub(r"<think>.*?</think>", "", text, flags=re.DOTALL | re.IGNORECASE)

        return text.strip()

    def chat_with_logprobs(
        self,
        messages: list[dict],
        max_tokens: int = 2048,
        temperature: float = 0.7,
        logprobs: int = 5,
    ) -> LLMResponse:
        """Chat completion with log probabilities for entropy analysis.

        Args:
            messages: List of message dicts with 'role' and 'content'
            max_tokens: Maximum tokens to generate
            temperature: Sampling temperature
            logprobs: Number of top logprobs to return per token

        Returns:
            LLMResponse with text and token-level logprobs
        """
        # Format messages into prompt
        prompt = self._format_messages(messages)

        # Generate with logprobs enabled
        sampling_params = SamplingParams(
            temperature=temperature,
            max_tokens=max_tokens,
            top_p=0.9,
            logprobs=logprobs,  # Enable log probability collection
        )

        outputs = self.llm.generate([prompt], sampling_params)
        output = outputs[0].outputs[0]

        text = output.text
        # Strip <think> tags
        text = re.sub(r"<think>.*?</think>", "", text, flags=re.DOTALL | re.IGNORECASE)

        # Extract log probabilities
        # output.logprobs is List[Dict[int, Logprob]] for each token
        token_logprobs = self._extract_logprobs(output.logprobs) if output.logprobs else []

        return LLMResponse(
            text=text.strip(),
            logprobs=token_logprobs,
            metadata={
                "model": self.model_id,
                "finish_reason": output.finish_reason,
                "num_tokens": len(output.token_ids),
            },
        )

    def embed(self, text: str) -> list[float]:
        """Generate embedding via Ollama for consistency.

        vLLM doesn't provide dedicated embedding models, so we use
        Ollama's nomic-embed-text for consistency with existing system.

        Args:
            text: Text to embed

        Returns:
            768-dim embedding vector
        """
        response = ollama.embeddings(
            model=self.embedding_model,
            prompt=text,
        )
        return list(response["embedding"])  # type: ignore[return-value]

    def _format_messages(self, messages: list[dict]) -> str:
        """Format messages into prompt string.

        Simple concatenation for now. In production, should use
        model-specific chat template.

        Args:
            messages: List of message dicts with 'role' and 'content'

        Returns:
            Formatted prompt string
        """
        # Simple format: concatenate with role prefixes
        parts = []
        for msg in messages:
            role = msg["role"]
            content = msg["content"]
            if role == "system":
                parts.append(f"System: {content}")
            elif role == "user":
                parts.append(f"User: {content}")
            elif role == "assistant":
                parts.append(f"Assistant: {content}")
        parts.append("Assistant:")  # Prompt for response
        return "\n\n".join(parts)

    def _extract_logprobs(self, logprobs_data: list) -> list[float]:
        """Extract log probabilities from vLLM output.

        Args:
            logprobs_data: vLLM logprobs output (list of dicts per token)

        Returns:
            List of log probabilities for generated tokens
        """
        token_logprobs = []

        for token_logprobs_dict in logprobs_data:
            if not token_logprobs_dict:
                continue

            # Get the logprob of the actual selected token
            # token_logprobs_dict maps token_id -> Logprob object
            # The selected token should have the highest probability
            max_logprob = max(lp.logprob for lp in token_logprobs_dict.values())
            token_logprobs.append(float(max_logprob))

        return token_logprobs
