"""Single experiment run orchestration."""

import logging
import time
from pathlib import Path

import numpy as np
import pandas as pd

from src.simulator.andes_wrapper import ANDESWrapper
from src.simulator.scenario_builder import ScenarioBuilder
from src.objective.severity import SeverityCalculator
from src.optimizer.bayesian_opt import BayesianOptimizer
from src.baselines.random_search import RandomSearch, LatinHypercubeSearch
from src.baselines.grid_search import GridSearch
from src.baselines.genetic_algorithm import GeneticAlgorithmBaseline
from src.utils.config import load_config, DictConfig
from src.utils.io import save_results

logger = logging.getLogger(__name__)


class ExperimentRunner:
    """Orchestrates a single experiment (one method, one seed)."""

    def __init__(self, config: DictConfig, method: str, seed: int):
        self.config = config
        self.method = method
        self.seed = seed

        # Extract config values
        self.system_name = self._get_system_name()
        self.space_name = self._get_space_name()
        self.n_init = config.get("optimizer", {}).get("n_init", 15)
        self.n_iter = config.get("optimizer", {}).get("n_iter", 60)
        self.acquisition = config.get("optimizer", {}).get("acquisition", "EI")
        self.kernel = config.get("optimizer", {}).get("kernel", "matern52")

    def run(self) -> dict:
        """Execute the experiment and return results."""
        logger.info(
            f"Starting experiment: method={self.method}, "
            f"seed={self.seed}, system={self.system_name}, "
            f"space={self.space_name}"
        )

        # Load system config
        system_config = load_config(
            test_system=self.system_name, base=False
        )

        # Build components
        builder = ScenarioBuilder(system_config, space_name=self.space_name)
        dim = builder.dim

        wrapper = ANDESWrapper(
            case_path=system_config.system.case_path,
            config=self._sim_config(),
        )
        sev_cfg = self.config.get("severity", {})
        severity_calc = SeverityCalculator(
            w_angle=sev_cfg.get("w_angle", 0.5),
            w_freq=sev_cfg.get("w_freq", 0.25),
            w_voltage=sev_cfg.get("w_voltage", 0.25),
            angle_threshold=sev_cfg.get("angle_threshold", 180.0),
            freq_nominal=system_config.system.get("freq_nominal", 60.0),
            freq_deviation=sev_cfg.get("freq_deviation", 2.0),
        )

        # Define the objective function
        def objective(x: np.ndarray) -> float:
            scenario = builder.build(x)
            result = wrapper.evaluate(scenario)
            return severity_calc.compute(result)

        # Run the selected method
        total_budget = self.n_init + self.n_iter
        t_start = time.time()

        # Determine acquisition function (override for ablation methods)
        acquisition = self.acquisition
        if self.method in ("bo_ei", "bo_ucb", "bo_pi"):
            acquisition = self.method.split("_")[1].upper()

        if self.method == "bo" or self.method.startswith("bo_"):
            optimizer = BayesianOptimizer(
                objective_fn=objective,
                dim=dim,
                n_init=self.n_init,
                n_iter=self.n_iter,
                acquisition=acquisition,
                kernel=self.kernel,
                seed=self.seed,
            )
            best_x, best_y = optimizer.optimize()
            convergence = optimizer.get_convergence()

        elif self.method == "random":
            searcher = RandomSearch(objective, dim, total_budget, seed=self.seed)
            best_x, best_y = searcher.optimize()
            convergence = searcher.get_convergence()

        elif self.method == "lhs":
            searcher = LatinHypercubeSearch(objective, dim, total_budget, seed=self.seed)
            best_x, best_y = searcher.optimize()
            convergence = searcher.get_convergence()

        elif self.method == "grid":
            n_per_dim = int(total_budget ** (1.0 / dim)) + 1
            searcher = GridSearch(objective, dim, points_per_dim=n_per_dim)
            best_x, best_y = searcher.optimize()
            convergence = searcher.get_convergence()

        elif self.method == "ga":
            searcher = GeneticAlgorithmBaseline(
                objective, dim, total_budget, seed=self.seed
            )
            best_x, best_y = searcher.optimize()
            convergence = searcher.get_convergence()

        else:
            raise ValueError(f"Unknown method: {self.method}")

        wall_time = time.time() - t_start

        # Build result
        best_scenario = builder.build(best_x)
        result = {
            "method": self.method,
            "seed": self.seed,
            "best_x": best_x.tolist(),
            "best_y": float(best_y),
            "best_scenario": best_scenario,
            "convergence": convergence.tolist(),
            "wall_time": wall_time,
            "dim": dim,
            "n_evaluations": len(convergence),
        }

        logger.info(
            f"Experiment done: {self.method} seed={self.seed} "
            f"best_severity={best_y:.4f} time={wall_time:.1f}s"
        )
        return result

    def _get_system_name(self) -> str:
        exp_name = self.config.get("experiment_name", "exp1_kundur_2d")
        if "kundur" in exp_name:
            return "kundur"
        if "ieee39" in exp_name:
            return "ieee39"
        return "kundur"

    def _get_space_name(self) -> str:
        exp_name = self.config.get("experiment_name", "exp1_kundur_2d")
        if "2d" in exp_name:
            return "2d"
        if "4d" in exp_name:
            return "4d"
        if "6d" in exp_name:
            return "6d"
        return "4d"

    def _sim_config(self) -> dict:
        sim = self.config.get("simulation", {})
        return {
            "tf": sim.get("tf", 10.0),
            "tstep": sim.get("tstep", 0.02),
            "criteria": sim.get("criteria", 1),
            "timeout": sim.get("timeout", 60),
        }
