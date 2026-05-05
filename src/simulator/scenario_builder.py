"""Convert normalized parameter vectors to concrete fault scenarios.

Maps x in [0,1]^d to physical ANDES fault scenario parameters.
"""

from typing import Any

import numpy as np

from src.utils.config import load_config, DictConfig


class ScenarioBuilder:
    """Builds fault scenarios from normalized BO parameter vectors.

    Handles the mapping from continuous [0,1]^d space to the mixed
    continuous/categorical physical parameter space.
    """

    def __init__(self, system_config: DictConfig, space_name: str = "4d"):
        self.system_config = system_config
        self.space_name = space_name
        self.space_config = system_config.scenario_spaces[space_name]
        self.dimensions = self.space_config.dimensions
        self.dim = len(self.dimensions)

    def build(self, x: np.ndarray) -> dict:
        """Convert normalized parameter vector to scenario dict.

        Args:
            x: Parameter vector in [0,1]^d.

        Returns:
            Dict with ANDES-compatible scenario parameters.
        """
        assert len(x) == self.dim, f"Expected {self.dim} dims, got {len(x)}"

        scenario = {
            "fault_time": 1.0,  # Default fault occurrence time
        }

        for i, dim_cfg in enumerate(self.dimensions):
            name = dim_cfg.name
            val = float(np.clip(x[i], 0.0, 1.0))

            if name == "fault_bus":
                scenario["fault_bus"] = self._map_categorical(val, dim_cfg["values"])

            elif name == "clear_time":
                scenario["clear_time"] = self._map_continuous(
                    val, dim_cfg.bounds[0], dim_cfg.bounds[1]
                )
                # Fault clear time = fault_time + clear_time
                scenario["clear_time"] = scenario["fault_time"] + scenario["clear_time"]

            elif name == "load_level_area1":
                factor = self._map_continuous(val, dim_cfg.bounds[0], dim_cfg.bounds[1])
                scenario.setdefault("load_scaling", {})["area1"] = factor

            elif name == "load_level_area2":
                factor = self._map_continuous(val, dim_cfg.bounds[0], dim_cfg.bounds[1])
                scenario.setdefault("load_scaling", {})["area2"] = factor

            elif name == "line_trip":
                mapped = self._map_categorical(val, dim_cfg["values"])
                if mapped != "none":
                    scenario["line_trip"] = {
                        "line_idx": mapped,
                        "time": scenario["fault_time"],
                    }

            elif name == "gen1_output_scale":
                factor = self._map_continuous(val, dim_cfg.bounds[0], dim_cfg.bounds[1])
                scenario.setdefault("gen_scaling", {})["GENROU_1"] = factor

        # Ensure defaults for missing fields
        scenario.setdefault("load_scaling", {})
        scenario.setdefault("gen_scaling", {})

        return scenario

    def build_batch(self, X: np.ndarray) -> list[dict]:
        """Build scenarios for a batch of parameter vectors."""
        return [self.build(x) for x in X]

    @staticmethod
    def _map_categorical(val: float, values: list) -> Any:
        """Map [0,1] value to categorical choice."""
        idx = int(val * len(values))
        idx = min(idx, len(values) - 1)
        return values[idx]

    @staticmethod
    def _map_continuous(val: float, low: float, high: float) -> float:
        """Map [0,1] value to [low, high]."""
        return low + val * (high - low)

    def get_bounds(self) -> np.ndarray:
        """Return [0,1]^d bounds for the optimizer."""
        return np.array([[0.0, 1.0]] * self.dim)
