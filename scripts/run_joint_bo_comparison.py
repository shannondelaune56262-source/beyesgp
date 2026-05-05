"""Joint 9D BO vs Random/LHS/GA comparison experiment.

Search space: 7 mode parameters + fault_bus + clear_time = 9D.
Each method gets the same total budget (n_init + n_iter evaluations).
Convergence curves are compared across multiple seeds.
"""

import logging
import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.simulator.andes_wrapper import ANDESWrapper
from src.objective.severity import SeverityCalculator
from src.optimizer.bayesian_opt import BayesianOptimizer
from src.baselines.random_search import RandomSearch, LatinHypercubeSearch
from src.baselines.genetic_algorithm import GeneticAlgorithmBaseline

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s", datefmt="%H:%M:%S")
logger = logging.getLogger(__name__)

# Mode parameter bounds (matching mode_generator.py)
MODE_BOUNDS = {
    "wind_area1_pct": (0.0, 0.40),
    "wind_area2_pct": (0.0, 0.40),
    "solar_area1_pct": (0.0, 0.30),
    "solar_area2_pct": (0.0, 0.30),
    "load_area1": (0.70, 1.15),
    "load_area2": (0.70, 1.15),
    "gen_dispatch_bias": (-0.15, 0.15),
}

FAULT_BUSES = [2, 3, 4, 5, 6, 7, 8, 9, 10]
CLEAR_TIME_BOUNDS = (0.05, 0.30)

DIM = 9  # 7 mode + fault_bus + clear_time


def x_to_params(x: np.ndarray) -> dict:
    """Map [0,1]^9 to physical parameters."""
    mode_keys = list(MODE_BOUNDS.keys())
    params = {}
    for i, key in enumerate(mode_keys):
        lo, hi = MODE_BOUNDS[key]
        params[key] = lo + x[i] * (hi - lo)

    # fault_bus: categorical via rounding
    fb_idx = min(int(x[7] * len(FAULT_BUSES)), len(FAULT_BUSES) - 1)
    params["fault_bus"] = FAULT_BUSES[fb_idx]

    # clear_time: continuous
    ct_lo, ct_hi = CLEAR_TIME_BOUNDS
    params["clear_time"] = ct_lo + x[8] * (ct_hi - ct_lo)

    return params


def build_scenario(params: dict) -> dict:
    """Convert physical parameters to ANDES scenario dict."""
    fault_time = 1.0
    return {
        "fault_bus": params["fault_bus"],
        "fault_time": fault_time,
        "clear_time": fault_time + params["clear_time"],
        "load_scaling": {
            "area1": max(params["load_area1"] * (1.0 - params["solar_area1_pct"]), 0.3),
            "area2": max(params["load_area2"] * (1.0 - params["solar_area2_pct"]), 0.3),
        },
        "gen_scaling": {
            "GENROU_1": max(1.0 - params["wind_area1_pct"], 0.3),
            "GENROU_3": max((1.0 - params["wind_area2_pct"]) * 0.6, 0.3),
            "GENROU_4": max((1.0 - params["wind_area2_pct"]) * 0.4, 0.3),
            "GENROU_2": max(1.0 + params["gen_dispatch_bias"], 0.3),
        },
        "line_trip": None,
    }


def main():
    output_dir = Path("data/processed/joint_bo_comparison")
    output_dir.mkdir(parents=True, exist_ok=True)

    # Experiment settings
    n_init = 15
    n_iter = 50
    total_budget = n_init + n_iter
    methods = ["bo", "random", "lhs", "ga"]
    n_seeds = 3
    seeds = [42, 123, 456]

    # Initialize ANDES
    logger.info("Initializing ANDES wrapper...")
    wrapper = ANDESWrapper(
        case_path="kundur/kundur_full.xlsx",
        config={"tf": 10.0, "tstep": 0.02, "timeout": 60},
    )
    severity_calc = SeverityCalculator()

    logger.info(f"Joint 9D BO comparison: {len(methods)} methods x {n_seeds} seeds x {total_budget} budget")

    all_results = []

    for seed_idx, seed in enumerate(seeds):
        for method in methods:
            logger.info(f"\n{'='*50}")
            logger.info(f"Method={method}, Seed={seed} ({seed_idx+1}/{n_seeds})")
            logger.info(f"{'='*50}")

            # Define objective
            eval_count = [0]

            def objective(x: np.ndarray, _eval_count=eval_count) -> float:
                params = x_to_params(x)
                scenario = build_scenario(params)
                try:
                    result = wrapper.evaluate(scenario)
                    sev = severity_calc.compute(result)
                except Exception:
                    sev = 0.0
                _eval_count[0] += 1
                return sev

            t_start = time.time()

            if method == "bo":
                optimizer = BayesianOptimizer(
                    objective_fn=objective,
                    dim=DIM,
                    n_init=n_init,
                    n_iter=n_iter,
                    acquisition="EI",
                    kernel="matern52",
                    seed=seed,
                )
                best_x, best_y = optimizer.optimize()
                convergence = optimizer.get_convergence()

            elif method == "random":
                searcher = RandomSearch(objective, DIM, total_budget, seed=seed)
                best_x, best_y = searcher.optimize()
                convergence = searcher.get_convergence()

            elif method == "lhs":
                searcher = LatinHypercubeSearch(objective, DIM, total_budget, seed=seed)
                best_x, best_y = searcher.optimize()
                convergence = searcher.get_convergence()

            elif method == "ga":
                searcher = GeneticAlgorithmBaseline(objective, DIM, total_budget, seed=seed)
                best_x, best_y = searcher.optimize()
                convergence = searcher.get_convergence()

            wall_time = time.time() - t_start

            result = {
                "method": method,
                "seed": seed,
                "best_severity": float(best_y),
                "best_params": x_to_params(best_x),
                "convergence": convergence.tolist(),
                "wall_time": wall_time,
                "n_evaluations": len(convergence),
            }
            all_results.append(result)

            logger.info(
                f"  {method} seed={seed}: best_sev={best_y:.4f}, "
                f"n_eval={len(convergence)}, time={wall_time:.1f}s"
            )

            # Save checkpoint after each run
            pd.DataFrame([{
                "method": r["method"],
                "seed": r["seed"],
                "best_severity": r["best_severity"],
                "wall_time": r["wall_time"],
                "n_evaluations": r["n_evaluations"],
                "convergence": str(r["convergence"]),
            } for r in all_results]).to_csv(output_dir / "checkpoint.csv", index=False)

    # Save final results
    import json
    with open(output_dir / "full_results.json", "w") as f:
        # Convert numpy arrays
        serializable = []
        for r in all_results:
            sr = dict(r)
            sr["best_params"] = {k: float(v) for k, v in sr["best_params"].items()}
            serializable.append(sr)
        json.dump(serializable, f, indent=2)

    # Analyze results
    logger.info(f"\n{'='*60}")
    logger.info("JOINT BO COMPARISON RESULTS")
    logger.info(f"{'='*60}")

    # Per-method summary
    for method in methods:
        method_results = [r for r in all_results if r["method"] == method]
        best_sevs = [r["best_severity"] for r in method_results]
        times = [r["wall_time"] for r in method_results]
        logger.info(
            f"  {method:8s}: best_sev mean={np.mean(best_sevs):.4f} "
            f"std={np.std(best_sevs):.4f} "
            f"range=[{np.min(best_sevs):.4f}, {np.max(best_sevs):.4f}] "
            f"time={np.mean(times):.1f}s"
        )

    # Convergence comparison at key budgets
    for budget in [15, 25, 35, 50, 65]:
        logger.info(f"\n  At budget={budget}:")
        for method in methods:
            method_results = [r for r in all_results if r["method"] == method]
            sevs_at_budget = []
            for r in method_results:
                conv = r["convergence"]
                if len(conv) >= budget:
                    sevs_at_budget.append(conv[budget - 1])
            if sevs_at_budget:
                logger.info(
                    f"    {method:8s}: mean={np.mean(sevs_at_budget):.4f} "
                    f"std={np.std(sevs_at_budget):.4f}"
                )

    # Simple regret comparison
    logger.info(f"\n  Simple Regret (1 - best_sev):")
    for method in methods:
        method_results = [r for r in all_results if r["method"] == method]
        regrets = [1.0 - r["best_severity"] for r in method_results]
        logger.info(f"    {method:8s}: {np.mean(regrets):.4f} ± {np.std(regrets):.4f}")

    # Speed-up: budget needed to reach 90% of max severity
    max_sev_overall = max(r["best_severity"] for r in all_results)
    target_sev = 0.9 * max_sev_overall
    logger.info(f"\n  Evaluations to reach {target_sev:.3f} (90% of max {max_sev_overall:.3f}):")
    for method in methods:
        method_results = [r for r in all_results if r["method"] == method]
        evals_needed = []
        for r in method_results:
            for i, sev in enumerate(r["convergence"]):
                if sev >= target_sev:
                    evals_needed.append(i + 1)
                    break
            else:
                evals_needed.append(len(r["convergence"]))
        if evals_needed:
            logger.info(f"    {method:8s}: mean={np.mean(evals_needed):.0f} evals")

    logger.info(f"\nResults saved to {output_dir}")


if __name__ == "__main__":
    main()
