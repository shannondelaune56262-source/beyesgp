"""Genetic algorithm baseline using pymoo."""

import logging

import numpy as np

logger = logging.getLogger(__name__)


class GeneticAlgorithmBaseline:
    """GA baseline using pymoo for worst-case scenario search."""

    def __init__(
        self,
        objective_fn,
        dim: int,
        n_evaluations: int,
        seed: int = 42,
        pop_size: int = 20,
    ):
        self.objective_fn = objective_fn
        self.dim = dim
        self.n_evaluations = n_evaluations
        self.seed = seed
        self.pop_size = min(pop_size, n_evaluations)
        self._convergence = None

    def optimize(self) -> tuple[np.ndarray, float]:
        from pymoo.algorithms.soo.nonconvex.ga import GA
        from pymoo.core.problem import Problem
        from pymoo.operators.crossover.sbx import SBX
        from pymoo.operators.mutation.pm import PM
        from pymoo.operators.sampling.rnd import FloatRandomSampling
        from pymoo.optimize import minimize
        from pymoo.core.repair import Repair

        class MaximizeProblem(Problem):
            """Wraps our objective as a pymoo minimization problem (negate)."""

            def __init__(self, obj_fn, dim):
                super().__init__(
                    n_var=dim,
                    n_obj=1,
                    xl=np.zeros(dim),
                    xu=np.ones(dim),
                )
                self.obj_fn = obj_fn
                self.history = []
                self._best = -np.inf

            def _evaluate(self, X, out, *args, **kwargs):
                F = np.array([-self.obj_fn(x) for x in X])
                out["F"] = F.reshape(-1, 1)
                # Track convergence
                for f_val in F:
                    current_best = -f_val
                    if current_best > self._best:
                        self._best = current_best
                    self.history.append(self._best)

        problem = MaximizeProblem(self.objective_fn, self.dim)

        algorithm = GA(
            pop_size=self.pop_size,
            sampling=FloatRandomSampling(),
            crossover=SBX(prob=0.9, eta=15),
            mutation=PM(eta=20),
            eliminate_duplicates=True,
        )

        n_gen = max(self.n_evaluations // self.pop_size, 1)

        result = minimize(
            problem,
            algorithm,
            termination=("n_gen", n_gen),
            seed=self.seed,
            verbose=False,
        )

        best_x = result.X
        best_y = -result.F[0]

        self._convergence = np.array(problem.history[:self.n_evaluations])

        logger.info(f"GA done. Best severity={best_y:.4f}")
        return best_x, best_y

    def get_convergence(self) -> np.ndarray:
        return self._convergence
