"""Initial design (Sobol sequence) for BO warm-start."""

import torch
from scipy.stats.qmc import Sobol


def sobol_design(n_points: int, dim: int, seed: int = 0) -> torch.Tensor:
    """Generate Sobol quasi-random initial samples in [0,1]^d.

    Args:
        n_points: Number of initial points.
        dim: Dimensionality of the search space.
        seed: Random seed for reproducibility.

    Returns:
        Tensor of shape (n_points, dim) in [0, 1]^d.
    """
    sampler = Sobol(d=dim, scramble=True, seed=seed)
    samples = sampler.random(n=n_points)
    return torch.tensor(samples, dtype=torch.float64)
