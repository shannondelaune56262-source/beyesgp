"""Quick validation: test each method with minimal budget.

Tests: bo, random, lhs, ga, grid — 2 evaluations each.
Total: ~15 simulations, should complete in <2 minutes.

Usage:
  python scripts/validate_methods.py
"""

# Thread limits MUST be before any imports
import os
os.environ["OMP_NUM_THREADS"] = "4"
os.environ["MKL_NUM_THREADS"] = "4"
os.environ["OPENBLAS_NUM_THREADS"] = "4"

import sys
import time
import traceback
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import numpy as np

from src.utils.config import load_config
from src.simulator.andes_wrapper import ANDESWrapper
from src.simulator.scenario_builder import ScenarioBuilder
from src.objective.severity import SeverityCalculator
from src.optimizer.bayesian_opt import BayesianOptimizer
from src.baselines.random_search import RandomSearch, LatinHypercubeSearch
from src.baselines.grid_search import GridSearch
from src.baselines.genetic_algorithm import GeneticAlgorithmBaseline


def main():
    print("=" * 60)
    print("Method Validation (minimal budget)")
    print("=" * 60)

    # Load config
    config = load_config(base=True, test_system="kundur", experiment="exp1_kundur_2d")
    system_config = load_config(test_system="kundur", base=False)

    # Build components
    builder = ScenarioBuilder(system_config, space_name="2d")
    print(f"Scenario: dim={builder.dim}, space=2d")

    wrapper = ANDESWrapper(
        case_path=system_config.system.case_path,
        config={"tf": 10.0, "tstep": 0.02, "criteria": 1, "timeout": 60},
    )

    sev_cfg = config.get("severity", {})
    sev_calc = SeverityCalculator(
        w_angle=sev_cfg.get("w_angle", 0.5),
        w_freq=sev_cfg.get("w_freq", 0.25),
        w_voltage=sev_cfg.get("w_voltage", 0.25),
        angle_threshold=sev_cfg.get("angle_threshold", 180.0),
        freq_nominal=system_config.system.get("freq_nominal", 60.0),
        freq_deviation=sev_cfg.get("freq_deviation", 2.0),
    )

    eval_count = [0]

    def objective(x):
        eval_count[0] += 1
        scenario = builder.build(x)
        result = wrapper.evaluate(scenario)
        sev = sev_calc.compute(result)
        tag = "OK" if result.success else "FAIL"
        print(f"    eval #{eval_count[0]}: sev={sev:.4f} [{tag}] x={[f'{v:.2f}' for v in x]}")
        return sev

    # ------------------------------------------------------------------
    # Test each method with minimal budget
    # ------------------------------------------------------------------
    results = {}

    # 1. Random Search (2 evals)
    print("\n--- Random Search (2 evals) ---")
    eval_count[0] = 0
    t0 = time.time()
    rs = RandomSearch(objective, dim=2, n_evaluations=2, seed=42)
    bx, by = rs.optimize()
    results["random"] = {"best_y": by, "time": time.time() - t0, "evals": eval_count[0]}
    print(f"  => best_severity={by:.4f}, time={results['random']['time']:.2f}s")

    # 2. LHS (2 evals)
    print("\n--- LHS (2 evals) ---")
    eval_count[0] = 0
    t0 = time.time()
    lhs = LatinHypercubeSearch(objective, dim=2, n_evaluations=2, seed=42)
    bx, by = lhs.optimize()
    results["lhs"] = {"best_y": by, "time": time.time() - t0, "evals": eval_count[0]}
    print(f"  => best_severity={by:.4f}, time={results['lhs']['time']:.2f}s")

    # 3. Grid Search (4 evals: 2 per dim)
    print("\n--- Grid Search (2x2=4 evals) ---")
    eval_count[0] = 0
    t0 = time.time()
    gs = GridSearch(objective, dim=2, points_per_dim=2)
    bx, by = gs.optimize()
    results["grid"] = {"best_y": by, "time": time.time() - t0, "evals": eval_count[0]}
    print(f"  => best_severity={by:.4f}, time={results['grid']['time']:.2f}s")

    # 4. GA (4 evals total)
    print("\n--- Genetic Algorithm (4 evals) ---")
    eval_count[0] = 0
    t0 = time.time()
    ga = GeneticAlgorithmBaseline(objective, dim=2, n_evaluations=4, seed=42)
    bx, by = ga.optimize()
    results["ga"] = {"best_y": by, "time": time.time() - t0, "evals": eval_count[0]}
    print(f"  => best_severity={by:.4f}, time={results['ga']['time']:.2f}s")

    # 5. BO (2 init + 1 iter = 3 evals)
    print("\n--- Bayesian Optimization (2 init + 1 iter = 3 evals) ---")
    eval_count[0] = 0
    t0 = time.time()
    bo = BayesianOptimizer(
        objective_fn=objective, dim=2, n_init=2, n_iter=1,
        acquisition="EI", kernel="matern52", seed=42,
    )
    bx, by = bo.optimize()
    results["bo"] = {"best_y": by, "time": time.time() - t0, "evals": eval_count[0]}
    print(f"  => best_severity={by:.4f}, time={results['bo']['time']:.2f}s")

    # ------------------------------------------------------------------
    # Summary
    # ------------------------------------------------------------------
    print("\n" + "=" * 60)
    print("VALIDATION SUMMARY")
    print("=" * 60)
    print(f"{'Method':<10} {'Evals':>6} {'Best Sev':>10} {'Time':>8} {'Status'}")
    print("-" * 50)

    all_ok = True
    for method, r in results.items():
        status = "OK" if r["best_y"] < 1.0 else "ALL FAILED"
        if status == "ALL FAILED":
            all_ok = False
        print(f"{method:<10} {r['evals']:>6} {r['best_y']:>10.4f} {r['time']:>7.2f}s {status}")

    print("-" * 50)
    total_evals = sum(r["evals"] for r in results.values())
    total_time = sum(r["time"] for r in results.values())
    print(f"{'TOTAL':<10} {total_evals:>6} {'':>10} {total_time:>7.2f}s")

    if all_ok:
        print("\nAll methods found valid (non-failed) scenarios. System stable.")
    else:
        print("\nWARNING: Some methods returned all-failed evaluations.")
        print("Check scenario builder mapping and bus indices.")

    print("\nDone. No system freeze.")


if __name__ == "__main__":
    main()
