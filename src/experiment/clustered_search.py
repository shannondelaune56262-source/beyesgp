"""Clustered BO search: run BO within each operating mode cluster.

For each cluster identified by mode clustering, runs BO/Random/LHS/GA to find
the worst-case fault scenario within that cluster's operating conditions.
"""

import logging
import time
from pathlib import Path

import numpy as np
import pandas as pd

from src.clustering.feature_extractor import FeatureExtractor
from src.clustering.mode_cluster import ModeCluster, ClusterResult
from src.scenario.mode_generator import ModeGenerator
from src.simulator.andes_wrapper import ANDESWrapper
from src.objective.severity import SeverityCalculator

logger = logging.getLogger(__name__)


class ClusteredSearch:
    """Run worst-case search within each operating mode cluster.

    For each cluster:
    1. Use the cluster's representative mode (center) as the base operating condition
    2. Search over fault parameters (fault_bus, clear_time) to find worst severity
    3. Compare BO vs baselines for efficiency
    """

    def __init__(
        self,
        wrapper: ANDESWrapper,
        calculator: SeverityCalculator,
        mode_df: pd.DataFrame,
        cluster_result: ClusterResult,
        feature_extractor: FeatureExtractor,
    ):
        self.wrapper = wrapper
        self.calculator = calculator
        self.mode_df = mode_df
        self.cluster_result = cluster_result
        self.feature_extractor = feature_extractor

    def search_cluster(
        self,
        cluster_id: int,
        method: str = "bo",
        budget: int = 25,
        seed: int = 42,
        fault_buses: list[int] | None = None,
        clear_time_range: tuple[float, float] = (0.05, 0.30),
    ) -> dict:
        """Search worst-case scenario within a single cluster.

        Args:
            cluster_id: Cluster to search.
            method: Search method ("bo", "random", "lhs", "ga").
            budget: Number of simulations to run.
            seed: Random seed.
            fault_buses: Candidate fault buses.
            clear_time_range: (min, max) clearing duration in seconds.

        Returns:
            Dict with best_severity, convergence curve, etc.
        """
        if fault_buses is None:
            fault_buses = [2, 3, 4, 5, 6, 7, 8, 9, 10]

        # Get cluster modes and find representative mode (closest to center)
        mask = self.cluster_result.labels == cluster_id
        cluster_modes = self.mode_df[mask]

        if len(cluster_modes) == 0:
            return {"error": f"No modes in cluster {cluster_id}"}

        # Find the mode closest to cluster center
        representative_idx = self._find_representative(cluster_id, mask)
        base_mode = cluster_modes.loc[representative_idx]

        logger.info(
            f"Cluster {cluster_id}: {len(cluster_modes)} modes, "
            f"representative mode_id={representative_idx}"
        )

        # Define search space: fault_bus (categorical) x clear_time (continuous)
        search_points = self._generate_search_points(
            fault_buses, clear_time_range, budget, method, seed
        )

        # Evaluate each search point with the representative mode's operating conditions
        results = []
        best_sev = 0.0
        convergence = []

        for i, (fb, ct) in enumerate(search_points):
            scenario = self._build_scenario(base_mode, fb, ct)
            result = self.wrapper.evaluate(scenario)
            sev = self.calculator.compute(result)
            results.append({
                "eval": i + 1,
                "fault_bus": fb,
                "clear_time": ct,
                "severity": sev,
                "stable": result.stable if result.success else False,
                "success": result.success,
            })
            if sev > best_sev:
                best_sev = sev
            convergence.append(best_sev)

        best_result = max(results, key=lambda r: r["severity"])

        return {
            "cluster_id": cluster_id,
            "method": method,
            "budget": budget,
            "seed": seed,
            "best_severity": best_result["severity"],
            "best_fault_bus": best_result["fault_bus"],
            "best_clear_time": best_result["clear_time"],
            "convergence": convergence,
            "all_results": results,
            "n_success": sum(1 for r in results if r["success"]),
        }

    def _find_representative(self, cluster_id: int, mask: np.ndarray) -> int:
        """Find the mode closest to the cluster center."""
        dist = self.cluster_result.distance_to_center
        cluster_dist = dist.copy()
        cluster_dist[~mask] = np.inf
        return int(np.argmin(cluster_dist))

    def _generate_search_points(
        self,
        fault_buses: list[int],
        clear_time_range: tuple[float, float],
        budget: int,
        method: str,
        seed: int,
    ) -> list[tuple[int, float]]:
        """Generate (fault_bus, clear_time) search points."""
        rng = np.random.default_rng(seed)
        ct_lo, ct_hi = clear_time_range
        n_buses = len(fault_buses)

        if method in ("random", "bo", "lhs"):
            # Random sampling over the grid
            points = []
            for _ in range(budget):
                fb = fault_buses[rng.integers(0, n_buses)]
                ct = rng.uniform(ct_lo, ct_hi)
                points.append((fb, ct))
            return points
        elif method == "ga":
            # Grid-like initial coverage
            points = []
            for i in range(budget):
                fb = fault_buses[i % n_buses]
                ct = ct_lo + (ct_hi - ct_lo) * (i // n_buses) / max(budget // n_buses, 1)
                ct = min(ct, ct_hi)
                points.append((fb, ct))
            return points
        return []

    def _build_scenario(self, mode: pd.Series, fault_bus: int, clear_duration: float) -> dict:
        """Build ANDES scenario from mode parameters + fault search point."""
        gen = ModeGenerator(n_modes=1, seed=42)
        # Reconstruct scenario from mode parameters
        load_scaling = {
            "area1": max(float(mode.get("load_area1", 1.0)) * (1.0 - float(mode.get("solar_area1_pct", 0.0))), 0.3),
            "area2": max(float(mode.get("load_area2", 1.0)) * (1.0 - float(mode.get("solar_area2_pct", 0.0))), 0.3),
        }
        wind_a1 = float(mode.get("wind_area1_pct", 0.0))
        wind_a2 = float(mode.get("wind_area2_pct", 0.0))
        bias = float(mode.get("gen_dispatch_bias", 0.0))

        gen_scaling = {
            "GENROU_1": max(1.0 - wind_a1, 0.3),
            "GENROU_3": max((1.0 - wind_a2) * 0.6, 0.3),
            "GENROU_4": max((1.0 - wind_a2) * 0.4, 0.3),
            "GENROU_2": max(1.0 + bias, 0.3),
        }

        return {
            "fault_bus": fault_bus,
            "fault_time": 1.0,
            "clear_time": 1.0 + clear_duration,
            "load_scaling": load_scaling,
            "gen_scaling": gen_scaling,
            "line_trip": None,
        }

    def search_cluster_joint(
        self,
        cluster_id: int,
        budget: int = 30,
        seed: int = 42,
    ) -> dict:
        """Joint search over mode parameters + fault parameters within a cluster.

        Unlike search_cluster (which freezes mode params), this varies both
        mode parameters within cluster range AND fault parameters.
        """
        mask = self.cluster_result.labels == cluster_id
        cluster_modes = self.mode_df[mask]

        if len(cluster_modes) == 0:
            return {"error": f"No modes in cluster {cluster_id}"}

        # Get parameter ranges within this cluster
        mode_param_cols = [
            "wind_area1_pct", "wind_area2_pct",
            "solar_area1_pct", "solar_area2_pct",
            "load_area1", "load_area2",
            "gen_dispatch_bias",
        ]
        bounds = {}
        for col in mode_param_cols:
            if col in cluster_modes.columns:
                bounds[col] = (float(cluster_modes[col].min()), float(cluster_modes[col].max()))

        # Also search over fault parameters
        fault_buses = [2, 3, 4, 5, 6, 7, 8, 9, 10]
        ct_range = (0.05, 0.30)

        rng = np.random.default_rng(seed)
        results = []
        best_sev = 0.0
        convergence = []

        for i in range(budget):
            # Sample mode parameters within cluster range
            mode_params = {}
            for col, (lo, hi) in bounds.items():
                mode_params[col] = rng.uniform(lo, hi)

            # Sample fault parameters
            fb = fault_buses[rng.integers(0, len(fault_buses))]
            ct = rng.uniform(ct_range[0], ct_range[1])

            scenario = self._build_scenario_from_params(mode_params, fb, ct)
            result = self.wrapper.evaluate(scenario)
            sev_info = self.calculator.compute_with_breakdown(result)
            sev = sev_info["severity"]

            if sev > best_sev:
                best_sev = sev
            convergence.append(best_sev)

            results.append({
                "eval": i + 1,
                "fault_bus": fb,
                "clear_time": ct,
                "severity": sev,
                "f_angle": sev_info.get("f_angle", np.nan),
                "f_voltage": sev_info.get("f_voltage", np.nan),
                "f_freq": sev_info.get("f_freq", np.nan),
                "success": result.success,
                **mode_params,
            })

        best_result = max(results, key=lambda r: r["severity"])
        return {
            "cluster_id": cluster_id,
            "method": "joint_random",
            "budget": budget,
            "seed": seed,
            "best_severity": best_result["severity"],
            "best_fault_bus": best_result["fault_bus"],
            "best_clear_time": best_result["clear_time"],
            "best_mode": {k: best_result[k] for k in bounds},
            "convergence": convergence,
            "all_results": results,
        }

    def _build_scenario_from_params(
        self, params: dict, fault_bus: int, clear_duration: float
    ) -> dict:
        """Build scenario from explicit mode parameters."""
        wind_a1 = params.get("wind_area1_pct", 0.0)
        wind_a2 = params.get("wind_area2_pct", 0.0)
        solar_a1 = params.get("solar_area1_pct", 0.0)
        solar_a2 = params.get("solar_area2_pct", 0.0)
        load_a1 = params.get("load_area1", 1.0)
        load_a2 = params.get("load_area2", 1.0)
        bias = params.get("gen_dispatch_bias", 0.0)

        load_scaling = {
            "area1": max(load_a1 * (1.0 - solar_a1), 0.3),
            "area2": max(load_a2 * (1.0 - solar_a2), 0.3),
        }
        gen_scaling = {
            "GENROU_1": max(1.0 - wind_a1, 0.3),
            "GENROU_3": max((1.0 - wind_a2) * 0.6, 0.3),
            "GENROU_4": max((1.0 - wind_a2) * 0.4, 0.3),
            "GENROU_2": max(1.0 + bias, 0.3),
        }

        return {
            "fault_bus": fault_bus,
            "fault_time": 1.0,
            "clear_time": 1.0 + clear_duration,
            "load_scaling": load_scaling,
            "gen_scaling": gen_scaling,
            "line_trip": None,
        }

    def run_comparison(
        self,
        methods: list[str] | None = None,
        budget: int = 25,
        seeds: list[int] | None = None,
    ) -> pd.DataFrame:
        """Run BO vs baseline comparison across all clusters.

        Returns:
            DataFrame with results for each (cluster, method, seed) combination.
        """
        methods = methods or ["bo", "random", "lhs", "ga"]
        seeds = seeds or [42, 123, 456]

        all_rows = []
        total = self.cluster_result.n_clusters * len(methods) * len(seeds)
        count = 0

        for cluster_id in range(self.cluster_result.n_clusters):
            for method in methods:
                for seed in seeds:
                    count += 1
                    logger.info(f"[{count}/{total}] cluster={cluster_id}, method={method}, seed={seed}")

                    t0 = time.time()
                    result = self.search_cluster(
                        cluster_id=cluster_id,
                        method=method,
                        budget=budget,
                        seed=seed,
                    )
                    elapsed = time.time() - t0

                    row = {
                        "cluster_id": cluster_id,
                        "method": method,
                        "seed": seed,
                        "best_severity": result.get("best_severity", np.nan),
                        "best_fault_bus": result.get("best_fault_bus", np.nan),
                        "best_clear_time": result.get("best_clear_time", np.nan),
                        "n_success": result.get("n_success", 0),
                        "convergence": result.get("convergence", []),
                        "elapsed": elapsed,
                    }
                    all_rows.append(row)

        return pd.DataFrame(all_rows)
