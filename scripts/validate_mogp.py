"""MOGP validation with cross-validation and BO active learning.

Validates Multi-Output GP accuracy on RE sweep data, performs 5-fold CV,
and supplements with BO active learning for weak constraints.
Produces Table 4 data for the paper.
"""

import logging
import sys
import io
import time
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.model_selection import KFold
from sklearn.metrics import r2_score, mean_squared_error, mean_absolute_error

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8")
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.optimizer.multi_output_gp import MultiOutputGP

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s", datefmt="%H:%M:%S")
logger = logging.getLogger(__name__)

MODE_FEATURES = [
    "wind_area1_pct", "wind_area2_pct", "solar_area1_pct", "solar_area2_pct",
    "load_area1", "load_area2", "gen_dispatch_bias",
]

FAULT_FEATURES = ["fault_bus", "clear_time"]


def load_sweep_data(path: str = "data/processed/re_sweep/re_sweep_results.csv"):
    """Load RE sweep results."""
    df = pd.read_csv(path)
    df = df[df["success"] == True].copy()
    logger.info(f"Loaded {len(df)} successful simulations from {path}")
    return df


def prepare_features(df: pd.DataFrame, mode: str = "mode_only"):
    """Prepare feature matrix X and targets y.

    mode: 'mode_only' (7D), 'joint' (9D with fault features), or 're_aware' (8D + RE level)
    """
    if mode == "mode_only":
        features = MODE_FEATURES
    elif mode == "joint":
        features = MODE_FEATURES + FAULT_FEATURES
    elif mode == "re_aware":
        features = MODE_FEATURES + ["re_level"]
    else:
        raise ValueError(f"Unknown mode: {mode}")

    X = df[features].values.astype(float)

    y_dict = {
        "f_angle": df["f_angle"].values.astype(float),
        "f_freq": df["f_freq"].values.astype(float),
        "f_voltage": df["f_voltage"].values.astype(float),
        "severity": df["severity"].values.astype(float),
    }

    # Drop NaN rows
    valid_mask = np.ones(len(df), dtype=bool)
    for key in y_dict:
        valid_mask &= ~np.isnan(y_dict[key])
    X = X[valid_mask]
    for key in y_dict:
        y_dict[key] = y_dict[key][valid_mask]

    return X, y_dict, features, valid_mask


def cross_validate(X, y_dict, n_splits=5, seed=42):
    """5-fold cross-validation of MOGP."""
    kf = KFold(n_splits=n_splits, shuffle=True, random_state=seed)
    all_metrics = []

    for fold_idx, (train_idx, test_idx) in enumerate(kf.split(X)):
        X_train, X_test = X[train_idx], X[test_idx]
        y_train = {k: v[train_idx] for k, v in y_dict.items()}
        y_test = {k: v[test_idx] for k, v in y_dict.items()}

        gp = MultiOutputGP(n_restarts=3, seed=seed + fold_idx)
        gp.fit(X_train, y_train)

        preds = gp.predict(X_test)

        fold_metrics = {"fold": fold_idx}
        for key in ["f_angle", "f_freq", "f_voltage", "severity"]:
            y_true = y_test[key]
            y_pred = preds[key]["mean"]
            fold_metrics[f"{key}_r2"] = r2_score(y_true, y_pred)
            fold_metrics[f"{key}_rmse"] = np.sqrt(mean_squared_error(y_true, y_pred))
            fold_metrics[f"{key}_mae"] = mean_absolute_error(y_true, y_pred)

        all_metrics.append(fold_metrics)
        logger.info(f"  Fold {fold_idx}: severity_R2={fold_metrics['severity_r2']:.3f}, "
                    f"f_angle_R2={fold_metrics['f_angle_r2']:.3f}, "
                    f"f_freq_R2={fold_metrics['f_freq_r2']:.3f}, "
                    f"f_voltage_R2={fold_metrics['f_voltage_r2']:.3f}")

    return pd.DataFrame(all_metrics)


def active_learning_boost(X, y_dict, n_new=50, seed=42):
    """Use MOGP active learning to supplement weak areas.

    Trains on 80% of data, identifies highest-uncertainty points from
    remaining 20%, and re-trains with added points.
    """
    n = len(X)
    rng = np.random.default_rng(seed)
    idx = rng.permutation(n)
    n_train = int(0.8 * n)

    X_train, X_pool = X[idx[:n_train]], X[idx[n_train:]]
    y_train = {k: v[idx[:n_train]] for k, v in y_dict.items()}
    y_pool = {k: v[idx[n_train:]] for k, v in y_dict.items()}

    # Initial fit
    gp = MultiOutputGP(n_restarts=3, seed=seed)
    gp.fit(X_train, y_train)

    # Select high-uncertainty points
    acq_idx = gp.active_learning_acquisition(X_pool, n=min(n_new, len(X_pool)))

    # Add selected points to training
    X_new = X_pool[acq_idx]
    y_new = {k: v[acq_idx] for k, v in y_pool.items()}

    X_aug = np.vstack([X_train, X_new])
    y_aug = {k: np.concatenate([y_train[k], y_new[k]]) for k in y_train}

    # Re-train
    gp_aug = MultiOutputGP(n_restarts=5, seed=seed)
    gp_aug.fit(X_aug, y_aug)

    return gp, gp_aug, X_aug, y_aug


def main():
    output_dir = Path("data/processed/mogp_validation")
    output_dir.mkdir(parents=True, exist_ok=True)

    # Load data
    sweep_path = "data/processed/re_sweep/re_sweep_results.csv"
    if not Path(sweep_path).exists():
        logger.error(f"RE sweep data not found at {sweep_path}. Run run_re_sweep.py first.")
        return

    df = load_sweep_data(sweep_path)

    # --- Compare feature sets ---
    results = {}
    for mode in ["mode_only", "re_aware", "joint"]:
        logger.info(f"\n=== Cross-validation: {mode} ===")
        X, y_dict, features, _ = prepare_features(df, mode=mode)
        logger.info(f"  Features ({len(features)}): {features}")
        logger.info(f"  Samples: {X.shape[0]}, dims: {X.shape[1]}")

        cv_df = cross_validate(X, y_dict, n_splits=5)
        results[mode] = cv_df

        # Summary
        for metric in ["r2", "rmse", "mae"]:
            for key in ["f_angle", "f_freq", "f_voltage", "severity"]:
                col = f"{key}_{metric}"
                if col in cv_df.columns:
                    vals = cv_df[col]
                    logger.info(f"  {col}: {vals.mean():.4f} ± {vals.std():.4f}")

    # Save comparison table
    summary_rows = []
    for mode, cv_df in results.items():
        row = {"feature_set": mode}
        for metric in ["r2", "rmse", "mae"]:
            for key in ["f_angle", "f_freq", "f_voltage", "severity"]:
                col = f"{key}_{metric}"
                if col in cv_df.columns:
                    row[f"{col}_mean"] = cv_df[col].mean()
                    row[f"{col}_std"] = cv_df[col].std()
        summary_rows.append(row)

    summary_df = pd.DataFrame(summary_rows)
    summary_df.to_csv(output_dir / "mogp_comparison.csv", index=False)
    logger.info(f"\nComparison saved to {output_dir / 'mogp_comparison.csv'}")

    # --- Active learning boost ---
    logger.info("\n=== Active Learning Boost ===")
    X, y_dict, features, _ = prepare_features(df, mode="joint")

    gp_before, gp_after, X_aug, y_aug = active_learning_boost(X, y_dict, n_new=50)

    # Evaluate on held-out 20%
    rng = np.random.default_rng(42)
    n = len(X)
    idx = rng.permutation(n)
    n_test = int(0.2 * n)
    X_test = X[idx[:n_test]]
    y_test = {k: v[idx[:n_test]] for k, v in y_dict.items()}

    r2_before = gp_before.r2_per_output(X_test, y_test)
    r2_after = gp_after.r2_per_output(X_test, y_test)

    logger.info("R2 comparison (before -> after active learning):")
    al_rows = []
    for key in ["f_angle", "f_freq", "f_voltage", "severity"]:
        before = r2_before.get(key, float("nan"))
        after = r2_after.get(key, float("nan"))
        improvement = ((after - before) / abs(before) * 100) if before != 0 else 0
        logger.info(f"  {key}: {before:.4f} -> {after:.4f} ({improvement:+.1f}%)")
        al_rows.append({
            "output": key,
            "r2_before": before,
            "r2_after": after,
            "improvement_pct": improvement,
        })

    pd.DataFrame(al_rows).to_csv(output_dir / "active_learning_results.csv", index=False)

    logger.info(f"\nResults saved to {output_dir}")
    logger.info("=== MOGP Validation Complete ===")


if __name__ == "__main__":
    main()
