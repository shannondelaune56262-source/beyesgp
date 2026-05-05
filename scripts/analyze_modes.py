"""Full clustering analysis pipeline: simulation → clustering → tiered limits.

Reads mode_sweep_results.csv, runs clustering, and generates analysis outputs.
"""

import logging
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.clustering.feature_extractor import FeatureExtractor
from src.clustering.mode_cluster import ModeCluster, ClusterResult, auto_select_k
from src.clustering.limiter import TieredLimiter, MultiConstraintLimiter

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s", datefmt="%H:%M:%S")
logger = logging.getLogger(__name__)

OUTPUT_DIR = Path("data/processed/mode_analysis")
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)


def main():
    # Load simulation results
    results_path = Path("data/processed/mode_sweep/mode_sweep_results.csv")
    if not results_path.exists():
        logger.error(f"Results not found: {results_path}")
        return

    df = pd.read_csv(results_path, index_col=0)
    logger.info(f"Loaded {len(df)} modes from {results_path}")

    # Report simulation success rate
    if "success" in df.columns:
        n_ok = df["success"].sum()
        n_total = len(df)
        logger.info(f"Simulation success: {n_ok}/{n_total} ({100*n_ok/n_total:.1f}%)")

    # Fill NaN severity for failed sims
    if "severity" in df.columns:
        nan_count = df["severity"].isna().sum()
        if nan_count > 0:
            df["severity"] = df["severity"].fillna(1.0)
            logger.info(f"Filled {nan_count} NaN severity values with 1.0")

    # Feature extraction
    extractor = FeatureExtractor(pca_dim=3)
    X = extractor.fit_transform(df)
    X_pca = extractor.fit_pca(X)

    # Save PCA loadings
    loadings = extractor.get_feature_importance()
    loadings.to_csv(OUTPUT_DIR / "pca_loadings.csv")
    logger.info(f"PCA explained variance: {extractor.pca.explained_variance_ratio_}")

    # Auto-select k
    logger.info("Auto-selecting number of clusters...")
    best_k = auto_select_k(X)

    # Clustering
    clusterer = ModeCluster(n_clusters=best_k, algorithm="kmeans")
    result = clusterer.fit(X)

    # Save cluster labels
    df["cluster"] = result.labels
    df["is_boundary"] = result.boundary_mask
    df["is_outlier"] = result.outlier_mask
    df["distance_to_center"] = result.distance_to_center

    # PCA coordinates
    df["PC1"] = X_pca[:, 0]
    df["PC2"] = X_pca[:, 1]
    if X_pca.shape[1] > 2:
        df["PC3"] = X_pca[:, 2]

    # Cluster summary
    summary = clusterer.summarize(result, df)
    summary.to_csv(OUTPUT_DIR / "cluster_summary.csv", index=False)
    logger.info(f"\nCluster summary:\n{summary.to_string()}")

    # Tiered limits (single constraint)
    limiter = TieredLimiter(max_transfer=400, min_transfer=100, safety_margin=0.10)
    limits_df = limiter.compute_cluster_limits(result, df)
    limits_df.to_csv(OUTPUT_DIR / "tiered_limits.csv", index=False)
    logger.info(f"\nTiered limits:\n{limits_df[['cluster_id', 'worst_severity', 'transfer_limit_mw', 'uniform_limit_mw', 'improvement_pct']].to_string()}")
    logger.info(f"Overall improvement: {limiter.overall_improvement:.1f}%")

    # Multi-constraint tiered limits
    mc_limiter = MultiConstraintLimiter(max_transfer=400, min_transfer=100, safety_margin=0.10)
    mc_limits_df = mc_limiter.compute_cluster_limits(result, df)
    mc_limits_df.to_csv(OUTPUT_DIR / "multi_constraint_limits.csv", index=False)
    if "binding_constraint" in mc_limits_df.columns:
        logger.info(f"\nMulti-constraint limits:\n{mc_limits_df[['cluster_id', 'binding_constraint', 'tiered_limit_mw', 'uniform_limit_mw', 'improvement_pct']].to_string()}")
        logger.info(f"Multi-constraint improvement: {mc_limiter.overall_improvement:.1f}%")

    # T08: Validate clustering
    validate_clustering(df, result)

    # Save full annotated results
    df.to_csv(OUTPUT_DIR / "mode_analysis_full.csv")
    logger.info(f"\nFull analysis saved to {OUTPUT_DIR}")


def validate_clustering(df: pd.DataFrame, result: ClusterResult):
    """T08: Validate clustering effectiveness."""
    logger.info("\n=== Clustering Validation (T08) ===")

    if "severity" not in df.columns:
        logger.warning("No severity column, skipping validation")
        return

    global_std = df["severity"].std()

    # Cluster intra-cluster severity std vs global
    cluster_stds = []
    for lbl in range(result.n_clusters):
        mask = result.labels == lbl
        if mask.sum() > 1:
            cluster_std = df.loc[mask, "severity"].std()
            cluster_stds.append(cluster_std)
            logger.info(f"  Cluster {lbl}: std={cluster_std:.4f} (global={global_std:.4f}, ratio={cluster_std/global_std:.2f})")

    avg_cluster_std = np.mean(cluster_stds)
    logger.info(f"  Avg cluster std: {avg_cluster_std:.4f} vs Global std: {global_std:.4f}")
    logger.info(f"  Reduction ratio: {avg_cluster_std/global_std:.2%}")

    # Boundary vs center severity
    boundary_sev = df.loc[df["is_boundary"], "severity"].mean()
    center_sev = df.loc[~df["is_boundary"], "severity"].mean()
    logger.info(f"  Boundary avg severity: {boundary_sev:.4f}")
    logger.info(f"  Center avg severity: {center_sev:.4f}")
    logger.info(f"  Boundary > Center: {boundary_sev > center_sev}")

    # Global worst captured?
    worst_idx = df["severity"].idxmax()
    is_boundary = df.loc[worst_idx, "is_boundary"]
    logger.info(f"  Global worst (sev={df.loc[worst_idx, 'severity']:.4f}): boundary={is_boundary}")

    return {
        "silhouette": result.silhouette,
        "avg_cluster_std": avg_cluster_std,
        "global_std": global_std,
        "reduction_ratio": avg_cluster_std / global_std,
        "boundary_sev": boundary_sev,
        "center_sev": center_sev,
    }


if __name__ == "__main__":
    main()
