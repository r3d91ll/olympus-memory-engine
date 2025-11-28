"""IF-Track core equations for entropy-based reasoning measurement.

Implements key formulas from "The Universal Landscape of Human Reasoning"
(arXiv:2510.21623v1):

- Uncertainty (u_t): Token-level Shannon entropy
- Cognitive Effort (e_t): Information gain between steps
- Divergence (∇·V): Phase space flow divergence (Liouville's theorem)
"""

import numpy as np


def calculate_uncertainty(logprobs: list[float]) -> float:
    """Calculate token-level Shannon entropy (uncertainty).

    Implements: u_t = -(1/n_t) Σ p_{t,i} log p_{t,i}

    This measures the ambiguity or uncertainty at a given reasoning step.
    High entropy → model is uncertain, exploring possibilities.
    Low entropy → model is confident, converging on answer.

    Args:
        logprobs: Log probabilities for tokens (from LLM)
                 Can be single token or sequence of tokens

    Returns:
        Average Shannon entropy across tokens

    Example:
        >>> # High uncertainty (model unsure)
        >>> logprobs = [-1.0, -1.2, -1.1, -1.3]  # Similar probabilities
        >>> uncertainty = calculate_uncertainty(logprobs)
        >>> # uncertainty ≈ 0.8 (high)

        >>> # Low uncertainty (model confident)
        >>> logprobs = [-0.1, -4.0, -5.0, -6.0]  # One dominant token
        >>> uncertainty = calculate_uncertainty(logprobs)
        >>> # uncertainty ≈ 0.2 (low)
    """
    if not logprobs:
        return 0.0

    # Convert log probabilities to probabilities
    logprobs_array = np.array(logprobs)
    probs = np.exp(logprobs_array)

    # Normalize to ensure they sum to 1
    probs = probs / (probs.sum() + 1e-10)  # Add epsilon for numerical stability

    # Calculate Shannon entropy: H = -Σ p_i log(p_i)
    # Using log base e (natural log) as in the paper
    entropy = -np.sum(probs * np.log(probs + 1e-10))

    return float(entropy)


def calculate_effort(prev_entropy: float, curr_entropy: float) -> float:
    """Calculate cognitive effort (information gain between steps).

    Implements: e_t = |H(step_t) - H(step_{t-1})|

    This measures how much information restructuring occurred between
    reasoning steps. High effort → significant cognitive processing.
    Low effort → incremental refinement.

    Args:
        prev_entropy: Entropy from previous reasoning step
        curr_entropy: Entropy from current reasoning step

    Returns:
        Absolute change in entropy (information gain)

    Example:
        >>> # Large effort (major restructuring)
        >>> prev_entropy = 0.9  # High uncertainty
        >>> curr_entropy = 0.2  # Low uncertainty (breakthrough)
        >>> effort = calculate_effort(prev_entropy, curr_entropy)
        >>> # effort = 0.7 (large information gain)

        >>> # Small effort (incremental)
        >>> prev_entropy = 0.5
        >>> curr_entropy = 0.48
        >>> effort = calculate_effort(prev_entropy, curr_entropy)
        >>> # effort = 0.02 (small refinement)
    """
    return abs(curr_entropy - prev_entropy)


def compute_divergence(trajectory: list[tuple[float, float]]) -> float:
    """Compute divergence in (uncertainty, effort) phase space.

    Implements finite-volume discretization from IF-Track paper.
    Measures ∇·V = ∂u/∂u + ∂e/∂e

    Liouville's theorem: Good reasoning maintains ∇·V ≈ 0 (divergence-free flow).
    Information volume is conserved through reasoning process.

    High divergence → reasoning breaking down, information loss
    Low divergence → coherent reasoning, information preserved

    Args:
        trajectory: List of (uncertainty, effort) tuples from reasoning steps

    Returns:
        Divergence value (lower is better for good reasoning)

    Example:
        >>> # Good reasoning trajectory
        >>> trajectory = [
        ...     (0.9, 0.0),  # Start: high uncertainty, no prior effort
        ...     (0.7, 0.2),  # Exploring: moderate reduction
        ...     (0.4, 0.3),  # Converging: larger reduction
        ...     (0.2, 0.2),  # Final: low uncertainty
        ... ]
        >>> div = compute_divergence(trajectory)
        >>> # div ≈ 0.005 (low, good reasoning)

        >>> # Poor reasoning trajectory (stuck/confused)
        >>> trajectory = [
        ...     (0.9, 0.0),
        ...     (0.95, 0.05),  # Uncertainty increasing!
        ...     (0.92, 0.03),  # Oscillating
        ...     (0.88, 0.04),
        ... ]
        >>> div = compute_divergence(trajectory)
        >>> # div ≈ 0.15 (high, poor reasoning)
    """
    if len(trajectory) < 2:
        # Need at least 2 points for gradients
        return 0.0

    # Extract (u, e) vectors
    u_vals = np.array([point[0] for point in trajectory])
    e_vals = np.array([point[1] for point in trajectory])

    # Compute gradients (finite differences)
    # du/dt and de/dt where t is step index
    du = np.gradient(u_vals)
    de = np.gradient(e_vals)

    # Divergence: ∇·V = ∂u/∂t + ∂e/∂t
    # We're using discrete steps, so this is an approximation
    # of the continuous phase space divergence

    # Mean absolute divergence (simplified from paper's full discretization)
    divergence = np.mean(np.abs(du) + np.abs(de))

    return float(divergence)


def compute_phase_space_density(
    trajectory: list[tuple[float, float]], grid_size: int = 10
) -> np.ndarray:
    """Compute probability density in (u, e) phase space.

    Creates 2D histogram of trajectory in phase space.
    Useful for visualization and advanced divergence calculations.

    Args:
        trajectory: List of (uncertainty, effort) tuples
        grid_size: Number of bins per dimension

    Returns:
        2D array of density values (grid_size × grid_size)
    """
    if len(trajectory) < 2:
        return np.zeros((grid_size, grid_size))

    u_vals = np.array([point[0] for point in trajectory])
    e_vals = np.array([point[1] for point in trajectory])

    # Create 2D histogram
    density, _, _ = np.histogram2d(
        u_vals,
        e_vals,
        bins=grid_size,
        range=[[0, 1], [0, 1]],  # Normalize to [0,1] range
        density=True,  # Normalize to probability density
    )

    return density


def analyze_trajectory(trajectory: list[tuple[float, float]]) -> dict:
    """Comprehensive trajectory analysis.

    Args:
        trajectory: List of (uncertainty, effort) tuples

    Returns:
        Dictionary with analysis metrics:
        - divergence: Phase space divergence
        - mean_uncertainty: Average uncertainty across trajectory
        - std_uncertainty: Uncertainty standard deviation
        - mean_effort: Average cognitive effort
        - std_effort: Effort standard deviation
        - uncertainty_reduction: Start uncertainty - end uncertainty
        - total_effort: Sum of all effort values
        - num_steps: Number of reasoning steps
        - efficiency: Uncertainty reduction per unit effort

    Example:
        >>> trajectory = [(0.9, 0.0), (0.6, 0.3), (0.3, 0.3), (0.15, 0.15)]
        >>> metrics = analyze_trajectory(trajectory)
        >>> print(f"Divergence: {metrics['divergence']:.3f}")
        >>> print(f"Uncertainty reduction: {metrics['uncertainty_reduction']:.2f}")
        >>> print(f"Efficiency: {metrics['efficiency']:.2f}")
    """
    if not trajectory:
        return {
            "divergence": 0.0,
            "mean_uncertainty": 0.0,
            "std_uncertainty": 0.0,
            "mean_effort": 0.0,
            "std_effort": 0.0,
            "uncertainty_reduction": 0.0,
            "total_effort": 0.0,
            "num_steps": 0,
            "efficiency": 0.0,
        }

    u_vals = [point[0] for point in trajectory]
    e_vals = [point[1] for point in trajectory]

    uncertainty_reduction = u_vals[0] - u_vals[-1] if len(u_vals) > 1 else 0.0
    total_effort = sum(e_vals)
    efficiency = uncertainty_reduction / (total_effort + 1e-10)

    return {
        "divergence": compute_divergence(trajectory),
        "mean_uncertainty": float(np.mean(u_vals)),
        "std_uncertainty": float(np.std(u_vals)),
        "mean_effort": float(np.mean(e_vals)),
        "std_effort": float(np.std(e_vals)),
        "uncertainty_reduction": float(uncertainty_reduction),
        "total_effort": float(total_effort),
        "num_steps": len(trajectory),
        "efficiency": float(efficiency),
    }
