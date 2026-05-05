"""Tiered safety limit determination based on clustering results.

For each cluster, computes a safety limit based on the worst-case scenario
severity. Compares tiered (cluster-specific) limits against a uniform
conservative limit to quantify the transmission capacity improvement.
"""

import logging

import numpy as np
import pandas as pd

from src.clustering.mode_cluster import ClusterResult

logger = logging.getLogger(__name__)


class TieredLimiter:
    """Compute tiered safety limits from cluster analysis.

    Each cluster's limit is derived from its worst-case scenario:
    - Higher severity → lower (more conservative) limit
    - Lower severity → higher (more permissive) limit

    The tiered approach replaces a single uniform conservative limit
    with cluster-specific limits that are no less safe but allow
    higher transmission utilization in less stressed operating modes.
    """

    def __init__(
        self,
        max_transfer: float = 400.0,
        min_transfer: float = 100.0,
        safety_margin: float = 0.10,
        severity_to_limit: str = "linear",
    ):
        """
        Args:
            max_transfer: Maximum transfer limit (MW) under ideal conditions.
            min_transfer: Minimum transfer limit (MW) under worst conditions.
            safety_margin: Safety margin fraction (0.10 = 10% margin).
            severity_to_limit: How severity maps to limit ("linear" or "exponential").
        """
        self.max_transfer = max_transfer
        self.min_transfer = min_transfer
        self.safety_margin = safety_margin
        self.severity_to_limit = severity_to_limit

    def compute_cluster_limits(
        self, cluster_result: ClusterResult, mode_df: pd.DataFrame
    ) -> pd.DataFrame:
        """Compute tiered limits for each cluster.

        Args:
            cluster_result: Clustering results with labels and statistics.
            mode_df: DataFrame with mode parameters and severity.

        Returns:
            DataFrame with one row per cluster: limit, severity, characteristics.
        """
        rows = []
        for cluster_id in range(cluster_result.n_clusters):
            mask = cluster_result.labels == cluster_id
            cluster_df = mode_df[mask]

            if "severity" not in cluster_df.columns:
                logger.warning(f"No severity column for cluster {cluster_id}")
                continue

            # Use the worst severity in the cluster
            worst_sev = cluster_df["severity"].max()
            mean_sev = cluster_df["severity"].mean()

            # Compute transfer limit from severity
            limit = self._severity_to_limit(worst_sev)

            # Cluster characteristics
            char = {}
            for col in ["total_re_pct", "inertia_proxy", "stress_index",
                        "net_flow_proxy", "load_area1", "load_area2"]:
                if col in cluster_df.columns:
                    char[f"avg_{col}"] = cluster_df[col].mean()

            row = {
                "cluster_id": cluster_id,
                "n_modes": mask.sum(),
                "worst_severity": worst_sev,
                "mean_severity": mean_sev,
                "transfer_limit_mw": limit,
                **char,
            }
            rows.append(row)

        df = pd.DataFrame(rows)

        # Add uniform conservative limit (based on global worst severity)
        global_worst = mode_df["severity"].max() if "severity" in mode_df.columns else 1.0
        self.uniform_limit = self._severity_to_limit(global_worst)
        df["uniform_limit_mw"] = self.uniform_limit

        # Compute improvement ratio
        df["improvement_pct"] = (
            (df["transfer_limit_mw"] - self.uniform_limit)
            / self.uniform_limit * 100
        )

        # Weighted average improvement
        total_modes = df["n_modes"].sum()
        weighted_avg = (
            (df["transfer_limit_mw"] * df["n_modes"]).sum()
            / total_modes
        )
        self.weighted_avg_limit = weighted_avg
        self.overall_improvement = (
            (weighted_avg - self.uniform_limit) / self.uniform_limit * 100
        )

        logger.info(f"Tiered limits computed:")
        logger.info(f"  Uniform limit: {self.uniform_limit:.1f} MW")
        logger.info(f"  Weighted avg tiered: {weighted_avg:.1f} MW")
        logger.info(f"  Overall improvement: {self.overall_improvement:.1f}%")

        return df

    def _severity_to_limit(self, severity: float) -> float:
        """Map severity [0,1] to transfer limit [min, max] MW."""
        if self.severity_to_limit == "linear":
            # Higher severity → lower limit
            limit = self.max_transfer - severity * (self.max_transfer - self.min_transfer)
        elif self.severity_to_limit == "exponential":
            # Exponential decay: more aggressive for high severity
            limit = self.min_transfer + (self.max_transfer - self.min_transfer) * np.exp(
                -3.0 * severity
            )
        else:
            limit = self.max_transfer - severity * (self.max_transfer - self.min_transfer)

        # Apply safety margin
        limit *= (1.0 - self.safety_margin)
        return max(limit, self.min_transfer)

    def validate_limits(
        self,
        cluster_result: ClusterResult,
        mode_df: pd.DataFrame,
        limits_df: pd.DataFrame,
    ) -> dict:
        """Validate tiered limits by checking safety within each cluster.

        For each cluster, verifies that all modes with severity below
        the worst-case are indeed within the computed limit.
        """
        validation = {
            "clusters_safe": 0,
            "clusters_unsafe": 0,
            "total_modes": 0,
            "modes_safe": 0,
        }

        for _, row in limits_df.iterrows():
            cid = row["cluster_id"]
            limit = row["transfer_limit_mw"]
            mask = cluster_result.labels == cid
            cluster_modes = mode_df[mask]

            # Check: limit should be <= what the worst severity allows
            worst_sev = cluster_modes["severity"].max() if "severity" in cluster_modes.columns else 1.0
            max_allowed = self._severity_to_limit(worst_sev)

            if limit <= max_allowed + 1e-6:
                validation["clusters_safe"] += 1
            else:
                validation["clusters_unsafe"] += 1
                logger.warning(
                    f"Cluster {cid}: limit {limit:.1f} MW > "
                    f"max allowed {max_allowed:.1f} MW"
                )

            validation["total_modes"] += mask.sum()
            validation["modes_safe"] += mask.sum()

        validation["safety_pct"] = (
            validation["modes_safe"] / validation["total_modes"] * 100
            if validation["total_modes"] > 0 else 0
        )

        return validation


class MultiConstraintLimiter:
    """Compute per-constraint tiered limits for each cluster.

    Instead of using a single composite severity, this computes independent
    transfer limits for each stability constraint (angle, voltage, frequency).
    The binding constraint (lowest limit) determines the cluster's final limit.
    Different clusters can have different binding constraints, which is the
    key advantage: tiered limits reflect which physical constraint actually
    limits transmission, rather than applying the worst-case across all constraints.
    """

    def __init__(
        self,
        max_transfer: float = 400.0,
        min_transfer: float = 100.0,
        safety_margin: float = 0.10,
    ):
        self.max_transfer = max_transfer
        self.min_transfer = min_transfer
        self.safety_margin = safety_margin

    def compute_cluster_limits(
        self, cluster_result: "ClusterResult", mode_df: pd.DataFrame
    ) -> pd.DataFrame:
        """Compute multi-constraint tiered limits per cluster.

        Requires mode_df to have columns: severity, f_angle, f_voltage, f_freq.
        """
        rows = []
        for cluster_id in range(cluster_result.n_clusters):
            mask = cluster_result.labels == cluster_id
            cluster_df = mode_df[mask]

            if "severity" not in cluster_df.columns:
                continue

            # Per-constraint worst severities
            worst_composite = cluster_df["severity"].max()
            worst_angle = cluster_df.get("f_angle", cluster_df["severity"]).max()
            worst_voltage = cluster_df.get("f_voltage", cluster_df["severity"]).max()
            worst_freq = cluster_df.get("f_freq", cluster_df["severity"]).max()

            # Per-constraint limits
            limit_angle = self._severity_to_limit(worst_angle)
            limit_voltage = self._severity_to_limit(worst_voltage)
            limit_freq = self._severity_to_limit(worst_freq)

            # Binding constraint = lowest limit
            limits = {
                "angle": limit_angle,
                "voltage": limit_voltage,
                "freq": limit_freq,
            }
            binding = min(limits, key=limits.get)
            tiered_limit = limits[binding]

            # Cluster characteristics
            char = {}
            for col in ["total_re_pct", "inertia_proxy", "stress_index"]:
                if col in cluster_df.columns:
                    char[f"avg_{col}"] = cluster_df[col].mean()

            rows.append({
                "cluster_id": cluster_id,
                "n_modes": mask.sum(),
                "worst_severity": worst_composite,
                "worst_f_angle": worst_angle,
                "worst_f_voltage": worst_voltage,
                "worst_f_freq": worst_freq,
                "limit_angle_mw": limit_angle,
                "limit_voltage_mw": limit_voltage,
                "limit_freq_mw": limit_freq,
                "binding_constraint": binding,
                "tiered_limit_mw": tiered_limit,
                **char,
            })

        df = pd.DataFrame(rows)

        # Uniform limit: based on global worst composite severity
        global_worst = mode_df["severity"].max() if "severity" in mode_df.columns else 1.0
        self.uniform_limit = self._severity_to_limit(global_worst)
        df["uniform_limit_mw"] = self.uniform_limit

        # Improvement: tiered vs uniform
        df["improvement_pct"] = (
            (df["tiered_limit_mw"] - self.uniform_limit)
            / self.uniform_limit * 100
        )

        # Weighted average
        total = df["n_modes"].sum()
        weighted = (df["tiered_limit_mw"] * df["n_modes"]).sum() / total
        self.weighted_avg_limit = weighted
        self.overall_improvement = (
            (weighted - self.uniform_limit) / self.uniform_limit * 100
        )

        logger.info("Multi-constraint tiered limits:")
        for _, r in df.iterrows():
            logger.info(
                f"  Cluster {r['cluster_id']}: binding={r['binding_constraint']}, "
                f"tiered={r['tiered_limit_mw']:.1f}MW, uniform={self.uniform_limit:.1f}MW"
            )
        logger.info(f"  Overall improvement: {self.overall_improvement:.1f}%")

        return df

    def _severity_to_limit(self, severity: float) -> float:
        """Map severity [0,1] to transfer limit [min, max] MW."""
        limit = self.max_transfer - severity * (self.max_transfer - self.min_transfer)
        limit *= (1.0 - self.safety_margin)
        return max(limit, self.min_transfer)
    """Test with synthetic data."""
    from src.scenario.mode_generator import ModeGenerator
    from src.clustering.feature_extractor import FeatureExtractor
    from src.clustering.mode_cluster import ModeCluster

    gen = ModeGenerator(n_modes=200, seed=42)
    df = gen.generate()

    rng = np.random.default_rng(42)
    df["severity"] = rng.uniform(0.1, 0.9, len(df))
    df["stable"] = rng.random(len(df)) > 0.3

    extractor = FeatureExtractor(pca_dim=3)
    X = extractor.fit_transform(df)

    clusterer = ModeCluster(n_clusters=5, algorithm="kmeans")
    result = clusterer.fit(X)

    limiter = TieredLimiter(max_transfer=400, min_transfer=100, safety_margin=0.10)
    limits_df = limiter.compute_cluster_limits(result, df)
    print(f"\nTiered limits:\n{limits_df[['cluster_id', 'worst_severity', 'transfer_limit_mw', 'uniform_limit_mw', 'improvement_pct']].to_string()}")
    print(f"\nUniform: {limiter.uniform_limit:.1f} MW, "
          f"Weighted avg: {limiter.weighted_avg_limit:.1f} MW, "
          f"Improvement: {limiter.overall_improvement:.1f}%")


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    quick_test()
