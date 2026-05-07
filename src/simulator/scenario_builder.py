"""Convert normalized parameter vectors to concrete fault scenarios.

Maps x in [0,1]^d to physical ANDES fault scenario parameters.
Supports both Kundur (4d/8d) and IEEE 39 (7d) parameter spaces.
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

        # Collect IEEE 39 RE distribution parameters for batch processing
        _ieee39_params = {}

        for i, dim_cfg in enumerate(self.dimensions):
            name = dim_cfg.name
            val = float(np.clip(x[i], 0.0, 1.0))

            if name == "fault_bus":
                scenario["fault_bus"] = self._map_categorical(val, dim_cfg["values"])

            elif name == "clear_time":
                scenario["clear_time"] = self._map_continuous(
                    val, dim_cfg.bounds[0], dim_cfg.bounds[1]
                )
                scenario["clear_time"] = scenario["fault_time"] + scenario["clear_time"]

            elif name == "load_level_area1":
                factor = self._map_continuous(val, dim_cfg.bounds[0], dim_cfg.bounds[1])
                scenario.setdefault("load_scaling", {})["area1"] = factor

            elif name == "load_level_area2":
                factor = self._map_continuous(val, dim_cfg.bounds[0], dim_cfg.bounds[1])
                scenario.setdefault("load_scaling", {})["area2"] = factor

            # IEEE 39 dimensions
            elif name == "load_level_west":
                factor = self._map_continuous(val, dim_cfg.bounds[0], dim_cfg.bounds[1])
                scenario.setdefault("load_scaling", {})["west"] = factor

            elif name == "load_level_east":
                factor = self._map_continuous(val, dim_cfg.bounds[0], dim_cfg.bounds[1])
                scenario.setdefault("load_scaling", {})["east"] = factor

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

            # IEEE 39 RE distribution parameters (collected for batch processing)
            elif name in ("re_penetration", "re_west_fraction",
                          "re_dispatch_west", "re_dispatch_east"):
                _ieee39_params[name] = self._map_continuous(
                    val, dim_cfg.bounds[0], dim_cfg.bounds[1]
                )

            elif name == "gen_dispatch":
                _ieee39_params[name] = int(round(
                    self._map_continuous(val, dim_cfg.bounds[0], dim_cfg.bounds[1])
                ))

            elif name == "gen_west_scale":
                factor = self._map_continuous(val, dim_cfg.bounds[0], dim_cfg.bounds[1])
                self._apply_area_gen_scaling(scenario, "west", factor)

            elif name == "gen_east_scale":
                factor = self._map_continuous(val, dim_cfg.bounds[0], dim_cfg.bounds[1])
                self._apply_area_gen_scaling(scenario, "east", factor)

        # Process IEEE 39 RE distribution if parameters were collected
        if _ieee39_params:
            self._apply_ieee39_re_distribution(scenario, _ieee39_params)

        # Ensure defaults for missing fields
        scenario.setdefault("load_scaling", {})
        scenario.setdefault("gen_scaling", {})

        return scenario

    def _apply_area_gen_scaling(self, scenario: dict, area: str, factor: float) -> None:
        """Apply uniform gen scaling to all generators in an area."""
        try:
            gens = self.system_config.areas[area].generators
            gs = scenario.setdefault("gen_scaling", {})
            for gen_name in gens:
                gs[gen_name] = factor
        except (AttributeError, KeyError):
            pass

    def _apply_ieee39_re_distribution(self, scenario: dict, params: dict) -> None:
        """Build RE devices and gen scaling from IEEE 39 distribution parameters."""
        from src.simulator.andes_wrapper import REDeviceConfig

        total_gen_mw = 5894.6
        penetration = params.get("re_penetration", 0.0)
        west_frac = params.get("re_west_fraction", 0.5)
        west_dispatch = params.get("re_dispatch_west", 0.7)
        east_dispatch = params.get("re_dispatch_east", 0.7)
        gen_dispatch = params.get("gen_dispatch", 0)

        total_re_mw = penetration * total_gen_mw
        west_re_mw = total_re_mw * west_frac
        east_re_mw = total_re_mw * (1.0 - west_frac)

        # RE placement (from ieee39.yaml)
        re_placement = {
            "west": [
                {"bus": 4,  "weight": 0.42},
                {"bus": 8,  "weight": 0.33},
                {"bus": 6,  "weight": 0.25},
            ],
            "east": [
                {"bus": 20, "weight": 0.46},
                {"bus": 16, "weight": 0.31},
                {"bus": 28, "weight": 0.23},
            ],
        }

        devices = []
        for re_info in re_placement["west"]:
            p_mw = west_re_mw * re_info["weight"] * west_dispatch
            if p_mw > 0.1:
                devices.append(REDeviceConfig(bus=re_info["bus"], p_mw=round(p_mw, 2)))
        for re_info in re_placement["east"]:
            p_mw = east_re_mw * re_info["weight"] * east_dispatch
            if p_mw > 0.1:
                devices.append(REDeviceConfig(bus=re_info["bus"], p_mw=round(p_mw, 2)))

        if devices:
            scenario["re_devices"] = devices

        # Gen scaling: reduce synchronous gen by RE amount
        gen_areas = {
            "west": {"gens": ["GENROU_1", "GENROU_2", "GENROU_3", "GENROU_8", "GENROU_10"],
                     "base_mw": 2703.0},
            "east": {"gens": ["GENROU_4", "GENROU_5", "GENROU_6", "GENROU_7", "GENROU_9"],
                     "base_mw": 3192.0},
        }

        # Dispatch bias
        bias = {0: (1.0, 1.0), 1: (1.08, 0.92), 2: (0.92, 1.08), 3: (1.05, 1.05)}
        wb, eb = bias.get(gen_dispatch, (1.0, 1.0))

        gs = scenario.setdefault("gen_scaling", {})
        for area_name, area_info in gen_areas.items():
            base = area_info["base_mw"]
            re_mw = west_re_mw if area_name == "west" else east_re_mw
            bias_val = wb if area_name == "west" else eb
            scale = max(0.3, bias_val * (1.0 - re_mw / base))
            for gen_name in area_info["gens"]:
                gs[gen_name] = scale

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
