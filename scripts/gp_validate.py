"""GP surrogate model validation with joint mode+fault features.

Supports three modes:
  --mode re-aware: GP on mode+re_level (8D, paper's main result, R²≈0.58)
  --mode mode-only: GP on mode parameters only (7D, expected low R²)
  --mode joint: GP on mode+fault parameters (9D, expected high R²)
"""

import logging
import sys
import json
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.model_selection import train_test_split
from sklearn.metrics import r2_score, mean_squared_error
from sklearn.gaussian_process import GaussianProcessRegressor
from sklearn.gaussian_process.kernels import Matern, WhiteKernel

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s", datefmt="%H:%M:%S")
logger = logging.getLogger(__name__)

MODE_FEATURES = [
    "wind_area1_pct", "wind_area2_pct",
    "solar_area1_pct", "solar_area2_pct",
    "load_area1", "load_area2",
    "gen_dispatch_bias",
]

RE_AWARE_FEATURES = MODE_FEATURES + ["re_level"]

JOINT_FEATURES = MODE_FEATURES + ["fault_bus", "clear_time"]


def validate_gp(
    results_csv: str | None = None,
    output_dir: str = "data/processed/gp_validation",
    mode: str = "joint",
):
    """Train GP on simulation results and validate prediction accuracy."""
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)

    # Auto-detect data source
    if results_csv is None:
        joint_csv = Path("data/processed/joint_sweep/joint_sweep_results.csv")
        re_csv = Path("data/processed/re_sweep/re_sweep_results.csv")
        mode_csv = Path("data/processed/mode_sweep/mode_sweep_results.csv")

        if mode == "joint" and joint_csv.exists():
            results_csv = str(joint_csv)
        elif mode == "re-aware" and re_csv.exists():
            results_csv = str(re_csv)
        elif mode == "mode-only" and mode_csv.exists():
            results_csv = str(mode_csv)
        elif re_csv.exists():
            results_csv = str(re_csv)
        elif joint_csv.exists():
            results_csv = str(joint_csv)
        elif mode_csv.exists():
            results_csv = str(mode_csv)
        else:
            logger.error("No simulation data found")
            return None

    df = pd.read_csv(results_csv)
    logger.info(f"Loaded {len(df)} records from {results_csv}")

    # Only use successful simulations
    if "success" in df.columns:
        df = df[df["success"] == True].copy()
        logger.info(f"Using {len(df)} successful simulations")

    if len(df) < 30:
        logger.warning("Too few data points for GP validation")
        return None

    # Select features
    if mode == "mode-only":
        feature_cols = MODE_FEATURES
    elif mode == "re-aware":
        feature_cols = RE_AWARE_FEATURES
    else:
        feature_cols = JOINT_FEATURES

    available = [c for c in feature_cols if c in df.columns]
    X = df[available].values
    y = df["severity"].values

    # Handle NaN
    mask = ~(np.isnan(X).any(axis=1) | np.isnan(y))
    X, y = X[mask], y[mask]

    logger.info(f"Mode: {mode}, Features: {available} ({X.shape[1]}D)")
    logger.info(f"Samples: {len(X)}, Target range: [{y.min():.3f}, {y.max():.3f}]")

    # Train/test split
    test_size = min(0.2, max(50 / len(X), 0.1))
    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=test_size, random_state=42
    )
    logger.info(f"Train: {len(X_train)}, Test: {len(X_test)}")

    # Train GP with jitter (WhiteKernel) for deterministic simulator robustness
    kernel = Matern(nu=2.5) + WhiteKernel(noise_level=1e-4, noise_level_bounds=(1e-6, 1e-2))
    gp = GaussianProcessRegressor(kernel=kernel, random_state=42, n_restarts_optimizer=5)
    gp.fit(X_train, y_train)
    y_pred, y_std = gp.predict(X_test, return_std=True)

    # Metrics
    r2 = r2_score(y_test, y_pred)
    rmse = np.sqrt(mean_squared_error(y_test, y_pred))
    mae = np.mean(np.abs(y_test - y_pred))

    # --- Local R² in boundary bands ---
    def local_metrics(y_true, y_pred, lo, hi, label):
        mask = (y_true >= lo) & (y_true <= hi)
        n = mask.sum()
        if n < 5:
            return {"n": int(n), "r2": None, "rmse": None, "mae": None}
        r2_l = r2_score(y_true[mask], y_pred[mask])
        rmse_l = np.sqrt(mean_squared_error(y_true[mask], y_pred[mask]))
        mae_l = np.mean(np.abs(y_true[mask] - y_pred[mask]))
        logger.info(f"  [{label}] n={n}, R²={r2_l:.4f}, RMSE={rmse_l:.4f}, MAE={mae_l:.4f}")
        return {"n": int(n), "r2": float(r2_l), "rmse": float(rmse_l), "mae": float(mae_l)}

    logger.info(f"\n=== GP Validation Results ({mode}) ===")
    logger.info(f"  Global R²:  {r2:.4f}")
    logger.info(f"  RMSE: {rmse:.4f}")
    logger.info(f"  MAE:  {mae:.4f}")
    logger.info(f"  Boundary-band R² (S ∈ [0.4, 0.8]):")
    boundary = local_metrics(y_test, y_pred, 0.4, 0.8, "boundary 0.4-0.8")
    logger.info(f"  Critical-band R² (S ∈ [0.5, 0.7]):")
    critical = local_metrics(y_test, y_pred, 0.5, 0.7, "critical 0.5-0.7")

    # --- Safety classification accuracy at θ=0.6 ---
    theta = 0.6
    y_true_safe = y_test < theta
    y_pred_safe = y_pred < theta
    n_boundary_zone = ((y_test >= 0.4) & (y_test <= 0.8)).sum()
    if n_boundary_zone > 0:
        bz_mask = (y_test >= 0.4) & (y_test <= 0.8)
        from sklearn.metrics import accuracy_score, confusion_matrix
        acc_boundary = accuracy_score(y_true_safe[bz_mask], y_pred_safe[bz_mask])
        cm = confusion_matrix(y_true_safe[bz_mask], y_pred_safe[bz_mask], labels=[True, False])
        tn, fp, fn, tp = cm.ravel() if cm.size == 4 else (0, 0, 0, 0)
        logger.info(f"  Boundary-zone classification accuracy (θ={theta}): {acc_boundary:.4f}")
        logger.info(f"    TN={tn}, FP={fp}, FN={fn}, TP={tp}")
        classification = {
            "threshold": theta,
            "boundary_zone_n": int(n_boundary_zone),
            "accuracy": float(acc_boundary),
            "true_negative": int(tn), "false_positive": int(fp),
            "false_negative": int(fn), "true_positive": int(tp),
        }
    else:
        classification = {}

    # Also train per-constraint GPs if data available (using same train/test split)
    constraint_results = {}
    for constraint in ["f_angle", "f_voltage", "f_freq"]:
        if constraint in df.columns:
            y_c = df[constraint].values[mask]
            if not np.isnan(y_c).any() and len(y_c) == len(X):
                y_c_train, y_c_test = train_test_split(y_c, test_size=test_size, random_state=42)
                kernel_c = Matern(nu=2.5) + WhiteKernel(noise_level=1e-4, noise_level_bounds=(1e-6, 1e-2))
                gp_c = GaussianProcessRegressor(kernel=kernel_c, random_state=42, n_restarts_optimizer=3)
                gp_c.fit(X_train, y_c_train)
                y_pred_c = gp_c.predict(X_test)
                r2_c = r2_score(y_c_test, y_pred_c)
                constraint_results[constraint] = float(r2_c)
                logger.info(f"  {constraint} R²: {r2_c:.4f}")

    # Save results
    gp_data = {
        "mode": mode,
        "r2": float(r2),
        "rmse": float(rmse),
        "mae": float(mae),
        "boundary_band": boundary,
        "critical_band": critical,
        "classification": classification,
        "n_train": len(X_train),
        "n_test": len(X_test),
        "n_features": X.shape[1],
        "features": available,
        "constraint_r2": constraint_results,
        "actual": y_test.tolist(),
        "predicted": y_pred.tolist(),
        "uncertainty": y_std.tolist() if isinstance(y_std, np.ndarray) else [],
    }

    suffix = {"mode-only": "mode_only", "re-aware": "re_aware"}.get(mode, "joint")
    with open(output_path / f"gp_validation_{suffix}.json", "w") as f:
        json.dump(gp_data, f, indent=2)

    logger.info(f"Saved to {output_path / f'gp_validation_{suffix}.json'}")
    return gp_data


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--mode", choices=["joint", "mode-only", "re-aware"], default="re-aware")
    args = parser.parse_args()
    validate_gp(mode=args.mode)
