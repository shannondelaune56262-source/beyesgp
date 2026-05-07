"""Compute per-scenario transfer capacity limits for IEEE 39-bus system.

Reads IEEE 39 RE sweep results, clusters scenarios by RE distribution mode,
and computes interface transfer limits (MW) for each cluster.

Compares two methods:
  - Uniform limit: overall 10th percentile of interface flow among stable cases
  - Per-cluster flexible limits: 10th percentile within each distribution-mode cluster

Produces ieee39_limits_comparison.csv with attribution of improvement sources.
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

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s", datefmt="%H:%M:%S")
logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Distribution-mode classification
# ---------------------------------------------------------------------------
def classify_distribution_mode(f: float) -> str:
    """Classify RE spatial distribution by west-side fraction.

    Parameters
    ----------
    f : float
        re_west_fraction: share of total RE capacity installed in the west area.

    Returns
    -------
    str
        One of 'west_concentrated', 'balanced', 'east_concentrated'.
    """
    if f >= 0.7:
        return "west_concentrated"
    elif f <= 0.3:
        return "east_concentrated"
    else:
        return "balanced"


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
def main():
    output_dir = Path("data/processed/ieee39_transfer_limits")
    output_dir.mkdir(parents=True, exist_ok=True)

    sweep_path = "data/processed/ieee39_re_sweep/ieee39_re_sweep_results.csv"

    if not Path(sweep_path).exists():
        logger.error(f"IEEE 39 RE sweep data not found at {sweep_path}")
        return

    df = pd.read_csv(sweep_path)
    logger.info(f"Loaded {len(df)} rows from sweep results")

    # Keep only successful (stable) simulations for limit calculation
    if "success" in df.columns:
        df = df[df["success"] == True].copy()
        logger.info(f"  {len(df)} successful simulations after filtering")
    elif "stable" in df.columns:
        df = df[df["stable"] == True].copy()
        logger.info(f"  {len(df)} stable simulations after filtering")
    else:
        logger.warning("No 'success' or 'stable' column found; using all rows")

    # Validate required column
    flow_col = "total_interface_flow_MW"
    if flow_col not in df.columns:
        logger.error(f"Required column '{flow_col}' not found in sweep data. "
                      f"Available columns: {list(df.columns)}")
        return

    # ------------------------------------------------------------------
    # Distribution-mode label
    # ------------------------------------------------------------------
    if "re_west_fraction" not in df.columns:
        logger.error("Required column 're_west_fraction' not found in sweep data.")
        return

    df["distribution_mode"] = df["re_west_fraction"].apply(classify_distribution_mode)
    logger.info(f"Distribution mode counts:\n{df['distribution_mode'].value_counts().to_string()}")

    # ------------------------------------------------------------------
    # KMeans clustering on engineering features
    # ------------------------------------------------------------------
    from sklearn.cluster import KMeans
    from sklearn.preprocessing import StandardScaler

    cluster_features = [
        "re_west_fraction",
        "re_penetration",
        "load_level_west",
        "load_level_east",
    ]

    # Verify all feature columns exist
    missing_cols = [c for c in cluster_features if c not in df.columns]
    if missing_cols:
        logger.error(f"Missing cluster feature columns: {missing_cols}")
        return

    X = df[cluster_features].values.astype(float)
    valid = ~np.any(np.isnan(X), axis=1)
    df = df[valid].copy()
    X = X[valid]
    logger.info(f"  {len(df)} rows after dropping NaN in cluster features")

    scaler = StandardScaler()
    X_scaled = scaler.fit_transform(X)

    n_clusters = 3  # one per expected distribution mode
    kmeans = KMeans(n_clusters=n_clusters, random_state=42, n_init=10)
    df["cluster_id"] = kmeans.fit_predict(X_scaled)

    logger.info(f"KMeans clustering with n_clusters={n_clusters} complete")
    for c in range(n_clusters):
        subset = df[df["cluster_id"] == c]
        logger.info(f"  Cluster {c}: n={len(subset)}, "
                     f"avg re_west_frac={subset['re_west_fraction'].mean():.3f}, "
                     f"avg re_penetration={subset['re_penetration'].mean():.3f}")

    # ------------------------------------------------------------------
    # Method 1: Uniform limit — overall 10th percentile of interface flow
    # ------------------------------------------------------------------
    uniform_limit = np.percentile(df[flow_col], 10)
    logger.info(f"Method 1 (Uniform limit): {uniform_limit:.2f} MW  "
                 f"(10th pct of {len(df)} stable scenarios)")

    # ------------------------------------------------------------------
    # Method 2: Per-cluster flexible limits
    # ------------------------------------------------------------------
    cluster_limits = {}
    for c in range(n_clusters):
        cluster_df = df[df["cluster_id"] == c]
        if len(cluster_df) < 5:
            logger.warning(f"  Cluster {c} has only {len(cluster_df)} samples; "
                           f"falling back to uniform limit")
            cluster_limits[c] = uniform_limit
        else:
            cluster_limits[c] = np.percentile(cluster_df[flow_col], 10)
    logger.info("Method 2 (Per-cluster limits):")
    for c, lim in cluster_limits.items():
        logger.info(f"  Cluster {c}: {lim:.2f} MW")

    # ------------------------------------------------------------------
    # Build comparison table
    # ------------------------------------------------------------------
    comparison_rows = []
    for c in range(n_clusters):
        cluster_df = df[df["cluster_id"] == c]
        n_samples = len(cluster_df)
        n_stable = n_samples  # all rows are stable/successful after filtering

        avg_west_frac = cluster_df["re_west_fraction"].mean()
        avg_re_pen = cluster_df["re_penetration"].mean()
        avg_flow = cluster_df[flow_col].mean()

        cluster_lim = cluster_limits[c]
        improvement = (cluster_lim - uniform_limit) / uniform_limit * 100

        # Determine dominant distribution mode in this cluster
        mode_counts = cluster_df["distribution_mode"].value_counts()
        dominant_mode = mode_counts.index[0] if len(mode_counts) > 0 else "unknown"

        row = {
            "cluster_id": c,
            "distribution_mode": dominant_mode,
            "n_samples": n_samples,
            "n_stable": n_stable,
            "avg_re_west_fraction": round(avg_west_frac, 4),
            "avg_re_penetration": round(avg_re_pen, 4),
            "avg_interface_flow_MW": round(avg_flow, 2),
            "uniform_limit_MW": round(uniform_limit, 2),
            "cluster_limit_MW": round(cluster_lim, 2),
            "improvement_pct": round(improvement, 2),
        }
        comparison_rows.append(row)

    comp_df = pd.DataFrame(comparison_rows)

    # ------------------------------------------------------------------
    # Attribution: how much of the improvement comes from RE distribution
    # ------------------------------------------------------------------
    # Decompose: separate the effect of re_west_fraction (distribution) from
    # the combined re_penetration + load effects.
    # Approach: fit a simple linear model of cluster_limit delta vs features
    #   and report the coefficient attributed to re_west_fraction.
    if n_clusters >= 2:
        # Compute per-cluster deviations from uniform
        deltas = comp_df["cluster_limit_MW"].values - uniform_limit
        avg_west_fracs = comp_df["avg_re_west_fraction"].values
        avg_re_pens = comp_df["avg_re_penetration"].values

        # Correlation-based attribution
        total_var = np.var(deltas)
        if total_var > 0:
            # Simple proportional attribution based on correlation
            corr_west = np.corrcoef(avg_west_fracs, deltas)[0, 1] if len(set(avg_west_fracs)) > 1 else 0.0
            corr_pen = np.corrcoef(avg_re_pens, deltas)[0, 1] if len(set(avg_re_pens)) > 1 else 0.0

            abs_corr_sum = abs(corr_west) + abs(corr_pen) + 1e-12
            attribution_dist = abs(corr_west) / abs_corr_sum * 100
            attribution_pen = abs(corr_pen) / abs_corr_sum * 100
        else:
            attribution_dist = 0.0
            attribution_pen = 0.0

        logger.info(f"\n=== Improvement Attribution ===")
        logger.info(f"  RE distribution (re_west_fraction): {attribution_dist:.1f}%")
        logger.info(f"  RE penetration level:               {attribution_pen:.1f}%")

        comp_df["attribution_dist_pct"] = round(attribution_dist, 1)
        comp_df["attribution_penetration_pct"] = round(attribution_pen, 1)

    # ------------------------------------------------------------------
    # Save results
    # ------------------------------------------------------------------
    out_path = output_dir / "ieee39_limits_comparison.csv"
    comp_df.to_csv(out_path, index=False)

    # ------------------------------------------------------------------
    # Summary
    # ------------------------------------------------------------------
    logger.info("\n" + "=" * 70)
    logger.info("IEEE 39-Bus Transfer Limits Comparison")
    logger.info("=" * 70)
    logger.info(f"\nTotal stable scenarios: {len(df)}")
    logger.info(f"Uniform limit (10th pct):  {uniform_limit:.2f} MW\n")
    logger.info(comp_df.to_string(index=False))

    # Weighted average improvement
    weights = comp_df["n_samples"].values
    improvements = comp_df["improvement_pct"].values
    weighted_avg_improvement = np.average(improvements, weights=weights)
    logger.info(f"\nWeighted avg improvement (cluster vs uniform): {weighted_avg_improvement:+.2f}%")

    # Per-distribution-mode summary
    logger.info("\n--- By Distribution Mode ---")
    mode_summary = comp_df.groupby("distribution_mode").agg(
        n_clusters=("cluster_id", "count"),
        total_samples=("n_samples", "sum"),
        avg_cluster_limit=("cluster_limit_MW", "mean"),
        avg_improvement=("improvement_pct", "mean"),
    )
    logger.info(mode_summary.to_string())

    logger.info(f"\nResults saved to {out_path}")
    logger.info("=== IEEE 39 Transfer Limits Computation Complete ===")


if __name__ == "__main__":
    main()
