"""Gaussian Process surrogate model configuration."""

import gpytorch
import torch
from botorch.models import SingleTaskGP
from botorch.models.transforms import Normalize, Standardize
from gpytorch.kernels import MaternKernel, RBFKernel, ScaleKernel
from gpytorch.means import ConstantMean
from gpytorch.priors import GammaPrior


def build_gp(
    train_X: torch.Tensor,
    train_Y: torch.Tensor,
    kernel: str = "matern52",
    ard: bool = True,
) -> SingleTaskGP:
    """Build and return a configured GP model.

    Args:
        train_X: Training inputs, shape (n, d).
        train_Y: Training targets, shape (n, 1).
        kernel: Kernel type ('matern52', 'matern32', 'rbf').
        ard: Whether to use Automatic Relevance Determination.

    Returns:
        Configured SingleTaskGP model (not yet fitted).
    """
    d = train_X.shape[-1]

    # Select kernel
    if kernel == "matern52":
        base_kernel = MaternKernel(
            nu=2.5,
            ard_num_dims=d if ard else None,
            lengthscale_prior=GammaPrior(3.0, 6.0),
        )
    elif kernel == "matern32":
        base_kernel = MaternKernel(
            nu=1.5,
            ard_num_dims=d if ard else None,
            lengthscale_prior=GammaPrior(3.0, 6.0),
        )
    elif kernel == "rbf":
        base_kernel = RBFKernel(
            ard_num_dims=d if ard else None,
            lengthscale_prior=GammaPrior(3.0, 6.0),
        )
    else:
        raise ValueError(f"Unknown kernel: {kernel}")

    covar_module = ScaleKernel(base_kernel)

    model = SingleTaskGP(
        train_X=train_X,
        train_Y=train_Y,
        input_transform=Normalize(d=d),
        outcome_transform=Standardize(m=1),
        covar_module=covar_module,
    )

    return model
