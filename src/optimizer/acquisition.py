"""Acquisition function wrappers for BoTorch."""

import torch
from botorch.acquisition import ExpectedImprovement, UpperConfidenceBound, ProbabilityOfImprovement
from botorch.models import SingleTaskGP


def get_acquisition(
    name: str,
    model: SingleTaskGP,
    best_f: float,
    beta: float = 2.0,
):
    """Create an acquisition function instance.

    Args:
        name: One of 'EI', 'UCB', 'PI'.
        model: Fitted GP model.
        best_f: Best observed value so far.
        beta: UCB exploration-exploitation parameter.

    Returns:
        BoTorch acquisition function object.
    """
    if name == "EI":
        return ExpectedImprovement(model=model, best_f=best_f)
    elif name == "UCB":
        return UpperConfidenceBound(model=model, beta=beta)
    elif name == "PI":
        return ProbabilityOfImprovement(model=model, best_f=best_f)
    else:
        raise ValueError(f"Unknown acquisition function: {name}")
