"""Random search baseline."""

import logging

import numpy as np

logger = logging.getLogger(__name__)


class RandomSearch:
    """Uniform random sampling baseline."""

    def __init__(
        self,
        objective_fn,
        dim: int,
        n_evaluations: int,
        seed: int = 42,
    ):
        self.objective_fn = objective_fn
        self.dim = dim
        self.n_evaluations = n_evaluations
        self.seed = seed

    def optimize(self) -> tuple[np.ndarray, float]:
        rng = np.random.RandomState(self.seed)
        best_x, best_y = None, -np.inf
        convergence = []

        for i in range(self.n_evaluations):
            x = rng.uniform(0, 1, size=self.dim)
            y = self.objective_fn(x)

            if y > best_y:
                best_x, best_y = x.copy(), y

            convergence.append(best_y)
            if (i + 1) % 10 == 0:
                logger.info(
                    f"Random [{i+1}/{self.n_evaluations}] "
                    f"severity={y:.4f} best={best_y:.4f}"
                )

        self._convergence = np.array(convergence)
        logger.info(f"Random search done. Best severity={best_y:.4f}")
        return best_x, best_y

    def get_convergence(self) -> np.ndarray:
        return self._convergence


class LatinHypercubeSearch:
    """One-shot Latin Hypercube Sampling baseline."""

    def __init__(
        self,
        objective_fn,
        dim: int,
        n_evaluations: int,
        seed: int = 42,
    ):
        self.objective_fn = objective_fn
        self.dim = dim
        self.n_evaluations = n_evaluations
        self.seed = seed
        self._convergence = None

    def optimize(self) -> tuple[np.ndarray, float]:
        from scipy.stats.qmc import LatinHypercube

        sampler = LatinHypercube(d=self.dim, seed=self.seed)
        X = sampler.random(n=self.n_evaluations)

        best_x, best_y = None, -np.inf
        convergence = []

        for i in range(self.n_evaluations):
            y = self.objective_fn(X[i])
            if y > best_y:
                best_x, best_y = X[i].copy(), y
            convergence.append(best_y)

        self._convergence = np.array(convergence)
        logger.info(f"LHS done. Best severity={best_y:.4f}")
        return best_x, best_y

    def get_convergence(self) -> np.ndarray:
        return self._convergence
