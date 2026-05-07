"""Compute per-scenario transfer capacity limits from AIA boundaries.

Converts AIA boundaries to engineering transfer limits on inter-area tie lines.
Compares 4 methods: uniform, linear-cluster, sigmoid-cluster, AIA-boundary.

Produces Table 7 and Figure 7 data.
"""

import logging
import sys
import io
from pathlib import Path

import numpy as np
import pandas as pd

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8")
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.boundary.boundary_manager import BoundaryManager
from src.boundary.tiered_limit_converter import AIAToTransferLimit

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s", datefmt="%H:%M:%S")
logger = logging.getLogger(__name__)


def main():
    output_dir = Path("data/processed/transfer_limits")
    output_dir.mkdir(parents=True, exist_ok=True)

    sweep_path = "data/processed/re_sweep/re_sweep_results.csv"
    boundaries_path = "data/processed/aia_boundaries/boundaries.json"

    if not Path(sweep_path).exists():
        logger.error(f"RE sweep data not found at {sweep_path}")
        return

    df = pd.read_csv(sweep_path)
    df = df[df["success"] == True].copy()
    logger.info(f"Loaded {len(df)} successful simulations")

    # Cluster for scenario-based limits (RE+sync machine only, NOT load)
    # Physical decomposition: stability-determining factors (w1,w2,s1,s2,r)
    # vs power-demanding factors (l1,l2,delta). Clustering on RE+sync only
    # allows load to vary freely within each cluster, making limit adaptivity
    # physically meaningful.
    from sklearn.cluster import KMeans
    from sklearn.preprocessing import StandardScaler

    mode_features = [
        "wind_area1_pct", "wind_area2_pct", "solar_area1_pct", "solar_area2_pct",
        "re_level",
    ]

    X_mode = df[mode_features].values.astype(float)
    valid = ~np.any(np.isnan(X_mode), axis=1)
    df = df[valid].copy()
    X_mode = X_mode[valid]

    scaler = StandardScaler()
    X_scaled = scaler.fit_transform(X_mode)
    n_clusters = min(6, max(2, len(df) // 50))
    kmeans = KMeans(n_clusters=n_clusters, random_state=42, n_init=10)
    df["cluster_id"] = kmeans.fit_predict(X_scaled)

    # --- Method 1: Uniform limit ---
    # Single limit for all scenarios based on worst-case severity
    worst_sev = df["severity"].max()
    uniform_limit = max(0.4, 1.2 - 0.8 * worst_sev)  # conservative
    logger.info(f"Method 1 (Uniform): limit = {uniform_limit:.3f}")

    # --- Method 2: Linear cluster-based ---
    linear_limits = {}
    for c in range(n_clusters):
        cluster_sev = df[df["cluster_id"] == c]["severity"].mean()
        linear_limits[c] = max(0.4, 1.2 - 0.6 * cluster_sev)

    logger.info(f"Method 2 (Linear cluster): {linear_limits}")

    # --- Method 3: Sigmoid cluster-based ---
    sigmoid_limits = {}
    converter = AIAToTransferLimit()
    for c in range(n_clusters):
        cluster_sev = df[df["cluster_id"] == c]["severity"].mean()
        sigmoid_limits[c] = converter.sigmoid_limit(cluster_sev, threshold=0.6)

    logger.info(f"Method 3 (Sigmoid cluster): {sigmoid_limits}")

    # --- Method 4: AIA boundary-based ---
    aia_limits = {}
    if Path(boundaries_path).exists():
        mgr = BoundaryManager.load(boundaries_path)

        # Compute per-scenario severity for AIA limit calculation
        scenario_severities = {}
        for fault_name in df["fault_name"].unique():
            for cluster_id in range(n_clusters):
                mask = (df["fault_name"] == fault_name) & (df["cluster_id"] == cluster_id)
                group = df[mask]
                if len(group) > 0:
                    key = f"{fault_name}__cluster_{cluster_id}"
                    scenario_severities[key] = group["severity"].mean()

        aia_converter = AIAToTransferLimit(flow_dim_idx=-1, flow_range=(0.3, 1.3), method="chebyshev")
        aia_limits_raw = aia_converter.compute_all_limits(mgr, severities=scenario_severities)
        # Map to cluster IDs
        for key, limit in aia_limits_raw.items():
            parts = key.split("__cluster_")
            if len(parts) == 2:
                fault = parts[0]
                cid = int(parts[1])
                # Average across fault types for each cluster
                if cid not in aia_limits:
                    aia_limits[cid] = []
                aia_limits[cid].append(limit)

        aia_limits = {c: np.mean(v) for c, v in aia_limits.items()}
        # Fallback for clusters without boundaries: use sigmoid (never worse than no-AIA)
        for c in range(n_clusters):
            if c not in aia_limits:
                aia_limits[c] = sigmoid_limits.get(c, uniform_limit)
        logger.info(f"Method 4 (AIA boundary): {aia_limits}")
    else:
        logger.warning(f"Boundaries file not found at {boundaries_path}")
        aia_limits = {c: sigmoid_limits.get(c, 0.8) for c in range(n_clusters)}

    # --- Build comparison table ---
    comparison_rows = []
    for c in range(n_clusters):
        cluster_df = df[df["cluster_id"] == c]
        n_samples = len(cluster_df)
        avg_sev = cluster_df["severity"].mean()

        row = {
            "cluster_id": c,
            "n_samples": n_samples,
            "avg_severity": avg_sev,
            "uniform_limit": uniform_limit,
            "linear_limit": linear_limits.get(c, uniform_limit),
            "sigmoid_limit": sigmoid_limits.get(c, uniform_limit),
            "aia_limit": aia_limits.get(c, uniform_limit),
        }

        # Compute improvement over uniform
        for method in ["linear", "sigmoid", "aia"]:
            method_limit = row[f"{method}_limit"]
            improvement = (method_limit - uniform_limit) / uniform_limit * 100
            row[f"{method}_improvement_pct"] = improvement

        # Decompose total improvement into clustering vs AIA geometry
        sigmoid_val = row["sigmoid_limit"]
        aia_val = row["aia_limit"]
        clustering_pct = (sigmoid_val - uniform_limit) / uniform_limit * 100
        aia_geometry_pct = (aia_val - sigmoid_val) / uniform_limit * 100
        row["clustering_contribution_pct"] = clustering_pct
        row["aia_geometry_contribution_pct"] = aia_geometry_pct

        comparison_rows.append(row)

    comp_df = pd.DataFrame(comparison_rows)
    comp_df.to_csv(output_dir / "transfer_limits_comparison.csv", index=False)

    # Summary
    logger.info("\n=== Transfer Limits Comparison (Table 7) ===")
    logger.info(comp_df.to_string())

    # Weighted average improvement
    weights = comp_df["n_samples"].values
    for method in ["linear", "sigmoid", "aia"]:
        improvements = comp_df[f"{method}_improvement_pct"].values
        weighted_avg = np.average(improvements, weights=weights)
        logger.info(f"  {method} weighted avg improvement: {weighted_avg:+.1f}%")

    # Decomposition summary
    clustering_wavg = np.average(comp_df["clustering_contribution_pct"].values, weights=weights)
    aia_geo_wavg = np.average(comp_df["aia_geometry_contribution_pct"].values, weights=weights)
    total_wavg = clustering_wavg + aia_geo_wavg
    logger.info(f"\n=== Improvement Decomposition ===")
    logger.info(f"  Clustering (sigmoid vs uniform): {clustering_wavg:+.1f}%")
    logger.info(f"  AIA geometry (AIA vs sigmoid):   {aia_geo_wavg:+.1f}%")
    logger.info(f"  Total (AIA vs uniform):          {total_wavg:+.1f}%")

    logger.info(f"\nResults saved to {output_dir}")
    logger.info("=== Transfer Limits Computation Complete ===")


if __name__ == "__main__":
    main()
