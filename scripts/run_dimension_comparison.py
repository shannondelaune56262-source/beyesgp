"""Quick dimension comparison experiment (2D/4D/6D).

Reduced budget for fast validation: 2 seeds, 15 evaluations each.
"""

import logging
import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.simulator.andes_wrapper import ANDESWrapper
from src.simulator.scenario_builder import ScenarioBuilder
from src.objective.severity import SeverityCalculator
from src.optimizer.bayesian_opt import BayesianOptimizer
from src.baselines.random_search import RandomSearch
from src.utils.config import load_config

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s", datefmt="%H:%M:%S")
logger = logging.getLogger(__name__)

DIMENSIONS = ["2d", "4d", "6d"]
METHODS = ["bo", "random"]
SEEDS = [42, 123]
BUDGETS = {"2d": 20, "4d": 30, "6d": 40}
N_INIT = {"2d": 5, "4d": 8, "6d": 10}


def main():
    output_dir = Path("data/processed/dimension_comparison")
    output_dir.mkdir(parents=True, exist_ok=True)

    # Initialize ANDES wrapper (shared across experiments)
    logger.info("Initializing ANDES wrapper...")
    system_config = load_config(test_system="kundur", base=False)
    wrapper = ANDESWrapper(
        case_path=system_config.system.case_path,
        config={"tf": 10.0, "tstep": 0.02, "timeout": 60},
    )
    severity_calc = SeverityCalculator()

    all_results = []

    for dim_name in DIMENSIONS:
        budget = BUDGETS[dim_name]
        n_init = N_INIT[dim_name]

        logger.info(f"\n{'='*50}")
        logger.info(f"Dimension: {dim_name} (budget={budget}, n_init={n_init})")
        logger.info(f"{'='*50}")

        builder = ScenarioBuilder(system_config, space_name=dim_name)
        dim = builder.dim

        for method in METHODS:
            for seed in SEEDS:
                logger.info(f"[{dim_name}] {method} seed={seed}")

                def objective(x, _builder=builder, _wrapper=wrapper, _calc=severity_calc):
                    scenario = _builder.build(x)
                    result = _wrapper.evaluate(scenario)
                    return _calc.compute(result)

                t0 = time.time()
                if method == "bo":
                    opt = BayesianOptimizer(
                        objective_fn=objective, dim=dim,
                        n_init=n_init, n_iter=budget - n_init,
                        acquisition="EI", seed=seed,
                    )
                    best_x, best_y = opt.optimize()
                    convergence = opt.get_convergence()
                else:
                    searcher = RandomSearch(objective, dim, budget, seed=seed)
                    best_x, best_y = searcher.optimize()
                    convergence = searcher.get_convergence()

                elapsed = time.time() - t0

                all_results.append({
                    "dimension": dim_name,
                    "method": method,
                    "seed": seed,
                    "best_severity": float(best_y),
                    "convergence": convergence.tolist(),
                    "wall_time": elapsed,
                    "n_evals": len(convergence),
                })
                logger.info(f"  -> best_sev={best_y:.4f}, time={elapsed:.1f}s")

    # Save results
    df = pd.DataFrame(all_results)
    df.to_csv(output_dir / "dimension_comparison.csv", index=False)

    # Summary
    print("\n=== Dimension Comparison Summary ===")
    for dim_name in DIMENSIONS:
        print(f"\n{dim_name}:")
        for method in METHODS:
            mask = (df["dimension"] == dim_name) & (df["method"] == method)
            sevs = df.loc[mask, "best_severity"]
            print(f"  {method}: mean={sevs.mean():.4f}, std={sevs.std():.4f}, "
                  f"min={sevs.min():.4f}, max={sevs.max():.4f}")

    # Generate convergence plot
    try:
        from src.visualization.paper_figures import plot_convergence_curves
        for dim_name in DIMENSIONS:
            conv_data = {}
            for method in METHODS:
                curves = []
                mask = (df["dimension"] == dim_name) & (df["method"] == method)
                for _, row in df[mask].iterrows():
                    curves.append(row["convergence"])
                if curves:
                    conv_data[method] = curves
            if conv_data:
                plot_convergence_curves(
                    conv_data,
                    output_dir / f"convergence_{dim_name}.png",
                    title=f"Convergence: {dim_name} space",
                )
    except Exception as e:
        logger.warning(f"Plot generation failed: {e}")

    print(f"\nResults saved to {output_dir}")


if __name__ == "__main__":
    main()
