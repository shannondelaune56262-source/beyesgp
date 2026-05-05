"""Main Bayesian Optimization loop for worst-case scenario search.

Implements the BO-WCS algorithm: iteratively fits a GP surrogate model,
optimizes an acquisition function, evaluates the next point via ANDES
simulation, and updates the dataset.
"""

import logging
import time
from typing import Callable

import numpy as np
import torch
from botorch.fit import fit_gpytorch_mll
from botorch.optim import optimize_acqf
from gpytorch.mlls import ExactMarginalLogLikelihood

from src.optimizer.acquisition import get_acquisition
from src.optimizer.gp_model import build_gp
from src.optimizer.initial_design import sobol_design

logger = logging.getLogger(__name__)


class BayesianOptimizer:
    """Bayesian Optimization for worst-case scenario search.

    Maximizes the severity function f(x) over x in [0,1]^d.
    """

    def __init__(
        self,
        objective_fn: Callable[[np.ndarray], float],
        dim: int,
        n_init: int = 15,
        n_iter: int = 60,
        acquisition: str = "EI",
        kernel: str = "matern52",
        ard: bool = True,
        num_restarts: int = 20,
        raw_samples: int = 100,
        seed: int = 42,
    ):
        self.objective_fn = objective_fn
        self.dim = dim
        self.n_init = n_init
        self.n_iter = n_iter
        self.acquisition = acquisition
        self.kernel = kernel
        self.ard = ard
        self.num_restarts = num_restarts
        self.raw_samples = raw_samples
        self.seed = seed

        # Will be populated during optimization
        self.X_observed: list[np.ndarray] = []
        self.y_observed: list[float] = []
        self.convergence: list[float] = []

    def optimize(self) -> tuple[np.ndarray, float]:
        """Run the full BO loop.

        Returns:
            (best_x, best_y) - the worst-case scenario and its severity.
        """
        torch.manual_seed(self.seed)

        # Phase 1: Initial design via Sobol
        logger.info(f"Generating {self.n_init} Sobol initial samples (dim={self.dim})")
        X_init = sobol_design(self.n_init, self.dim, seed=self.seed)

        for i in range(self.n_init):
            x_np = X_init[i].numpy()
            y = self.objective_fn(x_np)
            self.X_observed.append(x_np)
            self.y_observed.append(y)
            self._update_convergence()
            logger.info(
                f"Init [{i+1}/{self.n_init}] severity={y:.4f} "
                f"best_so_far={self.convergence[-1]:.4f}"
            )

        # Phase 2: Sequential BO iterations
        for t in range(self.n_iter):
            t_start = time.time()
            x_next, acq_value = self._suggest_next()
            y_next = self.objective_fn(x_next)
            self.X_observed.append(x_next)
            self.y_observed.append(y_next)
            self._update_convergence()
            elapsed = time.time() - t_start
            logger.info(
                f"BO iter [{t+1}/{self.n_iter}] severity={y_next:.4f} "
                f"best_so_far={self.convergence[-1]:.4f} "
                f"acq={acq_value:.4f} time={elapsed:.1f}s"
            )

        # Return best observed
        best_idx = int(np.argmax(self.y_observed))
        best_x = self.X_observed[best_idx]
        best_y = self.y_observed[best_idx]

        logger.info(f"BO complete. Best severity={best_y:.4f} at iteration {best_idx}")
        return best_x, best_y

    def _suggest_next(self) -> tuple[np.ndarray, float]:
        """Fit GP and optimize acquisition to suggest next evaluation point."""
        X = torch.tensor(
            np.array(self.X_observed), dtype=torch.float64
        )
        Y = torch.tensor(
            np.array(self.y_observed), dtype=torch.float64
        ).unsqueeze(-1)

        # Build and fit GP
        gp = build_gp(X, Y, kernel=self.kernel, ard=self.ard)
        mll = ExactMarginalLogLikelihood(gp.likelihood, gp)
        fit_gpytorch_mll(mll)

        # Create acquisition function
        best_f = float(Y.max())
        acq_fn = get_acquisition(self.acquisition, gp, best_f)

        # Optimize acquisition
        bounds = torch.stack([
            torch.zeros(self.dim, dtype=torch.float64),
            torch.ones(self.dim, dtype=torch.float64),
        ])

        candidates, acq_values = optimize_acqf(
            acq_function=acq_fn,
            bounds=bounds,
            q=1,
            num_restarts=self.num_restarts,
            raw_samples=self.raw_samples,
        )

        x_next = candidates[0].detach().numpy()
        acq_val = acq_values.item() if acq_values.dim() == 0 else float(acq_values[0])
        return x_next, acq_val

    def _update_convergence(self) -> None:
        """Record best observed severity so far."""
        self.convergence.append(float(np.max(self.y_observed)))

    def get_history(self) -> dict:
        """Return full optimization history."""
        return {
            "X": np.array(self.X_observed),
            "y": np.array(self.y_observed),
            "convergence": np.array(self.convergence),
            "n_evaluations": len(self.y_observed),
        }

    def get_convergence(self) -> np.ndarray:
        """Return convergence history as array."""
        return np.array(self.convergence)
