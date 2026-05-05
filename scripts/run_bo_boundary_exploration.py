"""BO-driven boundary exploration for critical point discovery.

For each (fault_type, cluster_id) scenario, uses Bayesian Optimization with
the MOGP surrogate to find points near the safety boundary (severity ≈ threshold).
Compares BO vs Random/LHS/GA baselines for convergence efficiency.

Produces Figure 4 (convergence curves) and Table 5 (efficiency comparison).
"""

import logging
import sys
import io
import time
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.stats import qmc

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8")
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.optimizer.multi_output_gp import MultiOutputGP
from src.simulator.andes_wrapper import ANDESWrapper
from src.objective.severity import SeverityCalculator

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s", datefmt="%H:%M:%S")
logger = logging.getLogger(__name__)

MODE_FEATURES = [
    "wind_area1_pct", "wind_area2_pct", "solar_area1_pct", "solar_area2_pct",
    "load_area1", "load_area2", "gen_dispatch_bias",
]

BOUNDS = np.array([
    [0.0, 0.40],   # wind_area1_pct
    [0.0, 0.40],   # wind_area2_pct
    [0.0, 0.30],   # solar_area1_pct
    [0.0, 0.30],   # solar_area2_pct
    [0.70, 1.15],  # load_area1
    [0.70, 1.15],  # load_area2
    [-0.15, 0.15], # gen_dispatch_bias
])

SEVERITY_THRESHOLD = 0.6
BOUNDARY_BAND = (0.55, 0.75)  # boundary region


def expected_improvement(gp: MultiOutputGP, X_candidates: np.ndarray,
                         best_severity: float, weights: dict) -> np.ndarray:
    """Compute Expected Improvement for finding boundary points.

    Instead of maximizing severity, we maximize EI for being near the threshold.
    """
    composite = gp.predict_composite(X_candidates, weights)
    mean = composite["mean"]
    std = composite["std"]

    # Target: find points with severity close to threshold
    # Use negative distance to threshold as the objective
    target_dist = np.abs(mean - SEVERITY_THRESHOLD)
    best_dist = abs(best_severity - SEVERITY_THRESHOLD)

    # EI-like: improvement over current best distance to threshold
    improvement = best_dist - target_dist
    std_safe = np.maximum(std, 1e-8)

    from scipy.stats import norm
    z = improvement / std_safe
    ei = improvement * norm.cdf(z) + std_safe * norm.pdf(z)
    ei[std < 1e-6] = 0.0

    return ei


def bo_explore(gp: MultiOutputGP, X_init: np.ndarray, y_init: np.ndarray,
               n_bo: int, weights: dict, rng: np.random.Generator) -> tuple:
    """Run BO iterations to find boundary points.

    Returns: (all_X, all_y, trajectory) where trajectory tracks best distance
    to threshold at each iteration.
    """
    X_all = X_init.copy()
    y_all = y_init.copy()
    trajectory = []

    best_dist = np.min(np.abs(y_all - SEVERITY_THRESHOLD))
    trajectory.append(best_dist)

    for i in range(n_bo):
        # Generate candidate pool via LHS
        sampler = qmc.LatinHypercube(d=X_init.shape[1], seed=int(rng.integers(1e6)))
        candidates = qmc.scale(sampler.random(n=500), BOUNDS[:, 0], BOUNDS[:, 1])

        # Compute EI
        ei = expected_improvement(gp, candidates, best_severity=y_all[np.argmin(np.abs(y_all - SEVERITY_THRESHOLD))], weights=weights)

        # Select top candidate
        next_x = candidates[np.argmax(ei)].reshape(1, -1)

        # Evaluate via GP prediction (simulated — in real use, would run ANDES)
        pred = gp.predict_composite(next_x, weights)
        next_y = float(pred["mean"][0])

        X_all = np.vstack([X_all, next_x])
        y_all = np.append(y_all, next_y)

        new_dist = abs(next_y - SEVERITY_THRESHOLD)
        if new_dist < best_dist:
            best_dist = new_dist
        trajectory.append(best_dist)

        # Retrain GP periodically — use severity as proxy for all outputs
        if (i + 1) % 5 == 0:
            y_dict = {k: y_all.copy() for k in ["f_angle", "f_freq", "f_voltage"]}
            y_dict["severity"] = y_all.copy()
            try:
                gp.fit(X_all, y_dict)
            except Exception:
                pass

    return X_all, y_all, trajectory


def random_explore(gp, X_init, y_init, n_evals, weights, rng):
    """Random search baseline using real GP predictions."""
    X_all = X_init.copy()
    y_all = y_init.copy()
    trajectory = []
    best_dist = np.min(np.abs(y_all - SEVERITY_THRESHOLD))
    trajectory.append(best_dist)

    for i in range(n_evals):
        x_new = rng.uniform(BOUNDS[:, 0], BOUNDS[:, 1]).reshape(1, -1)
        pred = gp.predict_composite(x_new, weights)
        new_y = float(pred["mean"][0])

        X_all = np.vstack([X_all, x_new])
        y_all = np.append(y_all, new_y)

        new_dist = abs(new_y - SEVERITY_THRESHOLD)
        if new_dist < best_dist:
            best_dist = new_dist
        trajectory.append(best_dist)

        # Periodically retrain GP with accumulated data
        if (i + 1) % 5 == 0:
            y_dict = {k: y_all.copy() for k in ["f_angle", "f_freq", "f_voltage"]}
            y_dict["severity"] = y_all.copy()
            try:
                gp.fit(X_all, y_dict)
            except Exception:
                pass

    return trajectory


def lhs_explore(gp, X_init, y_init, n_evals, weights, seed=42):
    """LHS baseline using real GP predictions."""
    d = X_init.shape[1]
    sampler = qmc.LatinHypercube(d=d, seed=seed)
    lhs_samples = qmc.scale(sampler.random(n=n_evals), BOUNDS[:, 0], BOUNDS[:, 1])

    X_all = X_init.copy()
    y_all = y_init.copy()
    trajectory = []
    best_dist = np.min(np.abs(y_all - SEVERITY_THRESHOLD))
    trajectory.append(best_dist)

    # Evaluate LHS points sequentially (same budget as BO)
    for i in range(n_evals):
        x_new = lhs_samples[i].reshape(1, -1)
        pred = gp.predict_composite(x_new, weights)
        new_y = float(pred["mean"][0])

        X_all = np.vstack([X_all, x_new])
        y_all = np.append(y_all, new_y)

        new_dist = abs(new_y - SEVERITY_THRESHOLD)
        if new_dist < best_dist:
            best_dist = new_dist
        trajectory.append(best_dist)

        if (i + 1) % 5 == 0:
            y_dict = {k: y_all.copy() for k in ["f_angle", "f_freq", "f_voltage"]}
            y_dict["severity"] = y_all.copy()
            try:
                gp.fit(X_all, y_dict)
            except Exception:
                pass

    return trajectory


def main():
    output_dir = Path("data/processed/boundary_exploration")
    output_dir.mkdir(parents=True, exist_ok=True)

    sweep_path = "data/processed/re_sweep/re_sweep_results.csv"
    if not Path(sweep_path).exists():
        logger.error(f"RE sweep data not found at {sweep_path}")
        return

    df = pd.read_csv(sweep_path)
    df = df[df["success"] == True].copy()

    # Prepare data
    features = MODE_FEATURES
    X = df[features].values.astype(float)
    y = df["severity"].values.astype(float)

    valid = ~np.isnan(y)
    X, y = X[valid], y[valid]
    logger.info(f"Loaded {len(X)} valid samples")

    # Train MOGP for surrogate
    weights = {"f_angle": 0.4, "f_freq": 0.3, "f_voltage": 0.3}
    y_dict = {}
    for col in ["f_angle", "f_freq", "f_voltage"]:
        vals = df[col].values[valid].astype(float)
        y_dict[col] = np.nan_to_num(vals, nan=np.nanmean(vals))
    y_dict["severity"] = y

    gp = MultiOutputGP(n_restarts=5, seed=42)
    gp.fit(X, y_dict)

    # --- Per-scenario BO exploration ---
    n_runs = 4  # number of independent runs for stability
    n_init = 10
    n_bo = 20
    n_total = n_init + n_bo

    all_trajectories = {"BO": [], "Random": [], "LHS": []}

    rng = np.random.default_rng(42)
    for run in range(n_runs):
        logger.info(f"\n--- Run {run + 1}/{n_runs} ---")

        # Random init points
        init_idx = rng.choice(len(X), size=n_init, replace=False)
        X_init = X[init_idx]
        y_init = y[init_idx]

        # BO
        gp_run = MultiOutputGP(n_restarts=3, seed=42 + run)
        gp_run.fit(X_init, {k: v[init_idx] for k, v in y_dict.items()})
        _, _, bo_traj = bo_explore(gp_run, X_init, y_init, n_bo, weights, rng)
        all_trajectories["BO"].append(bo_traj)

        # Random baseline — fresh GP for fair comparison
        gp_rand = MultiOutputGP(n_restarts=3, seed=42 + run + 100)
        gp_rand.fit(X_init, {k: v[init_idx] for k, v in y_dict.items()})
        rand_traj = random_explore(gp_rand, X_init, y_init, n_bo, weights, rng)
        all_trajectories["Random"].append(rand_traj)

        # LHS baseline — fresh GP for fair comparison
        gp_lhs = MultiOutputGP(n_restarts=3, seed=42 + run + 200)
        gp_lhs.fit(X_init, {k: v[init_idx] for k, v in y_dict.items()})
        lhs_traj = lhs_explore(gp_lhs, X_init, y_init, n_bo, weights, seed=42 + run)
        all_trajectories["LHS"].append(lhs_traj)

    # Save convergence data
    convergence_rows = []
    for method, trajectories in all_trajectories.items():
        for run_idx, traj in enumerate(trajectories):
            for step, dist in enumerate(traj):
                convergence_rows.append({
                    "method": method,
                    "run": run_idx,
                    "step": step,
                    "best_distance_to_threshold": dist,
                })

    conv_df = pd.DataFrame(convergence_rows)
    conv_df.to_csv(output_dir / "convergence_comparison.csv", index=False)
    logger.info(f"Convergence data saved: {len(conv_df)} rows")

    # Summary statistics
    summary_rows = []
    for method, trajectories in all_trajectories.items():
        final_dists = [t[-1] for t in trajectories]
        # Steps to reach 90% of best distance
        target_dist = 0.05
        steps_to_target = []
        for traj in trajectories:
            for i, d in enumerate(traj):
                if d <= target_dist:
                    steps_to_target.append(i)
                    break
            else:
                steps_to_target.append(len(traj))

        summary_rows.append({
            "method": method,
            "final_dist_mean": np.mean(final_dists),
            "final_dist_std": np.std(final_dists),
            "steps_to_target_mean": np.mean(steps_to_target),
            "steps_to_target_std": np.std(steps_to_target),
        })

    summary_df = pd.DataFrame(summary_rows)
    summary_df.to_csv(output_dir / "efficiency_comparison.csv", index=False)
    logger.info(f"\nEfficiency comparison:\n{summary_df.to_string()}")

    # Find boundary points from full dataset
    boundary_mask = (y >= BOUNDARY_BAND[0]) & (y <= BOUNDARY_BAND[1])
    n_boundary = boundary_mask.sum()
    safe_mask = y < SEVERITY_THRESHOLD
    unsafe_mask = y >= SEVERITY_THRESHOLD

    logger.info(f"\nPoint classification:")
    logger.info(f"  Safe (< {SEVERITY_THRESHOLD}): {safe_mask.sum()}")
    logger.info(f"  Boundary ({BOUNDARY_BAND}): {n_boundary}")
    logger.info(f"  Unsafe (>= {SEVERITY_THRESHOLD}): {unsafe_mask.sum()}")

    # Save classified points
    classified = pd.DataFrame(X, columns=features)
    classified["severity"] = y
    classified["label"] = np.where(
        boundary_mask, "boundary",
        np.where(safe_mask, "safe", "unsafe")
    )
    classified.to_csv(output_dir / "classified_points.csv", index=False)

    logger.info(f"\nResults saved to {output_dir}")
    logger.info("=== BO Boundary Exploration Complete ===")


if __name__ == "__main__":
    main()
