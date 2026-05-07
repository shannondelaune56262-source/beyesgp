"""IEEE 39-bus operating mode generator for GP+BO+AIA scalability validation.

Generates 7D parameter space modes focused on RE spatial distribution effects.
The key parameter re_west_fraction controls how much RE goes to WEST vs EAST,
creating distribution-dependent transfer limit variations.
"""

import logging
from dataclasses import dataclass

import numpy as np
import pandas as pd
from scipy.stats import qmc

from src.simulator.andes_wrapper import REDeviceConfig

logger = logging.getLogger(__name__)

# IEEE 39-bus total generation and base parameters
IEEE39_TOTAL_GEN_MW = 5894.6
IEEE39_BASE_MVA = 100.0

# RE placement points from ieee39.yaml
RE_PLACEMENT = {
    "west": [
        {"id": "RE_W1", "bus": 4,  "max_mw": 250, "weight": 0.42},
        {"id": "RE_W2", "bus": 8,  "max_mw": 200, "weight": 0.33},
        {"id": "RE_W3", "bus": 6,  "max_mw": 150, "weight": 0.25},
    ],
    "east": [
        {"id": "RE_E1", "bus": 20, "max_mw": 300, "weight": 0.46},
        {"id": "RE_E2", "bus": 16, "max_mw": 200, "weight": 0.31},
        {"id": "RE_E3", "bus": 28, "max_mw": 150, "weight": 0.23},
    ],
}

# Generator info for inertia calculation and dispatch scaling
GENERATORS = {
    "west": [
        {"name": "GENROU_1",  "bus": 30, "p_mw": 436.1, "sn_mva": 1040.0, "h_s": 8.40},
        {"name": "GENROU_2",  "bus": 31, "p_mw": 646.0, "sn_mva": 836.0,  "h_s": 6.06},
        {"name": "GENROU_3",  "bus": 32, "p_mw": 725.0, "sn_mva": 843.7,  "h_s": 7.16},
        {"name": "GENROU_8",  "bus": 37, "p_mw": 321.5, "sn_mva": 970.2,  "h_s": 4.86},
        {"name": "GENROU_10", "bus": 39, "p_mw": 574.2, "sn_mva": 1199.0, "h_s": 100.00},
    ],
    "east": [
        {"name": "GENROU_4",  "bus": 33, "p_mw": 652.0, "sn_mva": 1174.8, "h_s": 5.72},
        {"name": "GENROU_5",  "bus": 34, "p_mw": 508.0, "sn_mva": 1080.2, "h_s": 5.20},
        {"name": "GENROU_6",  "bus": 35, "p_mw": 687.0, "sn_mva": 1085.7, "h_s": 6.96},
        {"name": "GENROU_7",  "bus": 36, "p_mw": 580.0, "sn_mva": 1025.2, "h_s": 5.28},
        {"name": "GENROU_9",  "bus": 38, "p_mw": 764.8, "sn_mva": 1684.1, "h_s": 6.90},
    ],
}

# 7D parameter space definition
PARAM_DEFS = [
    ("re_penetration",  0.0, 0.60),
    ("re_west_fraction", 0.0, 1.0),
    ("re_dispatch_west", 0.3, 1.0),
    ("re_dispatch_east", 0.3, 1.0),
    ("load_level_west",  0.80, 1.20),
    ("load_level_east",  0.80, 1.20),
    ("gen_dispatch",     0.0, 3.0),  # categorical: 0=uniform, 1=west_heavy, 2=east_heavy, 3=peak
]


class IEEE39ModeGenerator:
    """Generate operating modes for IEEE 39-bus system with RE distribution effects."""

    def __init__(self, n_modes: int = 200, seed: int = 42,
                 method: str = "lhs",
                 re_penetration_levels: list[float] | None = None):
        self.n_modes = n_modes
        self.seed = seed
        self.method = method
        self.re_penetration_levels = re_penetration_levels
        self.dim = len(PARAM_DEFS)
        self._bounds_low = np.array([p[1] for p in PARAM_DEFS])
        self._bounds_high = np.array([p[2] for p in PARAM_DEFS])

    def generate(self) -> pd.DataFrame:
        """Generate operating modes via LHS/Sobol/random sampling."""
        rng = np.random.default_rng(self.seed)

        if self.re_penetration_levels is not None:
            n_per = self.n_modes // len(self.re_penetration_levels)
            remainder = self.n_modes % len(self.re_penetration_levels)
            all_dfs = []
            for i, pen in enumerate(self.re_penetration_levels):
                n = n_per + (1 if i < remainder else 0)
                samples = self._sample(rng, n)
                sub_df = pd.DataFrame(samples, columns=[p[0] for p in PARAM_DEFS])
                sub_df["re_penetration"] = pen
                all_dfs.append(sub_df)
            df = pd.concat(all_dfs, ignore_index=True)
        else:
            samples = self._sample(rng, self.n_modes)
            df = pd.DataFrame(samples, columns=[p[0] for p in PARAM_DEFS])

        # Snap gen_dispatch to nearest integer (categorical)
        df["gen_dispatch"] = df["gen_dispatch"].round().clip(0, 3).astype(int)

        df = self._add_derived_features(df)
        df.index.name = "mode_id"
        logger.info(f"Generated {len(df)} IEEE 39 operating modes via {self.method}")
        return df

    def _sample(self, rng, n: int) -> np.ndarray:
        if self.method == "lhs":
            sampler = qmc.LatinHypercube(d=self.dim, seed=self.seed)
            unit = sampler.random(n=n)
        elif self.method == "sobol":
            sampler = qmc.Sobol(d=self.dim, scramble=True, seed=self.seed)
            m = int(np.ceil(np.log2(n)))
            unit = sampler.random_base2(m)[:n]
        else:
            unit = rng.uniform(size=(n, self.dim))
        return qmc.scale(unit, self._bounds_low, self._bounds_high)

    def _add_derived_features(self, df: pd.DataFrame) -> pd.DataFrame:
        """Compute derived features for clustering and limit attribution."""
        # Total RE capacity
        df["total_re_mw"] = df["re_penetration"] * IEEE39_TOTAL_GEN_MW

        # Per-area RE capacity
        df["west_re_mw"] = df["re_west_fraction"] * df["total_re_mw"]
        df["east_re_mw"] = (1.0 - df["re_west_fraction"]) * df["total_re_mw"]

        # WEST import demand (positive = needs import)
        west_gen_base = sum(g["p_mw"] for g in GENERATORS["west"])  # 2703 MW
        east_gen_base = sum(g["p_mw"] for g in GENERATORS["east"])  # 3192 MW
        west_load_base = 3208.0
        east_load_base = 2649.0

        df["west_import_demand"] = (
            df["load_level_west"] * west_load_base
            - west_gen_base * self._gen_area_factor(df, "west")
            - df["west_re_mw"] * df["re_dispatch_west"]
        )
        df["east_export_surplus"] = (
            east_gen_base * self._gen_area_factor(df, "east")
            + df["east_re_mw"] * df["re_dispatch_east"]
            - df["load_level_east"] * east_load_base
        )

        # System inertia proxy
        df["inertia_proxy"] = self._compute_inertia_proxy(df)

        # Transfer demand (absolute)
        df["transfer_demand"] = df["west_import_demand"].abs()

        # Distribution mode label
        df["distribution_mode"] = df["re_west_fraction"].apply(self._classify_distribution)

        return df

    def _gen_area_factor(self, df: pd.DataFrame, area: str) -> pd.Series:
        """Compute per-area generator scaling factor based on gen_dispatch."""
        base = pd.Series(1.0, index=df.index)
        for idx, row in df.iterrows():
            gd = int(row["gen_dispatch"])
            if gd == 0:  # uniform
                base[idx] = 1.0
            elif gd == 1:  # west_heavy
                base[idx] = 1.1 if area == "west" else 0.9
            elif gd == 2:  # east_heavy
                base[idx] = 0.9 if area == "west" else 1.1
            elif gd == 3:  # peak
                base[idx] = 1.05
        return base

    def _compute_inertia_proxy(self, df: pd.DataFrame) -> pd.Series:
        """Estimate system equivalent inertia H_eq = sum(Hi*Si)/S_total."""
        total_sn = sum(g["sn_mva"] for g in GENERATORS["west"] + GENERATORS["east"])
        h_base = sum(g["h_s"] * g["sn_mva"] for g in GENERATORS["west"] + GENERATORS["east"]) / total_sn
        # RE displaces synchronous gen → reduces inertia proportionally
        return h_base * (1.0 - df["re_penetration"] * 0.8)

    @staticmethod
    def _classify_distribution(f: float) -> str:
        if f >= 0.7:
            return "west_concentrated"
        elif f <= 0.3:
            return "east_concentrated"
        else:
            return "balanced"

    def to_scenarios(self, df: pd.DataFrame,
                     fault_bus: int = 4,
                     fault_time: float = 1.0,
                     clear_time: float = 1.1) -> list[dict]:
        """Convert modes to ANDES-compatible scenario dicts with RE device injection."""
        scenarios = []
        for _, row in df.iterrows():
            re_devices = self._build_re_devices(row)
            gen_scaling = self._build_gen_scaling(row)
            load_scaling = {
                "west": float(row["load_level_west"]),
                "east": float(row["load_level_east"]),
            }

            scenario = {
                "fault_bus": fault_bus,
                "fault_time": fault_time,
                "clear_time": clear_time,
                "load_scaling": load_scaling,
                "gen_scaling": gen_scaling,
                "re_devices": re_devices,
            }
            scenario["_mode_features"] = {
                k: (float(v) if isinstance(v, (np.floating, float))
                    else int(v) if isinstance(v, (np.integer, int))
                    else str(v))
                for k, v in row.items()
            }
            scenarios.append(scenario)
        return scenarios

    def _build_re_devices(self, row: pd.Series) -> list[REDeviceConfig]:
        """Build RE device list from mode parameters using equal-capacity replacement."""
        total_re_mw = float(row["total_re_mw"])
        west_frac = float(row["re_west_fraction"])
        west_dispatch = float(row["re_dispatch_west"])
        east_dispatch = float(row["re_dispatch_east"])

        west_re_total = total_re_mw * west_frac
        east_re_total = total_re_mw * (1.0 - west_frac)

        devices = []
        for re_info in RE_PLACEMENT["west"]:
            p_mw = west_re_total * re_info["weight"] * west_dispatch
            if p_mw > 0.1:
                devices.append(REDeviceConfig(bus=re_info["bus"], p_mw=round(p_mw, 2)))

        for re_info in RE_PLACEMENT["east"]:
            p_mw = east_re_total * re_info["weight"] * east_dispatch
            if p_mw > 0.1:
                devices.append(REDeviceConfig(bus=re_info["bus"], p_mw=round(p_mw, 2)))

        return devices

    def _build_gen_scaling(self, row: pd.Series) -> dict[str, float]:
        """Compute gen scaling factors for equal-capacity replacement."""
        total_re_mw = float(row["total_re_mw"])
        west_frac = float(row["re_west_fraction"])
        gen_dispatch = int(row["gen_dispatch"])

        west_re_mw = total_re_mw * west_frac
        east_re_mw = total_re_mw * (1.0 - west_frac)

        # Base gen output per area
        west_gen_base = sum(g["p_mw"] for g in GENERATORS["west"])  # 2703
        east_gen_base = sum(g["p_mw"] for g in GENERATORS["east"])  # 3192

        # Dispatch bias
        if gen_dispatch == 0:
            west_bias, east_bias = 1.0, 1.0
        elif gen_dispatch == 1:
            west_bias, east_bias = 1.08, 0.92
        elif gen_dispatch == 2:
            west_bias, east_bias = 0.92, 1.08
        else:  # peak
            west_bias, east_bias = 1.05, 1.05

        # Scale factors: reduce gen by RE amount / base gen, apply dispatch bias
        west_scale = max(0.3, west_bias * (1.0 - west_re_mw / west_gen_base))
        east_scale = max(0.3, east_bias * (1.0 - east_re_mw / east_gen_base))

        gen_scaling = {}
        for g in GENERATORS["west"]:
            gen_scaling[g["name"]] = west_scale
        for g in GENERATORS["east"]:
            gen_scaling[g["name"]] = east_scale

        # Slack (GENROU_10) absorbs remaining imbalance
        return gen_scaling

    def is_feasible(self, row: pd.Series) -> bool:
        """Check if mode is likely to converge."""
        total_re = float(row["total_re_mw"])
        if total_re > IEEE39_TOTAL_GEN_MW * 0.65:
            return False
        if float(row["load_level_west"]) > 1.15 and float(row["re_penetration"]) > 0.5:
            return False
        if float(row["load_level_east"]) > 1.15 and float(row["re_penetration"]) > 0.5:
            return False
        return True

    def filter_feasible(self, df: pd.DataFrame) -> pd.DataFrame:
        """Filter modes unlikely to converge."""
        mask = df.apply(self.is_feasible, axis=1)
        n_filtered = (~mask).sum()
        if n_filtered > 0:
            logger.info(f"Feasibility filter: removed {n_filtered}/{len(df)} modes")
        return df[mask].copy()
