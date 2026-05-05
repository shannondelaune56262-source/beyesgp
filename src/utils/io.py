"""Result persistence utilities."""

import json
import pickle
from pathlib import Path

import numpy as np
import pandas as pd


def save_results(
    output_dir: Path,
    evaluations: pd.DataFrame,
    best_result: dict,
    convergence: np.ndarray,
    config: dict,
) -> None:
    """Save all results from a single experiment run.

    Args:
        output_dir: Directory to save results in.
        evaluations: DataFrame with columns [x0, x1, ..., severity, stable, sim_time].
        best_result: Dict with best x, severity, and iteration.
        convergence: Array of best-severity-so-far at each evaluation.
        config: The config dict used for this run.
    """
    output_dir.mkdir(parents=True, exist_ok=True)

    evaluations.to_csv(output_dir / "evaluations.csv", index=False)

    with open(output_dir / "best_result.json", "w", encoding="utf-8") as f:
        json.dump(best_result, f, indent=2, default=_json_default)

    np.save(output_dir / "convergence.npy", convergence)

    with open(output_dir / "config.pkl", "wb") as f:
        pickle.dump(config, f)


def load_results(output_dir: Path) -> tuple[pd.DataFrame, dict, np.ndarray]:
    """Load saved results.

    Returns:
        (evaluations, best_result, convergence)
    """
    evaluations = pd.read_csv(output_dir / "evaluations.csv")

    with open(output_dir / "best_result.json", encoding="utf-8") as f:
        best_result = json.load(f)

    convergence = np.load(output_dir / "convergence.npy")

    return evaluations, best_result, convergence


def _json_default(obj):
    if isinstance(obj, (np.integer,)):
        return int(obj)
    if isinstance(obj, (np.floating,)):
        return float(obj)
    if isinstance(obj, np.ndarray):
        return obj.tolist()
    raise TypeError(f"Object of type {type(obj)} is not JSON serializable")
