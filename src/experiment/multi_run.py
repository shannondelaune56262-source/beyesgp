"""Multi-seed experiment execution.

All tasks run sequentially in the main process to avoid memory issues
with loading multiple ANDES instances. n_workers is reserved for future
parallel execution support.
"""

import json
import logging
from pathlib import Path

import numpy as np
import pandas as pd

from src.experiment.runner import ExperimentRunner
from src.utils.config import DictConfig
from src.utils.io import save_results

logger = logging.getLogger(__name__)


class MultiRunExecutor:
    """Execute experiments across multiple seeds and methods sequentially."""

    def __init__(
        self,
        config: DictConfig,
        output_dir: str | Path,
        methods: list[str] | None = None,
        seeds: list[int] | None = None,
        n_workers: int = 1,
    ):
        self.config = config
        self.output_dir = Path(output_dir)
        self.methods = methods or ["bo", "random", "lhs", "ga"]
        self.seeds = seeds or config.get("experiment", {}).get(
            "seeds", [42, 123, 456, 789, 1024]
        )
        self.n_workers = n_workers

    def execute(self) -> dict:
        """Run all method-seed combinations sequentially.

        Returns:
            Nested dict: results[method][seed] = result_dict
        """
        all_results = {}

        # Build task list
        tasks = []
        for method in self.methods:
            for seed in self.seeds:
                tasks.append((method, seed))

        logger.info(
            f"Running {len(tasks)} experiments "
            f"({len(self.methods)} methods x {len(self.seeds)} seeds) "
            f"sequentially"
        )

        # Execute sequentially in the main process
        results_list = []
        for i, (method, seed) in enumerate(tasks):
            logger.info(f"[{i+1}/{len(tasks)}] method={method}, seed={seed}")
            try:
                runner = ExperimentRunner(self.config, method, seed)
                result = runner.run()
                results_list.append(result)
            except Exception as e:
                logger.error(f"Task failed (method={method}, seed={seed}): {e}")

        # Organize by method
        for result in results_list:
            method = result["method"]
            seed = result["seed"]
            all_results.setdefault(method, {})[seed] = result

            # Save individual result
            method_dir = self.output_dir / method
            seed_dir = method_dir / f"seed_{seed}"
            seed_dir.mkdir(parents=True, exist_ok=True)
            with open(seed_dir / "result.json", "w") as f:
                json.dump(result, f, indent=2, default=_json_default)

        # Aggregate statistics
        summary = self._aggregate(all_results)
        return {"individual": all_results, "summary": summary}

    def _aggregate(self, all_results: dict) -> pd.DataFrame:
        """Compute per-method statistics across seeds."""
        rows = []
        for method, seed_results in all_results.items():
            final_severities = [
                r["best_y"] for r in seed_results.values()
            ]
            wall_times = [r["wall_time"] for r in seed_results.values()]

            rows.append({
                "method": method,
                "mean_severity": np.mean(final_severities),
                "std_severity": np.std(final_severities),
                "min_severity": np.min(final_severities),
                "max_severity": np.max(final_severities),
                "mean_wall_time": np.mean(wall_times),
                "n_seeds": len(final_severities),
            })

        summary = pd.DataFrame(rows)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        summary.to_csv(self.output_dir / "summary.csv", index=False)
        logger.info(f"\n{summary.to_string()}")
        return summary


def _json_default(obj):
    if isinstance(obj, (np.integer,)):
        return int(obj)
    if isinstance(obj, (np.floating,)):
        return float(obj)
    if isinstance(obj, np.ndarray):
        return obj.tolist()
    raise TypeError(f"Not JSON serializable: {type(obj)}")
