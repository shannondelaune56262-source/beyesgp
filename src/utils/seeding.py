"""Centralized random seed management for reproducibility."""

import random
import numpy as np


def seed_all(seed: int) -> None:
    """Set random seeds for all libraries used in the project.

    Args:
        seed: Master random seed.
    """
    random.seed(seed)
    np.random.seed(seed)
    try:
        import torch
        torch.manual_seed(seed)
        if torch.cuda.is_available():
            torch.cuda.manual_seed_all(seed)
    except ImportError:
        pass


def derive_seeds(master_seed: int, n: int) -> list[int]:
    """Derive n independent seeds from a master seed.

    Uses numpy's SeedSequence for reproducible derivation.
    """
    rng = np.random.SeedSequence(master_seed)
    child_seeds = rng.spawn(n)
    return [int(s.generate_state(1)[0]) for s in child_seeds]
