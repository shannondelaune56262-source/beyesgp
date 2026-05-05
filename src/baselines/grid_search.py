"""Grid search baseline (low-dimensional only)."""

import logging
from itertools import product

import numpy as np

logger = logging.getLogger(__name__)


class GridSearch:
    """Exhaustive grid search. Only practical for <=3 dimensions."""

    def __init__(
        self,
        objective_fn,
        dim: int,
        points_per_dim: int = 20,
    ):
        self.objective_fn = objective_fn
        self.dim = dim
        self.points_per_dim = points_per_dim

    def optimize(self) -> tuple[np.ndarray, float]:
        grid_1d = np.linspace(0, 1, self.points_per_dim)
        grid_points = np.array(list(product(grid_1d, repeat=self.dim)))

        logger.info(
            f"Grid search: {len(grid_points)} points "
            f"({self.points_per_dim}^{self.dim})"
        )

        best_x, best_y = None, -np.inf
        results = []
        convergence = []

        for i, x in enumerate(grid_points):
            y = self.objective_fn(x)
            results.append((x.copy(), y))
            if y > best_y:
                best_x, best_y = x.copy(), y
            convergence.append(best_y)

        self._results = results
        self._convergence = np.array(convergence)
        self._grid = grid_points

        logger.info(f"Grid search done. Best severity={best_y:.4f}")
        return best_x, best_y

    def get_convergence(self) -> np.ndarray:
        return self._convergence

    def get_severity_grid(self) -> tuple[np.ndarray, np.ndarray]:
        """Return grid points and their severity values (for heatmap)."""
        X = np.array([r[0] for r in self._results])
        y = np.array([r[1] for r in self._results])
        return X, y
