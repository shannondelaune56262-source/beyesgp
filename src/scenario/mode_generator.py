"""Operating mode generator for high-RE power grid analysis.

Generates diverse operating modes by varying renewable penetration, load levels,
and inter-area power flows. Models wind/solar as displacing synchronous generation
(reducing inertia), reflecting real high-RE grid conditions.

Uses Latin Hypercube Sampling (LHS) for efficient coverage of the multi-dimensional
operating space.
"""

import logging
from dataclasses import dataclass
from typing import Literal

import numpy as np
import pandas as pd
from scipy.stats import qmc

logger = logging.getLogger(__name__)


@dataclass
class ModeSpec:
    """Specification for a single operating mode parameter."""
    name: str
    low: float
    high: float
    description: str


# Default parameter ranges for Kundur 2-area system with renewable integration
DEFAULT_MODE_PARAMS = [
    ModeSpec("wind_area1_pct", 0.0, 0.40,
             "Wind penetration in Area 1 (fraction of GENROU_1 output displaced)"),
    ModeSpec("wind_area2_pct", 0.0, 0.40,
             "Wind penetration in Area 2 (fraction of GENROU_3/4 output displaced)"),
    ModeSpec("solar_area1_pct", 0.0, 0.30,
             "Solar penetration in Area 1 (fraction of Area 1 load met by solar)"),
    ModeSpec("solar_area2_pct", 0.0, 0.30,
             "Solar penetration in Area 2 (fraction of Area 2 load met by solar)"),
    ModeSpec("load_area1", 0.70, 1.15,
             "Area 1 load scaling factor (seasonal/daily variation)"),
    ModeSpec("load_area2", 0.70, 1.15,
             "Area 2 load scaling factor (seasonal/daily variation)"),
    ModeSpec("gen_dispatch_bias", -0.15, 0.15,
             "Inter-area generation dispatch bias (negative = more Area 1 gen)"),
]

# RE penetration level definitions (maps level to RE device count and gen displacement)
RE_LEVEL_MAP = {
    0: {"n_devices": 0, "gen_factor_a1": 1.00, "gen_factor_a2": 1.00,
        "description": "No renewable energy (conventional only)"},
    1: {"n_devices": 1, "gen_factor_a1": 0.90, "gen_factor_a2": 1.00,
        "description": "Low RE: 1 device (~20 MW, ~10% penetration)"},
    2: {"n_devices": 3, "gen_factor_a1": 0.85, "gen_factor_a2": 0.85,
        "description": "Medium RE: 3 devices (~60 MW, ~30% penetration)"},
    3: {"n_devices": 5, "gen_factor_a1": 0.70, "gen_factor_a2": 0.75,
        "description": "High RE: 5 devices (~100 MW, ~50% penetration)"},
    4: {"n_devices": 6, "gen_factor_a1": 0.55, "gen_factor_a2": 0.60,
        "description": "Extreme RE: 6 devices (~120 MW, ~60% penetration)"},
}


class ModeGenerator:
    """Generates diverse operating modes for clustering-based stability analysis.

    Each mode represents a snapshot of grid operating conditions:
    - Renewable penetration levels (wind/solar displacing synchronous gen)
    - Load levels (seasonal/daily variation)
    - Inter-area power flow (generation dispatch pattern)

    Renewable penetration is modeled as synchronous generation displacement:
    higher wind_pct means lower GENROU output → reduced inertia → different dynamics.
    """

    def __init__(
        self,
        n_modes: int = 1000,
        params: list[ModeSpec] | None = None,
        seed: int = 42,
        method: Literal["lhs", "random", "sobol"] = "lhs",
        re_levels: list[int] | None = None,
    ):
        self.n_modes = n_modes
        self.params = params or DEFAULT_MODE_PARAMS
        self.seed = seed
        self.method = method
        self.re_levels = re_levels  # None means all modes use RE level 0 (no RE)
        self.dim = len(self.params)
        self._bounds_low = np.array([p.low for p in self.params])
        self._bounds_high = np.array([p.high for p in self.params])

    def generate(self) -> pd.DataFrame:
        """Generate operating modes as a DataFrame.

        Returns:
            DataFrame with one row per mode, columns for each parameter,
            plus derived features (total_re, net_flow, inertia_proxy).
            If re_levels is set, includes re_level column.
        """
        rng = np.random.default_rng(self.seed)

        if self.re_levels is not None:
            # Distribute modes evenly across RE levels
            n_per_level = self.n_modes // len(self.re_levels)
            remainder = self.n_modes % len(self.re_levels)
            all_dfs = []
            for i, level in enumerate(self.re_levels):
                n = n_per_level + (1 if i < remainder else 0)
                samples = self._sample(rng, n)
                sub_df = pd.DataFrame(samples, columns=[p.name for p in self.params])
                sub_df["re_level"] = level
                all_dfs.append(sub_df)
            df = pd.concat(all_dfs, ignore_index=True)
        else:
            samples = self._sample(rng, self.n_modes)
            df = pd.DataFrame(samples, columns=[p.name for p in self.params])
            df["re_level"] = 0

        df = self._add_derived_features(df)
        df.index.name = "mode_id"

        logger.info(f"Generated {len(df)} operating modes via {self.method}")
        return df

    def _sample(self, rng: np.random.Generator, n: int | None = None) -> np.ndarray:
        """Draw samples in [0,1]^d and scale to parameter bounds."""
        n = n or self.n_modes
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
        """Compute derived features used in clustering and analysis."""
        # Total renewable energy penetration (weighted average across areas)
        df["total_re_pct"] = (
            0.5 * (df["wind_area1_pct"] + df["solar_area1_pct"])
            + 0.5 * (df["wind_area2_pct"] + df["solar_area2_pct"])
        )

        # Inter-area net power flow proxy
        # Positive = Area 1 exports to Area 2, negative = reverse
        df["net_flow_proxy"] = (
            (df["load_area1"] - 1.0)
            - (df["load_area2"] - 1.0)
            + df["gen_dispatch_bias"]
            - 0.5 * (df["wind_area1_pct"] - df["wind_area2_pct"])
        )

        # System inertia proxy: higher RE → lower inertia
        # Base inertia H≈6.5s for GENROU; wind has ~0 inertia contribution
        df["inertia_proxy"] = 1.0 - 0.5 * (
            df["wind_area1_pct"] + df["wind_area2_pct"]
        )

        # Stress index: high load + high RE + large inter-area flow
        df["stress_index"] = (
            0.3 * ((df["load_area1"] + df["load_area2"]) / 2.0 - 0.7) / 0.6
            + 0.4 * df["total_re_pct"]
            + 0.3 * np.abs(df["net_flow_proxy"]) / 0.5
        )

        return df

    def to_scenarios(
        self,
        df: pd.DataFrame,
        fault_bus: int = 7,
        fault_time: float = 1.0,
        clear_time: float = 1.1,
    ) -> list[dict]:
        """Convert operating modes to ANDES-compatible scenario dicts.

        Each mode maps to a simulation scenario with:
        - Load scaling by area
        - Generator output scaling (renewable displacement)
        - RE device injection (REGCA1+REECA1+REPCA1 chains)
        - Standard fault at specified bus

        Args:
            df: DataFrame from generate(), must include 're_level' column.
            fault_bus: Fault location (default bus 7, tie-line bus).
            fault_time: Fault occurrence time.
            clear_time: Fault clearing time.

        Returns:
            List of scenario dicts for ANDESWrapper.evaluate().
        """
        from src.simulator.andes_wrapper import RE_LEVEL_CONFIGS

        scenarios = []
        for _, row in df.iterrows():
            # Load scaling (solar reduces effective load)
            load_scaling = {
                "area1": max(float(row["load_area1"]) * (1.0 - float(row["solar_area1_pct"])), 0.3),
                "area2": max(float(row["load_area2"]) * (1.0 - float(row["solar_area2_pct"])), 0.3),
            }

            re_level = int(row.get("re_level", 0))
            re_cfg = RE_LEVEL_MAP.get(re_level, RE_LEVEL_MAP[0])

            # Generator scaling: RE displaces synchronous gen output
            gen_factor_a1 = re_cfg["gen_factor_a1"]
            gen_factor_a2 = re_cfg["gen_factor_a2"]

            # Wind displaces Area 1 gen (GENROU_1 is main dispatchable gen)
            wind_a1_factor = gen_factor_a1 * (1.0 - row["wind_area1_pct"])
            gen_scaling = {
                "GENROU_1": max(wind_a1_factor, 0.3),
                "GENROU_2": max((1.0 + row["gen_dispatch_bias"]) * gen_factor_a1, 0.3),
            }

            # Wind displaces Area 2 gen (GENROU_3,4)
            wind_a2_factor = gen_factor_a2 * (1.0 - row["wind_area2_pct"])
            gen_scaling["GENROU_3"] = max(wind_a2_factor * 0.6, 0.3)
            gen_scaling["GENROU_4"] = max(wind_a2_factor * 0.4, 0.3)

            scenario = {
                "fault_bus": fault_bus,
                "fault_time": fault_time,
                "clear_time": clear_time,
                "load_scaling": load_scaling,
                "gen_scaling": gen_scaling,
                "line_trip": None,
            }

            # Add RE devices if level > 0
            if re_level > 0 and re_level in RE_LEVEL_CONFIGS:
                scenario["re_devices"] = RE_LEVEL_CONFIGS[re_level]

            # Store mode features for post-processing
            scenario["_mode_features"] = {
                k: float(row[k]) for k in df.columns if not k.startswith("_")
            }

            scenarios.append(scenario)

        return scenarios

    def get_param_bounds(self) -> dict[str, tuple[float, float]]:
        """Return parameter bounds for reference."""
        return {p.name: (p.low, p.high) for p in self.params}

    def is_feasible(self, row: pd.Series) -> bool:
        """Check if a mode is likely to have convergent power flow.

        Feasibility constraint: effective load must not exceed effective generation
        by more than 10% (margin for network losses). RE displacement reduces
        effective conventional generation capacity.
        """
        re_level = int(row.get("re_level", 0))
        re_cfg = RE_LEVEL_MAP.get(re_level, RE_LEVEL_MAP[0])

        for area, gen_key in [("area1", "gen_factor_a1"), ("area2", "gen_factor_a2")]:
            load_eff = float(row[f"load_{area}"]) * (1.0 - float(row[f"solar_{area}_pct"]))
            gen_base = re_cfg[gen_key]
            gen_eff = gen_base * (1.0 - float(row[f"wind_{area}_pct"]))
            # RE devices add ~20 MW per device on 100 MVA base = 0.2 p.u.
            re_gen_added = re_cfg["n_devices"] * 0.2 * 0.5  # rough area split
            total_gen = gen_eff + re_gen_added
            if load_eff > total_gen * 1.25:
                return False
        return True

    def filter_feasible(self, df: pd.DataFrame) -> pd.DataFrame:
        """Filter out modes unlikely to converge in power flow."""
        mask = df.apply(self.is_feasible, axis=1)
        n_filtered = (~mask).sum()
        if n_filtered > 0:
            logger.info(f"Feasibility filter: removed {n_filtered}/{len(df)} modes")
        return df[mask].copy()


def quick_test():
    """Smoke test: generate 100 modes and verify output."""
    gen = ModeGenerator(n_modes=100, seed=42)
    df = gen.generate()

    assert len(df) == 100
    assert "total_re_pct" in df.columns
    assert "inertia_proxy" in df.columns
    assert df["load_area1"].between(0.70, 1.15).all()
    assert df["wind_area1_pct"].between(0.0, 0.40).all()

    scenarios = gen.to_scenarios(df.head(5))
    assert len(scenarios) == 5
    assert "load_scaling" in scenarios[0]
    assert "gen_scaling" in scenarios[0]
    assert scenarios[0]["fault_bus"] == 7

    print(f"Quick test passed: {len(df)} modes generated")
    print(df.describe().to_string())
    return df


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    quick_test()
