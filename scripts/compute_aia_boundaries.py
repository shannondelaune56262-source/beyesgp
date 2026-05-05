"""Compute AIA boundaries per scenario and validate with MOGP.

For each (fault_type, cluster_id) scenario:
1. Extract safe/unsafe points from BO exploration data
2. Compute AIA polyhedral boundary
3. Validate boundary quality using MOGP predictions
4. Optionally verify with actual ANDES simulations

Produces Table 6 (AIA boundary parameters) and Figure 6 (2D projection).
"""

import logging
import sys
import io
import time
from pathlib import Path

import numpy as np
import pandas as pd

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8")
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from scipy.spatial import ConvexHull

from src.boundary.affine_inner import AIABoundary, AffineInnerApproximation
from src.boundary.boundary_manager import BoundaryManager
from src.optimizer.multi_output_gp import MultiOutputGP

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s", datefmt="%H:%M:%S")
logger = logging.getLogger(__name__)

MODE_FEATURES = [
    "wind_area1_pct", "wind_area2_pct", "solar_area1_pct", "solar_area2_pct",
    "load_area1", "load_area2", "gen_dispatch_bias",
]

SEVERITY_THRESHOLD = 0.6

# Bounds for normalizing volumes
BOUNDS = np.array([
    [0.0, 0.40],   # wind_area1_pct
    [0.0, 0.40],   # wind_area2_pct
    [0.0, 0.30],   # solar_area1_pct
    [0.0, 0.30],   # solar_area2_pct
    [0.70, 1.15],  # load_area1
    [0.70, 1.15],  # load_area2
    [-0.15, 0.15], # gen_dispatch_bias
])


def compute_normalized_volume(X_safe: np.ndarray) -> float:
    """Compute volume of safe convex hull in PCA-reduced normalized space.

    In 7D with few points, the convex hull degenerates. We use PCA to find
    the effective subspace and compute volume there, then report as a
    fraction of the total parameter space volume.
    """
    if X_safe.shape[0] <= X_safe.shape[1]:
        return 0.0

    # Normalize each dimension to [0, 1]
    ranges = BOUNDS[:, 1] - BOUNDS[:, 0]
    ranges[ranges < 1e-12] = 1.0
    X_norm = (X_safe - BOUNDS[:, 0]) / ranges

    # Use PCA to find effective dimensionality
    from sklearn.decomposition import PCA
    n_components = min(X_safe.shape[1], X_safe.shape[0] - 1)
    pca = PCA(n_components=n_components)
    X_pca = pca.fit_transform(X_norm)

    # Find effective rank (95% variance)
    cumvar = np.cumsum(pca.explained_variance_ratio_)
    eff_dim = max(2, int(np.searchsorted(cumvar, 0.95) + 1))
    eff_dim = min(eff_dim, n_components)
    X_red = X_pca[:, :eff_dim]

    # Add tiny jitter for numerical stability
    rng = np.random.default_rng(42)
    X_red = X_red + rng.normal(0, 1e-8, size=X_red.shape)

    try:
        hull = ConvexHull(X_red)
        return float(hull.volume)
    except Exception:
        return 0.0


def main():
    output_dir = Path("data/processed/aia_boundaries")
    output_dir.mkdir(parents=True, exist_ok=True)

    sweep_path = "data/processed/re_sweep/re_sweep_results.csv"
    if not Path(sweep_path).exists():
        logger.error(f"RE sweep data not found at {sweep_path}")
        return

    df = pd.read_csv(sweep_path)
    df = df[df["success"] == True].copy()
    logger.info(f"Loaded {len(df)} successful simulations")

    # --- Cluster modes ---
    from sklearn.cluster import KMeans
    from sklearn.preprocessing import StandardScaler

    X_mode = df[MODE_FEATURES].values.astype(float)

    # Remove NaN rows
    valid = ~np.any(np.isnan(X_mode), axis=1)
    df = df[valid].copy()
    X_mode = X_mode[valid]

    scaler = StandardScaler()
    X_scaled = scaler.fit_transform(X_mode)

    n_clusters = min(6, max(2, len(df) // 50))
    kmeans = KMeans(n_clusters=n_clusters, random_state=42, n_init=10)
    df["cluster_id"] = kmeans.fit_predict(X_scaled)

    logger.info(f"Clustered {len(df)} samples into {n_clusters} groups")
    for c in range(n_clusters):
        n_c = (df["cluster_id"] == c).sum()
        logger.info(f"  Cluster {c}: {n_c} samples, avg severity={df[df['cluster_id']==c]['severity'].mean():.3f}")

    # --- Train MOGP for validation ---
    y_dict = {}
    for col in ["f_angle", "f_freq", "f_voltage"]:
        vals = df[col].values.astype(float)
        y_dict[col] = np.nan_to_num(vals, nan=np.nanmean(vals))
    y_dict["severity"] = df["severity"].values.astype(float)

    gp = MultiOutputGP(n_restarts=5, seed=42)
    gp.fit(X_mode, y_dict)
    logger.info("MOGP trained for boundary validation")

    # --- Compute AIA boundaries ---
    aia = AffineInnerApproximation()
    boundary_results = []

    for fault_name in df["fault_name"].unique():
        for cluster_id in df["cluster_id"].unique():
            mask = (df["fault_name"] == fault_name) & (df["cluster_id"] == cluster_id)
            group = df[mask]
            if len(group) < 10:
                continue

            X_group = group[MODE_FEATURES].values.astype(float)
            sev_group = group["severity"].values.astype(float)

            safe_mask = sev_group < SEVERITY_THRESHOLD
            unsafe_mask = sev_group >= SEVERITY_THRESHOLD

            n_safe = safe_mask.sum()
            n_unsafe = unsafe_mask.sum()

            if n_safe < len(MODE_FEATURES) + 1 or n_unsafe < 1:
                logger.debug(f"Skipping {fault_name}/cluster_{cluster_id}: safe={n_safe}, unsafe={n_unsafe}")
                continue

            try:
                boundary = aia.compute(X_group[safe_mask], X_group[unsafe_mask],
                                       threshold=SEVERITY_THRESHOLD, epsilon=0.01)

                # Validate with MOGP
                n_validate = 200
                rng = np.random.default_rng(42)
                # Sample points near the boundary
                center_idx = np.argmin(np.abs(sev_group - SEVERITY_THRESHOLD))
                center = X_group[center_idx]
                X_validate = center + rng.normal(0, 0.05, size=(n_validate, len(MODE_FEATURES)))

                mogp_preds = gp.predict(X_validate)
                mogp_sev = mogp_preds["severity"]["mean"]

                # Check boundary safety via MOGP
                inside_mask = boundary.contains(X_validate)
                if inside_mask.sum() > 0:
                    mogp_safe_rate = (mogp_sev[inside_mask] < SEVERITY_THRESHOLD).mean()
                else:
                    mogp_safe_rate = float("nan")

                vol = compute_normalized_volume(X_group[safe_mask])
                center_c, radius_c = boundary._chebyshev_center()

                boundary_results.append({
                    "fault_name": fault_name,
                    "cluster_id": int(cluster_id),
                    "n_safe": n_safe,
                    "n_unsafe": n_unsafe,
                    "n_dims": boundary.n_dims,
                    "n_facets": boundary.n_facets,
                    "volume": vol,
                    "chebyshev_radius": radius_c,
                    "mogp_safe_rate": mogp_safe_rate,
                })

                logger.info(
                    f"  {fault_name}/cluster_{cluster_id}: "
                    f"facets={boundary.n_facets}, vol={vol:.4f}, "
                    f"ChebR={radius_c:.4f}, MOGP_safe={mogp_safe_rate:.1%}"
                )

            except Exception as e:
                logger.warning(f"AIA failed for {fault_name}/cluster_{cluster_id}: {e}")

    # Save results
    if boundary_results:
        results_df = pd.DataFrame(boundary_results)
        results_df.to_csv(output_dir / "aia_boundary_results.csv", index=False)
        logger.info(f"\nAIA boundary results (Table 6 data):")
        logger.info(results_df.to_string())
    else:
        logger.warning("No boundaries computed — insufficient data")

    # --- Save boundary manager ---
    mgr = BoundaryManager()
    mgr.compute_all_boundaries(
        df, MODE_FEATURES,
        severity_col="severity",
        threshold=SEVERITY_THRESHOLD,
        fault_col="fault_name",
        cluster_col="cluster_id",
        epsilon=0.01,
    )
    mgr.save(output_dir / "boundaries.json")
    logger.info(f"Saved {mgr.n_boundaries} boundaries to {output_dir / 'boundaries.json'}")

    # --- Generate 2D projection for visualization ---
    if len(boundary_results) > 0:
        logger.info("\nGenerating 2D boundary visualization data...")

        # Use ALL data across scenarios for a rich visualization
        # Project onto wind_area1_pct × wind_area2_pct (dims 0,1)
        all_X = df[MODE_FEATURES].values.astype(float)
        all_sev = df["severity"].values.astype(float)

        dim0_range = (all_X[:, 0].min() - 0.02, all_X[:, 0].max() + 0.02)
        dim1_range = (all_X[:, 1].min() - 0.02, all_X[:, 1].max() + 0.02)

        # Generate severity heatmap grid (200×200) using MOGP
        n_grid = 200
        g0 = np.linspace(dim0_range[0], dim0_range[1], n_grid)
        g1 = np.linspace(dim1_range[0], dim1_range[1], n_grid)
        G0, G1 = np.meshgrid(g0, g1)
        grid_2d = np.column_stack([G0.ravel(), G1.ravel()])

        # For MOGP prediction, fix other dims at median values
        median_vals = np.median(all_X, axis=0)
        grid_full = np.tile(median_vals, (len(grid_2d), 1))
        grid_full[:, 0] = grid_2d[:, 0]
        grid_full[:, 1] = grid_2d[:, 1]

        pred = gp.predict(grid_full)
        severity_grid = pred["severity"]["mean"].reshape(n_grid, n_grid)

        # Save heatmap data
        heatmap_df = pd.DataFrame({
            "dim0": G0.ravel(),
            "dim1": G1.ravel(),
            "predicted_severity": severity_grid.ravel(),
        })
        heatmap_df.to_csv(output_dir / "severity_heatmap.csv", index=False)

        # Save data points with labels
        all_proj_df = pd.DataFrame({
            "dim0": all_X[:, 0],
            "dim1": all_X[:, 1],
            "severity": all_sev,
            "label": np.where(all_sev < SEVERITY_THRESHOLD, "safe", "unsafe"),
            "fault_name": df["fault_name"].values,
            "cluster_id": df["cluster_id"].values,
        })
        all_proj_df.to_csv(output_dir / "boundary_2d_projection.csv", index=False)

        # Compute boundary contour for each scenario with enough data
        boundary_contours = {}
        for br in boundary_results:
            fault = br["fault_name"]
            cluster = br["cluster_id"]
            key = BoundaryManager._make_key(fault, cluster)
            bnd = mgr._boundaries.get(key)
            if bnd is None:
                continue

            # Check which grid points are inside boundary
            grid_inside = bnd.contains(grid_full)
            contour_mask = grid_inside.reshape(n_grid, n_grid)

            boundary_contours[f"{fault}_c{cluster}"] = {
                "contour_mask": contour_mask.ravel().tolist(),
                "n_grid": n_grid,
            }

        import json
        (output_dir / "boundary_contours.json").write_text(
            json.dumps(boundary_contours, indent=2), encoding="utf-8"
        )

        logger.info(f"2D visualization data saved: heatmap ({n_grid}×{n_grid}), "
                     f"{len(all_proj_df)} points, {len(boundary_contours)} contours")

    logger.info(f"\nResults saved to {output_dir}")
    logger.info("=== AIA Boundary Computation Complete ===")


if __name__ == "__main__":
    main()
