"""Diagnostic LLM engine using HuggingFace Transformers.

This is a SLOW but DEEP analysis engine for capturing internal model metrics:
- Hidden states (all layers)
- Attention weights (all heads)
- Layer-wise embeddings
- D_eff (effective dimensionality via PCA)
- β (collapse indicator)
- Attention entropy

Use vLLMClient for fast inference (100+ samples).
Use TransformersModelEngine for diagnostic analysis (10-20 samples).

Example:
    >>> from src.llm.transformers_engine import TransformersModelEngine
    >>>
    >>> # Initialize with diagnostic mode
    >>> engine = TransformersModelEngine(
    ...     model_id="Qwen/Qwen2.5-7B-Instruct",
    ...     device="cuda",
    ...     load_in_8bit=False  # Use full precision for metrics
    ... )
    >>>
    >>> # Run inference with full internal capture
    >>> result = engine.inference_with_diagnostics(
    ...     prompt="Solve: 2x + 5 = 13",
    ...     max_tokens=512
    ... )
    >>>
    >>> # Access deep metrics
    >>> print(f"D_eff by layer: {result['d_eff_by_layer']}")
    >>> print(f"β by layer: {result['beta_by_layer']}")
    >>> print(f"Attention entropy: {result['attention_entropy']}")
"""

import numpy as np
import torch
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from scipy.spatial.distance import pdist

try:
    from transformers import AutoModelForCausalLM, AutoTokenizer
    TRANSFORMERS_AVAILABLE = True
except ImportError:
    TRANSFORMERS_AVAILABLE = False


@dataclass
class DiagnosticResult:
    """Full diagnostic output from TransformersModelEngine.

    Attributes:
        text: Generated text response
        hidden_states: List of layer activations (num_layers, seq_len, hidden_dim)
        attentions: List of attention weights (num_layers, num_heads, seq_len, seq_len)
        d_eff_by_layer: Effective dimensionality per layer
        beta_by_layer: Collapse indicator per layer
        attention_entropy_by_layer: Information flow per layer
        layer_norms: L2 norm of representations per layer
        token_logprobs: Log probabilities for generated tokens
        token_entropy_trajectory: Per-token prediction entropy (model confidence)
        mean_token_entropy: Average prediction entropy across all tokens
        early_token_entropy: Average entropy for first 10 tokens
        late_token_entropy: Average entropy for last 10 tokens
        generation_time: Inference time in seconds
    """
    text: str
    hidden_states: List[np.ndarray]
    attentions: List[np.ndarray]
    d_eff_by_layer: List[float]
    beta_by_layer: List[float]
    attention_entropy_by_layer: List[float]
    layer_norms: List[float]
    token_logprobs: List[float]
    token_entropy_trajectory: List[float]
    mean_token_entropy: float
    early_token_entropy: float
    late_token_entropy: float
    generation_time: float

    def to_dict(self) -> Dict:
        """Convert to JSON-serializable dictionary (excludes large arrays)."""
        return {
            "text": self.text,
            "d_eff_by_layer": self.d_eff_by_layer,
            "beta_by_layer": self.beta_by_layer,
            "attention_entropy_by_layer": self.attention_entropy_by_layer,
            "layer_norms": self.layer_norms,
            "token_logprobs": self.token_logprobs,
            "token_entropy_trajectory": self.token_entropy_trajectory,
            "mean_token_entropy": self.mean_token_entropy,
            "early_token_entropy": self.early_token_entropy,
            "late_token_entropy": self.late_token_entropy,
            "generation_time": self.generation_time,
            # Hidden states and attentions excluded (too large)
            # Save separately with np.savez if needed
        }


class TransformersModelEngine:
    """Diagnostic LLM engine for deep metric capture.

    This engine is SLOWER than vLLM but provides access to internal model state:
    - All layer hidden states
    - All attention weights
    - Conveyance Framework metrics (D_eff, β)
    - Attention flow analysis

    Use for:
    - Phase 2: Analyze 10-20 tutorial examples with memory
    - Phase 3: Prove conveyance metrics predict reasoning success
    - Phase 4: Compare BDH vs. standard transformer architectures

    Do NOT use for:
    - Baseline testing (use vLLMClient - 10x faster)
    - Large-scale experiments (>50 samples)
    """

    def __init__(
        self,
        model_id: str,
        device: str = "cuda",
        load_in_8bit: bool = False,
        load_in_4bit: bool = False,
        torch_dtype: str = "bfloat16",
        device_map: Optional[str] = None,
    ):
        """Initialize diagnostic engine.

        Args:
            model_id: HuggingFace model ID (e.g., "Qwen/Qwen2.5-7B-Instruct")
            device: Device to load model on ("cuda" or "cpu")
            load_in_8bit: Use 8-bit quantization (faster, less memory, less accurate metrics)
            load_in_4bit: Use 4-bit quantization (even less memory, slower, less accurate)
            torch_dtype: Torch dtype for model weights ("bfloat16", "float16", "float32")
            device_map: Device map for multi-GPU (None = auto, "auto" = balanced)

        Raises:
            ImportError: If transformers not installed
            ValueError: If model_id not found
        """
        if not TRANSFORMERS_AVAILABLE:
            raise ImportError(
                "transformers not installed. Install with: poetry add transformers torch"
            )

        self.model_id = model_id
        self.device = device

        # Convert dtype string to torch dtype
        dtype_map = {
            "bfloat16": torch.bfloat16,
            "float16": torch.float16,
            "float32": torch.float32,
        }
        dtype = dtype_map.get(torch_dtype, torch.bfloat16)

        print(f"[TransformersEngine] Loading model: {model_id}")
        quant_str = "4-bit" if load_in_4bit else ("8-bit" if load_in_8bit else "full precision")
        print(f"[TransformersEngine] Device: {device}, Dtype: {torch_dtype}, Quantization: {quant_str}")

        # Load tokenizer
        self.tokenizer = AutoTokenizer.from_pretrained(
            model_id,
            trust_remote_code=True
        )

        # Ensure pad token exists (needed for batch generation)
        if self.tokenizer.pad_token is None:
            self.tokenizer.pad_token = self.tokenizer.eos_token

        # Load model with diagnostic outputs enabled
        # Note: When using quantization, don't specify dtype (causes conflict)
        from transformers import BitsAndBytesConfig

        model_kwargs = {
            "device_map": device_map or device,
            "trust_remote_code": True,
            "output_hidden_states": True,
            "output_attentions": True,
        }

        # Add quantization options (8-bit or 4-bit) using BitsAndBytesConfig
        if load_in_4bit:
            quantization_config = BitsAndBytesConfig(
                load_in_4bit=True,
                bnb_4bit_compute_dtype=dtype,
                bnb_4bit_use_double_quant=True,
                bnb_4bit_quant_type="nf4"
            )
            model_kwargs["quantization_config"] = quantization_config
        elif load_in_8bit:
            quantization_config = BitsAndBytesConfig(
                load_in_8bit=True,
                llm_int8_enable_fp32_cpu_offload=True,  # Allow CPU offloading for large models
            )
            model_kwargs["quantization_config"] = quantization_config
        else:
            # Only add dtype if NOT using quantization (they conflict)
            model_kwargs["dtype"] = dtype

        self.model = AutoModelForCausalLM.from_pretrained(model_id, **model_kwargs)

        self.model.eval()  # Inference mode
        print(f"[TransformersEngine] Model loaded successfully")
        print(f"[TransformersEngine] Num layers: {self.model.config.num_hidden_layers}")
        print(f"[TransformersEngine] Hidden dim: {self.model.config.hidden_size}")

    def inference_with_diagnostics(
        self,
        prompt: str,
        max_tokens: int = 512,
        temperature: float = 0.7,
        top_p: float = 0.9,
    ) -> DiagnosticResult:
        """Run inference and capture all internal metrics.

        Args:
            prompt: Input prompt
            max_tokens: Maximum tokens to generate
            temperature: Sampling temperature (0.0 = greedy)
            top_p: Nucleus sampling threshold

        Returns:
            DiagnosticResult with text, metrics, and internal state

        Example:
            >>> result = engine.inference_with_diagnostics("What is 2+2?")
            >>> print(f"Response: {result.text}")
            >>> print(f"D_eff (layer 0): {result.d_eff_by_layer[0]:.2f}")
            >>> print(f"β (layer 0): {result.beta_by_layer[0]:.2f}")
        """
        import time
        start_time = time.time()

        # Tokenize input
        inputs = self.tokenizer(
            prompt,
            return_tensors="pt",
            padding=True,
            truncation=True,
        ).to(self.model.device)

        # Generate with full diagnostics
        with torch.no_grad():
            outputs = self.model.generate(
                **inputs,
                max_new_tokens=max_tokens,
                temperature=temperature,
                top_p=top_p,
                do_sample=temperature > 0.0,
                # CRITICAL: Capture internal state
                output_hidden_states=True,
                output_attentions=True,
                output_scores=True,  # Logits per token
                return_dict_in_generate=True,
            )

        generation_time = time.time() - start_time

        # Decode generated text
        # Note: We configure return_dict_in_generate=True so outputs has these attrs
        generated_ids = outputs.sequences[0][inputs.input_ids.shape[1]:]  # type: ignore[union-attr]
        text = self.tokenizer.decode(generated_ids, skip_special_tokens=True)

        # Extract token logprobs AND prediction entropy (the CORRECT entropy)
        (token_logprobs, token_entropy_trajectory,
         mean_token_entropy, early_token_entropy, late_token_entropy) = \
            self._extract_token_logprobs_and_entropy(outputs.scores)  # type: ignore[union-attr]

        # Extract and analyze hidden states
        hidden_states = self._extract_hidden_states(outputs.hidden_states)  # type: ignore[union-attr]
        d_eff_by_layer = self._compute_d_eff_by_layer(hidden_states)
        beta_by_layer = self._compute_beta_by_layer(hidden_states)
        layer_norms = self._compute_layer_norms(hidden_states)

        # Extract and analyze attention patterns
        attentions = self._extract_attentions(outputs.attentions)  # type: ignore[union-attr]
        attention_entropy_by_layer = self._compute_attention_entropy(attentions)

        return DiagnosticResult(
            text=text,
            hidden_states=hidden_states,
            attentions=attentions,
            d_eff_by_layer=d_eff_by_layer,
            beta_by_layer=beta_by_layer,
            attention_entropy_by_layer=attention_entropy_by_layer,
            layer_norms=layer_norms,
            token_logprobs=token_logprobs,
            token_entropy_trajectory=token_entropy_trajectory,
            mean_token_entropy=mean_token_entropy,
            early_token_entropy=early_token_entropy,
            late_token_entropy=late_token_entropy,
            generation_time=generation_time,
        )

    def _extract_hidden_states(
        self,
        hidden_states_tuple: Tuple
    ) -> List[np.ndarray]:
        """Extract hidden states from generation output.

        Args:
            hidden_states_tuple: Tuple of (step, layer, batch, seq, hidden_dim)

        Returns:
            List of arrays per layer: [layer_0, layer_1, ...]
            Each array shape: (num_generated_tokens, hidden_dim)
        """
        if not hidden_states_tuple:
            return []

        num_layers = len(hidden_states_tuple[0])
        num_steps = len(hidden_states_tuple)

        # Organize by layer
        layer_states: list[list[np.ndarray]] = [[] for _ in range(num_layers)]

        for step_states in hidden_states_tuple:
            for layer_idx, layer_state in enumerate(step_states):
                # layer_state shape: (batch=1, seq_len, hidden_dim)
                # Take last token of sequence (newly generated token)
                # Convert to float32 before numpy (bfloat16 not supported by numpy)
                token_state: np.ndarray = layer_state[0, -1, :].cpu().float().numpy()
                layer_states[layer_idx].append(token_state)

        # Convert to arrays
        return [np.array(states) for states in layer_states]

    def _extract_attentions(
        self,
        attentions_tuple: Tuple
    ) -> List[np.ndarray]:
        """Extract attention weights from generation output.

        Args:
            attentions_tuple: Tuple of (step, layer, batch, num_heads, seq, seq)

        Returns:
            List of arrays per layer: [layer_0, layer_1, ...]
            Each array shape: (num_generated_tokens, num_heads, seq_len, seq_len)
        """
        if not attentions_tuple:
            return []

        num_layers = len(attentions_tuple[0])
        layer_attentions: list[list[np.ndarray]] = [[] for _ in range(num_layers)]

        for step_attns in attentions_tuple:
            for layer_idx, layer_attn in enumerate(step_attns):
                # layer_attn shape: (batch=1, num_heads, seq_len, seq_len)
                # Convert to float32 before numpy (bfloat16 not supported by numpy)
                attn: np.ndarray = layer_attn[0].cpu().float().numpy()
                layer_attentions[layer_idx].append(attn)

        # Stack each layer's attentions into a single array
        return [np.array(attns) for attns in layer_attentions]

    def _extract_token_logprobs_and_entropy(self, scores: Tuple) -> Tuple[List[float], List[float], float, float, float]:
        """Extract log probabilities AND prediction entropy for generated tokens.

        This computes the CORRECT entropy - uncertainty over vocabulary at each generation step.

        Args:
            scores: Tuple of logits per generation step

        Returns:
            Tuple of:
            - token_logprobs: Log probabilities of chosen tokens
            - token_entropy_trajectory: Per-token prediction entropy (model confidence)
            - mean_token_entropy: Average entropy across all tokens
            - early_token_entropy: Average entropy for first 10 tokens
            - late_token_entropy: Average entropy for last 10 tokens
        """
        if not scores:
            return [], [], 0.0, 0.0, 0.0

        logprobs = []
        entropies = []

        from scipy.stats import entropy as scipy_entropy

        for step_logits in scores:
            # step_logits shape: (batch=1, vocab_size)
            logits = step_logits[0]  # (vocab_size,)

            # Convert to probability distribution
            probs = torch.softmax(logits, dim=-1)

            # Log probability of chosen token (for compatibility)
            chosen_token = probs.argmax()
            logprob = torch.log(probs[chosen_token]).item()
            logprobs.append(logprob)

            # CORRECT ENTROPY: Shannon entropy over vocabulary distribution
            # H = -Σ(p_i * log(p_i)) for i in vocab_size
            # Measures: How confident is the model in its prediction?
            probs_np = probs.cpu().numpy()
            entropy_val = scipy_entropy(probs_np + 1e-10)  # Add small constant to avoid log(0)
            entropies.append(float(entropy_val))

        entropies_array = np.array(entropies)
        mean_entropy = float(np.mean(entropies_array))

        # Early vs late entropy (first/last 10 tokens)
        if len(entropies) >= 10:
            early_entropy = float(np.mean(entropies_array[:10]))
            late_entropy = float(np.mean(entropies_array[-10:]))
        else:
            early_entropy = mean_entropy
            late_entropy = mean_entropy

        return logprobs, entropies, mean_entropy, early_entropy, late_entropy

    def _compute_d_eff_by_layer(
        self,
        hidden_states: List[np.ndarray],
        variance_threshold: float = 0.90
    ) -> List[float]:
        """Compute effective dimensionality (D_eff) per layer via PCA.

        D_eff measures semantic richness of representations.
        Higher D_eff = richer, more structured representations.

        Args:
            hidden_states: List of layer states (num_tokens, hidden_dim)
            variance_threshold: Variance explained threshold for D_eff

        Returns:
            List of D_eff values per layer
        """
        d_eff_values = []

        for layer_states in hidden_states:
            if len(layer_states) < 2:
                d_eff_values.append(0.0)
                continue

            # Center data
            centered = layer_states - layer_states.mean(axis=0)

            # Compute covariance matrix
            cov = np.cov(centered.T)

            # Eigendecomposition
            eigenvalues = np.linalg.eigh(cov)[0][::-1]

            # Cumulative variance explained
            cumsum = np.cumsum(eigenvalues)
            total_variance = cumsum[-1]

            if total_variance == 0:
                d_eff_values.append(0.0)
                continue

            # Count dimensions needed for 90% variance
            eff_dims = np.sum(cumsum < variance_threshold * total_variance) + 1
            d_eff_values.append(float(eff_dims))

        return d_eff_values

    def _compute_beta_by_layer(
        self,
        hidden_states: List[np.ndarray]
    ) -> List[float]:
        """Compute collapse indicator (β) per layer.

        β = mean(distances) / std(distances)

        Lower β = well-distributed representations (good generalization)
        Higher β = collapsed representations (overfitting)

        Target: β < 1.8 (excellent), β < 2.0 (good)

        Args:
            hidden_states: List of layer states (num_tokens, hidden_dim)

        Returns:
            List of β values per layer
        """
        beta_values = []

        for layer_states in hidden_states:
            if len(layer_states) < 2:
                beta_values.append(0.0)
                continue

            # Compute pairwise Euclidean distances
            distances = pdist(layer_states, metric='euclidean')

            if len(distances) == 0 or distances.std() == 0:
                beta_values.append(0.0)
                continue

            beta = distances.mean() / distances.std()
            beta_values.append(float(beta))

        return beta_values

    def _compute_layer_norms(
        self,
        hidden_states: List[np.ndarray]
    ) -> List[float]:
        """Compute mean L2 norm of representations per layer.

        Args:
            hidden_states: List of layer states

        Returns:
            List of mean L2 norms per layer
        """
        norms = []
        for layer_states in hidden_states:
            if len(layer_states) == 0:
                norms.append(0.0)
                continue

            layer_norm = np.linalg.norm(layer_states, axis=1).mean()
            norms.append(float(layer_norm))

        return norms

    def _compute_attention_entropy(
        self,
        attentions: List[np.ndarray]
    ) -> List[float]:
        """Compute attention entropy per layer (averaged over heads).

        High entropy = diffuse attention (uncertainty/exploration)
        Low entropy = focused attention (confidence/exploitation)

        Args:
            attentions: List of attention weights per layer

        Returns:
            List of mean attention entropy per layer
        """
        entropies = []

        for layer_attns in attentions:
            if len(layer_attns) == 0:
                entropies.append(0.0)
                continue

            # layer_attns shape: (num_tokens, num_heads, seq_len, seq_len)
            # Compute entropy over last dimension (attention distribution)

            layer_entropy_values = []
            for token_attns in layer_attns:
                # token_attns shape: (num_heads, seq_len, seq_len)
                for head_idx in range(token_attns.shape[0]):
                    attn_dist = token_attns[head_idx, -1, :]  # Last query attends to all keys

                    # Shannon entropy: -sum(p * log(p))
                    attn_dist = attn_dist + 1e-10  # Avoid log(0)
                    entropy = -np.sum(attn_dist * np.log(attn_dist))
                    layer_entropy_values.append(entropy)

            mean_entropy = np.mean(layer_entropy_values)
            entropies.append(float(mean_entropy))

        return entropies

    def chat(
        self,
        messages: List[Dict[str, str]],
        max_tokens: int = 512,
        temperature: float = 0.7,
    ) -> str:
        """Simple chat interface (compatible with vLLMClient API).

        Use this for drop-in compatibility with existing code.
        Use inference_with_diagnostics() for full metrics.

        Args:
            messages: Chat messages [{"role": "user", "content": "..."}]
            max_tokens: Max tokens to generate
            temperature: Sampling temperature

        Returns:
            Generated text response
        """
        # Format messages into prompt
        prompt = self._format_messages(messages)

        # Generate
        result = self.inference_with_diagnostics(
            prompt=prompt,
            max_tokens=max_tokens,
            temperature=temperature,
        )

        return result.text

    def _format_messages(self, messages: List[Dict[str, str]]) -> str:
        """Format chat messages into single prompt string.

        Args:
            messages: List of message dicts with role/content

        Returns:
            Formatted prompt string
        """
        # Try to use tokenizer's chat template if available
        if hasattr(self.tokenizer, "apply_chat_template"):
            try:
                result = self.tokenizer.apply_chat_template(
                    messages,
                    tokenize=False,
                    add_generation_prompt=True
                )
                return str(result)
            except Exception:
                pass

        # Fallback: Simple formatting
        prompt_parts = []
        for msg in messages:
            role = msg["role"]
            content = msg["content"]
            if role == "system":
                prompt_parts.append(f"System: {content}")
            elif role == "user":
                prompt_parts.append(f"User: {content}")
            elif role == "assistant":
                prompt_parts.append(f"Assistant: {content}")

        prompt_parts.append("Assistant:")
        return "\n\n".join(prompt_parts)
