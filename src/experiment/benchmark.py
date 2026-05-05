"""Benchmark framework for comparing methods."""

import logging
from pathlib import Path

import numpy as np

from src.experiment.multi_run import MultiRunExecutor
from src.utils.config import load_config

logger = logging.getLogger(__name__)


class Benchmark:
    """High-level benchmark orchestrator for a complete experiment."""

    def __init__(
        self,
        experiment_name: str,
        test_system: str = "kundur",
        n_workers: int = 1,
    ):
        self.experiment_name = experiment_name
        self.test_system = test_system
        self.n_workers = n_workers

        # Load merged config
        self.config = load_config(
            base=True,
            test_system=test_system,
            experiment=experiment_name.replace(".yaml", ""),
        )
        # Add experiment name to config
        self.config.experiment_name = experiment_name.replace(".yaml", "")

    def run(self, output_dir: str | None = None) -> dict:
        """Run the full benchmark."""
        if output_dir is None:
            output_dir = f"data/processed/{self.experiment_name}"

        methods = self._get_methods()
        seeds = self.config.get("experiment", {}).get(
            "seeds", [42, 123, 456, 789, 1024, 2048, 3141, 4096, 5555, 9999]
        )

        executor = MultiRunExecutor(
            config=self.config,
            output_dir=output_dir,
            methods=methods,
            seeds=seeds,
            n_workers=self.n_workers,
        )

        return executor.execute()

    def _get_methods(self) -> list[str]:
        """Determine which methods to compare based on experiment."""
        name = self.experiment_name.lower()
        if "ablation" in name:
            return ["bo_ei", "bo_ucb", "bo_pi"]
        if "2d" in name:
            return ["bo", "random", "lhs", "ga", "grid"]
        return ["bo", "random", "lhs", "ga"]
