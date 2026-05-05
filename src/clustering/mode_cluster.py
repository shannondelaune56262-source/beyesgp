"""Operating mode clustering and boundary identification.

Clusters operating modes using K-means/GMM/DBSCAN, identifies boundary modes
(edge cases near cluster borders), and outlier modes (anomalous operating points).
"""

import logging
from dataclasses import dataclass, field

import numpy as np
import pandas as pd
from sklearn.cluster import KMeans, DBSCAN
from sklearn.mixture import GaussianMixture
from sklearn.metrics import silhouette_score

logger = logging.getLogger(__name__)


@dataclass
class ClusterResult:
    """Result from clustering analysis."""
    labels: np.ndarray           # Cluster label per mode
    centers: np.ndarray          # Cluster centers (in scaled feature space)
    n_clusters: int
    silhouette: float            # Silhouette score
    boundary_mask: np.ndarray    # True for boundary modes
    outlier_mask: np.ndarray     # True for outlier modes
    distance_to_center: np.ndarray  # Distance of each mode to its cluster center
    algorithm: str


class ModeCluster:
    """Cluster operating modes and identify boundary/outlier modes.

    Boundary modes: those far from cluster center (distance > 75th percentile).
    Outlier modes: detected by DBSCAN as noise (label = -1).
    """

    def __init__(
        self,
        n_clusters: int = 5,
        algorithm: str = "kmeans",
        boundary_quantile: float = 0.75,
        dbscan_eps: float = 0.5,
        dbscan_min_samples: int = 5,
        seed: int = 42,
    ):
        self.n_clusters = n_clusters
        self.algorithm = algorithm
        self.boundary_quantile = boundary_quantile
        self.dbscan_eps = dbscan_eps
        self.dbscan_min_samples = dbscan_min_samples
        self.seed = seed

    def fit(self, X: np.ndarray) -> ClusterResult:
        """Cluster the feature matrix and identify boundary/outlier modes.

        Args:
            X: Standardized feature matrix (n_modes, n_features).

        Returns:
            ClusterResult with labels, centers, boundary/outlier masks.
        """
        if self.algorithm == "kmeans":
            model = KMeans(
                n_clusters=self.n_clusters,
                random_state=self.seed,
                n_init=10,
            )
            labels = model.fit_predict(X)
            centers = model.cluster_centers_

        elif self.algorithm == "gmm":
            model = GaussianMixture(
                n_components=self.n_clusters,
                random_state=self.seed,
                n_init=3,
            )
            labels = model.fit_predict(X)
            centers = model.means_

        elif self.algorithm == "dbscan":
            model = DBSCAN(
                eps=self.dbscan_eps,
                min_samples=self.dbscan_min_samples,
            )
            labels = model.fit_predict(X)
            n_found = len(set(labels)) - (1 if -1 in labels else 0)
            logger.info(f"DBSCAN found {n_found} clusters, {np.sum(labels == -1)} outliers")
            # Compute centers for non-outlier clusters
            unique_labels = sorted(set(labels) - {-1})
            centers = np.zeros((len(unique_labels), X.shape[1]))
            for i, lbl in enumerate(unique_labels):
                centers[i] = X[labels == lbl].mean(axis=0)
            self.n_clusters = n_found
        else:
            raise ValueError(f"Unknown algorithm: {self.algorithm}")

        # Silhouette score (only if more than 1 cluster and no noise)
        non_noise = labels >= 0
        if len(set(labels[non_noise])) > 1:
            sil = silhouette_score(X[non_noise], labels[non_noise])
        else:
            sil = 0.0
        logger.info(
            f"{self.algorithm}: {self.n_clusters} clusters, "
            f"silhouette={sil:.3f}"
        )

        # Distance to cluster center
        dist = self._compute_distances(X, labels, centers)

        # Boundary identification: distance > threshold within each cluster
        boundary_mask = np.zeros(len(X), dtype=bool)
        for lbl in range(self.n_clusters):
            mask = labels == lbl
            if mask.sum() == 0:
                continue
            threshold = np.quantile(dist[mask], self.boundary_quantile)
            boundary_mask |= mask & (dist >= threshold)

        # Outlier identification: DBSCAN noise or extreme boundary
        outlier_mask = labels == -1

        return ClusterResult(
            labels=labels,
            centers=centers,
            n_clusters=self.n_clusters,
            silhouette=sil,
            boundary_mask=boundary_mask,
            outlier_mask=outlier_mask,
            distance_to_center=dist,
            algorithm=self.algorithm,
        )

    def _compute_distances(
        self, X: np.ndarray, labels: np.ndarray, centers: np.ndarray
    ) -> np.ndarray:
        """Compute Euclidean distance of each point to its cluster center."""
        dist = np.full(len(X), np.inf)
        for lbl in range(len(centers)):
            mask = labels == lbl
            if mask.sum() == 0:
                continue
            diff = X[mask] - centers[lbl]
            dist[mask] = np.linalg.norm(diff, axis=1)
        # For outliers (label=-1), use distance to nearest center
        outlier_mask = labels == -1
        if outlier_mask.any() and len(centers) > 0:
            for i in np.where(outlier_mask)[0]:
                dist[i] = np.min(np.linalg.norm(centers - X[i], axis=1))
        return dist

    def summarize(self, result: ClusterResult, df: pd.DataFrame) -> pd.DataFrame:
        """Generate summary statistics per cluster.

        Args:
            result: ClusterResult from fit().
            df: Original DataFrame with mode parameters.

        Returns:
            DataFrame with one row per cluster, columns for statistics.
        """
        rows = []
        for lbl in range(result.n_clusters):
            mask = result.labels == lbl
            cluster_df = df[mask]

            row = {
                "cluster": lbl,
                "n_modes": mask.sum(),
                "n_boundary": result.boundary_mask[mask].sum(),
                "n_outlier": result.outlier_mask[mask].sum(),
                "avg_severity": cluster_df["severity"].mean() if "severity" in cluster_df.columns else np.nan,
                "max_severity": cluster_df["severity"].max() if "severity" in cluster_df.columns else np.nan,
                "std_severity": cluster_df["severity"].std() if "severity" in cluster_df.columns else np.nan,
                "stable_pct": (cluster_df["stable"].mean() * 100) if "stable" in cluster_df.columns else np.nan,
            }

            # Key mode characteristics
            for col in ["total_re_pct", "inertia_proxy", "stress_index", "net_flow_proxy"]:
                if col in cluster_df.columns:
                    row[f"avg_{col}"] = cluster_df[col].mean()

            rows.append(row)

        return pd.DataFrame(rows)


def auto_select_k(X: np.ndarray, k_range: range = range(3, 10), seed: int = 42) -> int:
    """Select optimal number of clusters via silhouette score."""
    best_k, best_sil = 3, -1.0
    for k in k_range:
        km = KMeans(n_clusters=k, random_state=seed, n_init=10)
        labels = km.fit_predict(X)
        sil = silhouette_score(X, labels)
        logger.info(f"  k={k}: silhouette={sil:.3f}")
        if sil > best_sil:
            best_k, best_sil = k, sil
    logger.info(f"Best k={best_k} (silhouette={best_sil:.3f})")
    return best_k


def quick_test():
    """Smoke test with synthetic data."""
    from src.scenario.mode_generator import ModeGenerator
    from src.clustering.feature_extractor import FeatureExtractor

    gen = ModeGenerator(n_modes=200, seed=42)
    df = gen.generate()

    # Add synthetic severity
    rng = np.random.default_rng(42)
    df["severity"] = rng.uniform(0.1, 0.9, len(df))
    df["f_angle"] = rng.uniform(0, 1, len(df))
    df["f_freq"] = rng.uniform(0, 1, len(df))
    df["f_voltage"] = rng.uniform(0, 1, len(df))
    df["stable"] = rng.random(len(df)) > 0.3
    df["success"] = True

    extractor = FeatureExtractor(pca_dim=3)
    X = extractor.fit_transform(df)

    # Test K-means
    clusterer = ModeCluster(n_clusters=5, algorithm="kmeans")
    result = clusterer.fit(X)
    print(f"\nK-means: {result.n_clusters} clusters, silhouette={result.silhouette:.3f}")
    print(f"  Boundary modes: {result.boundary_mask.sum()}")
    print(f"  Outlier modes: {result.outlier_mask.sum()}")

    # Test auto-k
    print("\nAuto-select k:")
    best_k = auto_select_k(X)

    # Summary
    summary = clusterer.summarize(result, df)
    print(f"\nCluster summary:\n{summary.to_string()}")


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    quick_test()
