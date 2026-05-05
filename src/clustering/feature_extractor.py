"""Feature extraction and dimensionality reduction for operating mode clustering.

Extracts meaningful features from operating mode definitions and simulation results,
then reduces dimensionality via PCA for visualization and clustering.
"""

import logging

import numpy as np
import pandas as pd
from sklearn.decomposition import PCA
from sklearn.preprocessing import StandardScaler

logger = logging.getLogger(__name__)

# Default feature columns used for clustering
DEFAULT_FEATURE_COLS = [
    "wind_area1_pct",
    "wind_area2_pct",
    "solar_area1_pct",
    "solar_area2_pct",
    "load_area1",
    "load_area2",
    "gen_dispatch_bias",
]

# Include derived features
DERIVED_FEATURE_COLS = [
    "total_re_pct",
    "net_flow_proxy",
    "inertia_proxy",
    "stress_index",
]

ALL_FEATURE_COLS = DEFAULT_FEATURE_COLS + DERIVED_FEATURE_COLS

# Severity-related columns (added after simulation)
SEVERITY_COLS = [
    "severity",
    "f_angle",
    "f_freq",
    "f_voltage",
]


class FeatureExtractor:
    """Extract features from mode definitions and optionally simulation results.

    Features are standardized before PCA. The scaler is stored for later use
    (e.g., transforming new modes into the same feature space).
    """

    def __init__(
        self,
        feature_cols: list[str] | None = None,
        include_severity: bool = True,
        pca_dim: int = 2,
    ):
        self.feature_cols = feature_cols or ALL_FEATURE_COLS
        self.include_severity = include_severity
        self.pca_dim = pca_dim
        self.scaler = StandardScaler()
        self.pca = PCA(n_components=pca_dim)
        self._fitted = False

    def fit_transform(self, df: pd.DataFrame) -> np.ndarray:
        """Extract features, standardize, and apply PCA.

        Args:
            df: DataFrame with mode definitions and optionally severity columns.

        Returns:
            Standardized feature matrix (before PCA) if you need raw features,
            or PCA-transformed matrix for clustering/visualization.
        """
        cols = list(self.feature_cols)
        if self.include_severity:
            for c in SEVERITY_COLS:
                if c in df.columns:
                    cols.append(c)

        # Select available columns
        available = [c for c in cols if c in df.columns]
        missing = set(cols) - set(available)
        if missing:
            logger.warning(f"Missing feature columns: {missing}")

        X = df[available].values.astype(np.float64)

        # Handle NaN (fill with column median)
        nan_mask = np.isnan(X)
        if nan_mask.any():
            medians = np.nanmedian(X, axis=0)
            for j in range(X.shape[1]):
                X[nan_mask[:, j], j] = medians[j]
            logger.info(f"Filled {nan_mask.sum()} NaN values with column medians")

        # Standardize
        X_scaled = self.scaler.fit_transform(X)
        self._feature_names = available
        self._fitted = True

        return X_scaled

    def transform(self, df: pd.DataFrame) -> np.ndarray:
        """Transform new data using fitted scaler."""
        if not self._fitted:
            raise RuntimeError("Must call fit_transform first")

        available = [c for c in self._feature_names if c in df.columns]
        X = df[available].values.astype(np.float64)

        nan_mask = np.isnan(X)
        if nan_mask.any():
            medians = np.nanmedian(X, axis=0)
            for j in range(X.shape[1]):
                X[nan_mask[:, j], j] = medians[j]

        return self.scaler.transform(X)

    def fit_pca(self, X_scaled: np.ndarray) -> np.ndarray:
        """Fit PCA and return reduced representation."""
        self.pca.fit(X_scaled)
        explained = self.pca.explained_variance_ratio_
        logger.info(
            f"PCA({self.pca_dim}): explained variance = "
            f"{explained.sum():.1%} ({', '.join(f'{v:.1%}' for v in explained)})"
        )
        return self.pca.transform(X_scaled)

    def transform_pca(self, X_scaled: np.ndarray) -> np.ndarray:
        """Transform using fitted PCA."""
        return self.pca.transform(X_scaled)

    def get_feature_importance(self) -> pd.DataFrame:
        """Get PCA loadings (feature contributions to principal components)."""
        if not self._fitted:
            raise RuntimeError("Must call fit_transform first")

        loadings = pd.DataFrame(
            self.pca.components_.T,
            index=self._feature_names,
            columns=[f"PC{i+1}" for i in range(self.pca_dim)],
        )
        return loadings


def quick_test():
    """Test with synthetic data."""
    from src.scenario.mode_generator import ModeGenerator

    gen = ModeGenerator(n_modes=200, seed=42)
    df = gen.generate()

    # Add synthetic severity for testing
    rng = np.random.default_rng(42)
    df["severity"] = rng.uniform(0.1, 0.9, len(df))
    df["f_angle"] = rng.uniform(0, 1, len(df))
    df["f_freq"] = rng.uniform(0, 1, len(df))
    df["f_voltage"] = rng.uniform(0, 1, len(df))

    extractor = FeatureExtractor(pca_dim=3)
    X = extractor.fit_transform(df)
    X_pca = extractor.fit_pca(X)

    print(f"Feature matrix: {X.shape}")
    print(f"PCA output: {X_pca.shape}")
    print(f"\nPCA loadings:\n{extractor.get_feature_importance().round(3).to_string()}")


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    quick_test()
