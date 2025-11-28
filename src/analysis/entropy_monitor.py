"""Entropy monitoring for reasoning trajectory tracking."""

import time
from dataclasses import dataclass, field
from typing import Optional

from src.analysis.if_track import analyze_trajectory, calculate_effort, calculate_uncertainty
from src.llm.client import LLMClient


@dataclass
class ReasoningStep:
    """One step in a reasoning trajectory.

    Captures both the content (prompt/response) and the information-theoretic
    measurements (uncertainty, effort) at this step.
    """

    step_number: int
    """Sequential step number in trajectory"""

    step_type: str
    """Type of reasoning step: 'problem_recognition', 'memory_retrieval',
    'context_integration', 'solution_synthesis', or custom"""

    prompt: str
    """Input prompt for this step"""

    response: str
    """Generated response"""

    logprobs: list[float]
    """Token-level log probabilities from LLM"""

    uncertainty: float
    """Shannon entropy (u_t) - measures ambiguity"""

    effort: float
    """Information gain (e_t) - measures cognitive work"""

    timestamp: float = field(default_factory=time.time)
    """When this step occurred"""

    metadata: dict = field(default_factory=dict)
    """Additional context (model, memory IDs, etc.)"""


class EntropyMonitor:
    """Monitor reasoning quality through entropy analysis.

    Tracks reasoning trajectories in (uncertainty, effort) phase space
    and computes IF-Track metrics (divergence, information flow).

    Usage:
        >>> from src.llm.vllm_client import VLLMClient
        >>> from src.analysis import EntropyMonitor
        >>>
        >>> # Initialize with vLLM (needs logprobs support)
        >>> llm = VLLMClient(model_id="Qwen/Qwen2-VL-7B-Instruct")
        >>> monitor = EntropyMonitor(llm)
        >>>
        >>> # Track reasoning steps
        >>> monitor.measure_step(
        ...     prompt="Solve: 5 + 3 * 2",
        ...     step_type='problem_recognition'
        ... )
        >>> monitor.measure_step(
        ...     prompt="What is 3 * 2?",
        ...     step_type='subproblem'
        ... )
        >>> monitor.measure_step(
        ...     prompt="What is 5 + 6?",
        ...     step_type='final_calculation'
        ... )
        >>>
        >>> # Analyze trajectory
        >>> summary = monitor.get_trajectory_summary()
        >>> print(f"Divergence: {summary['divergence']:.3f}")
        >>> print(f"Uncertainty reduction: {summary['uncertainty_reduction']:.2f}")
    """

    def __init__(self, llm_client: LLMClient):
        """Initialize entropy monitor.

        Args:
            llm_client: LLM client with logprobs support (e.g., VLLMClient)

        Raises:
            ValueError: If client doesn't support logprobs
        """
        self.client = llm_client
        self.trajectory: list[ReasoningStep] = []

        # Check if client supports logprobs
        if not hasattr(self.client, "chat_with_logprobs"):
            raise ValueError(
                f"{type(self.client).__name__} must support chat_with_logprobs() "
                "for entropy measurement. Use VLLMClient."
            )

    def measure_step(
        self,
        prompt: str,
        step_type: str,
        max_tokens: int = 256,
        temperature: float = 0.7,
        metadata: Optional[dict] = None,
    ) -> ReasoningStep:
        """Measure entropy for one reasoning step.

        Args:
            prompt: Input prompt for this step
            step_type: Category of reasoning step
            max_tokens: Maximum tokens to generate
            temperature: Sampling temperature
            metadata: Optional additional context

        Returns:
            ReasoningStep with measurements

        Example:
            >>> step = monitor.measure_step(
            ...     prompt="What is 2 + 2?",
            ...     step_type='arithmetic',
            ...     metadata={'problem_id': 'gsm8k_001'}
            ... )
            >>> print(f"Uncertainty: {step.uncertainty:.3f}")
            >>> print(f"Effort: {step.effort:.3f}")
        """
        # Generate with logprobs
        messages = [{"role": "user", "content": prompt}]
        response = self.client.chat_with_logprobs(
            messages=messages, max_tokens=max_tokens, temperature=temperature
        )

        # Calculate uncertainty (u_t) from token logprobs
        uncertainty = calculate_uncertainty(response.logprobs or [])

        # Calculate effort (e_t) from change in entropy
        effort = 0.0
        if self.trajectory:
            previous_step = self.trajectory[-1]
            effort = calculate_effort(previous_step.uncertainty, uncertainty)

        # Create reasoning step
        step = ReasoningStep(
            step_number=len(self.trajectory),
            step_type=step_type,
            prompt=prompt,
            response=response.text,
            logprobs=response.logprobs or [],
            uncertainty=uncertainty,
            effort=effort,
            timestamp=time.time(),
            metadata=metadata or {},
        )

        self.trajectory.append(step)
        return step

    def get_trajectory(self) -> list[tuple[float, float]]:
        """Get (uncertainty, effort) trajectory for phase space analysis.

        Returns:
            List of (u_t, e_t) tuples
        """
        return [(step.uncertainty, step.effort) for step in self.trajectory]

    def get_trajectory_summary(self) -> dict:
        """Get comprehensive summary statistics for trajectory.

        Returns:
            Dictionary with metrics:
            - num_steps: Number of reasoning steps
            - divergence: Phase space divergence (lower = better)
            - mean_uncertainty: Average uncertainty
            - uncertainty_reduction: Start - end uncertainty
            - total_effort: Sum of all effort values
            - efficiency: Uncertainty reduction per unit effort
            - final_uncertainty: Ending uncertainty (confidence)
            - ... and more (see analyze_trajectory docs)

        Example:
            >>> summary = monitor.get_trajectory_summary()
            >>> if summary['divergence'] < 0.01:
            ...     print("Good reasoning (low divergence)")
            >>> if summary['uncertainty_reduction'] > 0.5:
            ...     print("Significant learning occurred")
        """
        if not self.trajectory:
            return {
                "num_steps": 0,
                "divergence": 0.0,
                "mean_uncertainty": 0.0,
                "final_uncertainty": 0.0,
                "uncertainty_reduction": 0.0,
            }

        trajectory_points = self.get_trajectory()
        metrics = analyze_trajectory(trajectory_points)

        # Add final uncertainty for convenience
        metrics["final_uncertainty"] = self.trajectory[-1].uncertainty

        return metrics

    def reset(self):
        """Clear trajectory for new measurement session."""
        self.trajectory = []

    def export_trajectory(self) -> list[dict]:
        """Export full trajectory as JSON-serializable format.

        Useful for saving to files for later analysis.

        Returns:
            List of step dictionaries with all fields

        Example:
            >>> import json
            >>> trajectory_data = monitor.export_trajectory()
            >>> with open('reasoning_trace.json', 'w') as f:
            ...     json.dump(trajectory_data, f, indent=2)
        """
        return [
            {
                "step_number": step.step_number,
                "step_type": step.step_type,
                "prompt": step.prompt,
                "response": step.response,
                "uncertainty": step.uncertainty,
                "effort": step.effort,
                "timestamp": step.timestamp,
                "metadata": step.metadata,
                # Logprobs can be large, optionally exclude
                # "logprobs": step.logprobs,
            }
            for step in self.trajectory
        ]
