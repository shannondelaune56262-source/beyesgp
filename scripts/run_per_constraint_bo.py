"""Per-constraint BO search: find worst-case scenarios for each stability constraint.

For each cluster, runs BO targeting:
  1. Max composite severity
  2. Max f_angle (rotor angle stability)
  3. Max f_freq (frequency stability)

Uses BayesianOptimizer (BoTorch) for actual BO, not random sampling.
Identifies the binding constraint per cluster.
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
from src.clustering.limiter import MultiConstraintLimiter
from src.optimizer.bayesian_opt import BayesianOptimizer

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s", datefmt="%H:%M:%S")
logger = logging.getLogger(__name__)

FAULT_BUSES = [2, 3, 4, 5, 6, 7, 8, 9, 10]
CT_RANGE = (0.05, 0.30)

# Mode parameter bounds (global, will be clipped per cluster)
MODE_BOUNDS = {
    "wind_area1_pct": (0.0, 0.40),
    "wind_area2_pct": (0.0, 0.40),
    "solar_area1_pct": (0.0, 0.30),
    "solar_area2_pct": (0.0, 0.30),
    "load_area1": (0.70, 1.15),
    "load_area2": (0.70, 1.15),
    "gen_dispatch_bias": (-0.15, 0.15),
}
MODE_KEYS = list(MODE_BOUNDS.keys())
DIM = 9  # 7 mode params + fault_bus + clear_time


def x_to_cluster_params(x: np.ndarray, cluster_bounds: dict) -> dict:
    """Map [0,1]^9 to physical params within cluster bounds."""
    params = {}
    for i, key in enumerate(MODE_KEYS):
        lo, hi = cluster_bounds.get(key, MODE_BOUNDS[key])
        params[key] = lo + x[i] * (hi - lo)

    fb_idx = min(int(x[7] * len(FAULT_BUSES)), len(FAULT_BUSES) - 1)
    params["fault_bus"] = FAULT_BUSES[fb_idx]

    ct_lo, ct_hi = CT_RANGE
    params["clear_time"] = ct_lo + x[8] * (ct_hi - ct_lo)
    return params


def main():
    output_dir = Path("data/processed/per_constraint_bo")
    output_dir.mkdir(parents=True, exist_ok=True)

    # Load mode analysis with cluster labels
    analysis_path = Path("data/processed/mode_analysis/mode_analysis_full.csv")
    if not analysis_path.exists():
        logger.error("Run analyze_modes.py first to generate cluster labels")
        return

    df = pd.read_csv(analysis_path, index_col=0)
    logger.info(f"Loaded {len(df)} modes with cluster labels")

    # Initialize ANDES
    logger.info("Initializing ANDES wrapper...")
    wrapper = ANDESWrapper(
        case_path="kundur/kundur_full.xlsx",
        config={"tf": 10.0, "tstep": 0.02, "timeout": 60},
    )
    calculator = SeverityCalculator()

    n_clusters = df["cluster"].nunique()
    constraints = ["composite", "f_angle", "f_freq"]
    n_init = 10
    n_iter = 20
    all_results = []

    for cluster_id in range(n_clusters):
        mask = df["cluster"] == cluster_id
        cluster_df = df[mask]
        logger.info(f"\nCluster {cluster_id}: {len(cluster_df)} modes")

        # Get mode parameter ranges within cluster (with padding)
        cluster_bounds = {}
        for col in MODE_KEYS:
            if col in cluster_df.columns:
                lo = float(cluster_df[col].min())
                hi = float(cluster_df[col].max())
                pad = (hi - lo) * 0.1
                global_lo, global_hi = MODE_BOUNDS[col]
                cluster_bounds[col] = (max(lo - pad, global_lo), min(hi + pad, global_hi))
            else:
                cluster_bounds[col] = MODE_BOUNDS[col]

        for constraint in constraints:
            logger.info(f"  BO search: max {constraint} (n_init={n_init}, n_iter={n_iter})...")

            def objective(x: np.ndarray, _cb=cluster_bounds, _con=constraint) -> float:
                params = x_to_cluster_params(x, _cb)
                scenario = _build_scenario_from_params(params)
                try:
                    result = wrapper.evaluate(scenario)
                    sev_info = calculator.compute_with_breakdown(result)
                except Exception:
                    return 0.0
                if _con == "composite":
                    return sev_info["severity"]
                return sev_info.get(_con, 0.0)

            optimizer = BayesianOptimizer(
                objective_fn=objective,
                dim=DIM,
                n_init=n_init,
                n_iter=n_iter,
                acquisition="EI",
                kernel="matern52",
                seed=42 + cluster_id * 10 + constraints.index(constraint),
            )
            best_x, best_y = optimizer.optimize()
            best_params = x_to_cluster_params(best_x, cluster_bounds)

            # Get full breakdown at best point
            scenario = _build_scenario_from_params(best_params)
            result = wrapper.evaluate(scenario)
            sev_info = calculator.compute_with_breakdown(result)

            info = {
                "constraint": constraint,
                "cluster_id": cluster_id,
                "best_target_severity": float(best_y),
                "f_angle": sev_info.get("f_angle", np.nan),
                "f_voltage": sev_info.get("f_voltage", np.nan),
                "f_freq": sev_info.get("f_freq", np.nan),
                "composite": sev_info["severity"],
                "fault_bus": best_params["fault_bus"],
                "clear_time": best_params["clear_time"],
                **{k: float(best_params[k]) for k in MODE_KEYS},
            }
            all_results.append(info)
            logger.info(f"    Best {constraint}: {best_y:.4f} (composite={sev_info['severity']:.4f})")

    # Save results
    results_df = pd.DataFrame(all_results)
    results_df.to_csv(output_dir / "per_constraint_results.csv", index=False)

    # Compute multi-constraint limits
    logger.info("\n=== Multi-Constraint Tiered Limits ===")
    _compute_limits_standalone(df, n_clusters, output_dir)

    logger.info(f"\nResults saved to {output_dir}")


def _build_scenario_from_params(params: dict) -> dict:
    wind_a1 = params.get("wind_area1_pct", 0.0)
    wind_a2 = params.get("wind_area2_pct", 0.0)
    solar_a1 = params.get("solar_area1_pct", 0.0)
    solar_a2 = params.get("solar_area2_pct", 0.0)
    load_a1 = params.get("load_area1", 1.0)
    load_a2 = params.get("load_area2", 1.0)
    bias = params.get("gen_dispatch_bias", 0.0)

    return {
        "fault_bus": params["fault_bus"],
        "fault_time": 1.0,
        "clear_time": 1.0 + params["clear_time"],
        "load_scaling": {
            "area1": max(load_a1 * (1.0 - solar_a1), 0.3),
            "area2": max(load_a2 * (1.0 - solar_a2), 0.3),
        },
        "gen_scaling": {
            "GENROU_1": max(1.0 - wind_a1, 0.3),
            "GENROU_3": max((1.0 - wind_a2) * 0.6, 0.3),
            "GENROU_4": max((1.0 - wind_a2) * 0.4, 0.3),
            "GENROU_2": max(1.0 + bias, 0.3),
        },
        "line_trip": None,
    }


def _compute_limits_standalone(
    df: pd.DataFrame,
    n_clusters: int,
    output_dir: Path,
):
    """Compute multi-constraint limits directly from mode analysis data."""
    from scipy.special import expit as sigmoid

    max_transfer = 400.0
    min_transfer = 100.0

    def sig_limit(sev, k=10, midpoint=0.7):
        return max_transfer - (max_transfer - min_transfer) * sigmoid(k * (sev - midpoint))

    rows = []
    for cid in range(n_clusters):
        mask = df["cluster"] == cid
        cdf = df[mask]

        worst_composite = cdf["severity"].max()
        worst_angle = cdf.get("f_angle", cdf["severity"]).max()
        worst_voltage = cdf.get("f_voltage", cdf["severity"]).max()
        worst_freq = cdf.get("f_freq", cdf["severity"]).max()

        limit_a = sig_limit(worst_angle)
        limit_v = sig_limit(worst_voltage)
        limit_f = sig_limit(worst_freq)

        limits = {"angle": limit_a, "voltage": limit_v, "freq": limit_f}
        binding = min(limits, key=limits.get)
        tiered = limits[binding]

        rows.append({
            "cluster_id": cid,
            "n_modes": mask.sum(),
            "worst_severity": worst_composite,
            "worst_f_angle": worst_angle,
            "worst_f_voltage": worst_voltage,
            "worst_f_freq": worst_freq,
            "limit_angle_mw": limit_a,
            "limit_voltage_mw": limit_v,
            "limit_freq_mw": limit_f,
            "binding_constraint": binding,
            "tiered_limit_mw": tiered,
        })

    limits_df = pd.DataFrame(rows)

    global_worst = df["severity"].max()
    uniform_limit = sig_limit(global_worst)
    limits_df["uniform_limit_mw"] = uniform_limit
    limits_df["improvement_pct"] = (
        (limits_df["tiered_limit_mw"] - uniform_limit) / uniform_limit * 100
    )

    total = limits_df["n_modes"].sum()
    weighted = (limits_df["tiered_limit_mw"] * limits_df["n_modes"]).sum() / total
    improvement = (weighted - uniform_limit) / uniform_limit * 100

    limits_df.to_csv(output_dir / "multi_constraint_limits.csv", index=False)

    print(f"\n{'='*70}")
    print("Multi-Constraint Tiered Limits")
    print(f"{'='*70}")
    print(limits_df.to_string(index=False))
    print(f"\nUniform limit: {uniform_limit:.1f} MW")
    print(f"Weighted avg tiered: {weighted:.1f} MW")
    print(f"Overall improvement: {improvement:.1f}%")

    # Count clusters with different binding constraints
    bindings = limits_df["binding_constraint"].value_counts()
    print(f"\nBinding constraint distribution:")
    for bc, count in bindings.items():
        print(f"  {bc}: {count} clusters")


if __name__ == "__main__":
    main()
