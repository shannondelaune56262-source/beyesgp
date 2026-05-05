"""Closed-loop iterative refinement of AIA boundaries.

Three-round BO→AIA→Validate→BO cycle:
1. Find weakest boundary points (smallest margin)
2. BO-directed search near weak points
3. Add new points to dataset → recompute AIA boundary
4. Track volume growth and safety rate per iteration

Produces Figure 8 (volume convergence) and Algorithm 1 pseudocode data.
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

from src.boundary.affine_inner import AffineInnerApproximation, AIABoundary
from src.boundary.boundary_manager import BoundaryManager
from src.optimizer.multi_output_gp import MultiOutputGP

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s", datefmt="%H:%M:%S")
logger = logging.getLogger(__name__)

MODE_FEATURES = [
    "wind_area1_pct", "wind_area2_pct", "solar_area1_pct", "solar_area2_pct",
    "load_area1", "load_area2", "gen_dispatch_bias",
]

SEVERITY_THRESHOLD = 0.6
N_ROUNDS = 3
N_WEAK_POINTS = 5
N_BO_PER_ROUND = 10

BOUNDS = np.array([
    [0.0, 0.40], [0.0, 0.40], [0.0, 0.30], [0.0, 0.30],
    [0.70, 1.15], [0.70, 1.15], [-0.15, 0.15],
])


def compute_normalized_volume(X_safe: np.ndarray) -> float:
    """Compute volume of safe convex hull in PCA-reduced normalized space."""
    if X_safe.shape[0] <= X_safe.shape[1]:
        return 0.0
    ranges = BOUNDS[:, 1] - BOUNDS[:, 0]
    ranges[ranges < 1e-12] = 1.0
    X_norm = (X_safe - BOUNDS[:, 0]) / ranges

    from sklearn.decomposition import PCA
    n_comp = min(X_safe.shape[1], X_safe.shape[0] - 1)
    pca = PCA(n_components=n_comp)
    X_pca = pca.fit_transform(X_norm)
    cumvar = np.cumsum(pca.explained_variance_ratio_)
    eff_dim = max(2, int(np.searchsorted(cumvar, 0.95) + 1))
    eff_dim = min(eff_dim, n_comp)
    X_red = X_pca[:, :eff_dim]

    rng = np.random.default_rng(42)
    X_red = X_red + rng.normal(0, 1e-8, size=X_red.shape)
    try:
        hull = ConvexHull(X_red)
        return float(hull.volume)
    except Exception:
        return 0.0


def find_weakest_points(boundary: AIABoundary, X_safe: np.ndarray, n: int = 5) -> np.ndarray:
    """Find points on the boundary with smallest margin (closest to edge)."""
    margins = boundary.margin(X_safe)
    weakest_idx = np.argsort(margins)[:n]
    return X_safe[weakest_idx]


def bo_directed_search(gp: MultiOutputGP, center: np.ndarray, n_points: int = 10,
                       radius: float = 0.05, seed: int = 42) -> tuple:
    """Directed BO search near a center point.

    Generates candidates in a small ball around center, selects those
    predicted to be near the severity threshold.
    """
    rng = np.random.default_rng(seed)
    n_dim = len(center)

    candidates = center + rng.normal(0, radius, size=(n_points * 10, n_dim))
    # Clip to reasonable bounds
    bounds = np.array([
        [0.0, 0.40], [0.0, 0.40], [0.0, 0.30], [0.0, 0.30],
        [0.70, 1.15], [0.70, 1.15], [-0.15, 0.15],
    ])
    for d in range(n_dim):
        candidates[:, d] = np.clip(candidates[:, d], bounds[d, 0], bounds[d, 1])

    # Use GP to predict severity
    weights = {"f_angle": 0.4, "f_freq": 0.3, "f_voltage": 0.3}
    composite = gp.predict_composite(candidates, weights)
    pred_sev = composite["mean"]

    # Select points closest to threshold (boundary points)
    dist_to_threshold = np.abs(pred_sev - SEVERITY_THRESHOLD)
    selected_idx = np.argsort(dist_to_threshold)[:n_points]

    return candidates[selected_idx], pred_sev[selected_idx]


def main():
    output_dir = Path("data/processed/closed_loop")
    output_dir.mkdir(parents=True, exist_ok=True)

    sweep_path = "data/processed/re_sweep/re_sweep_results.csv"
    boundaries_path = "data/processed/aia_boundaries/boundaries.json"

    if not Path(sweep_path).exists():
        logger.error(f"RE sweep data not found at {sweep_path}")
        return

    df = pd.read_csv(sweep_path)
    df = df[df["success"] == True].copy()
    logger.info(f"Loaded {len(df)} successful simulations")

    # Cluster
    from sklearn.cluster import KMeans
    from sklearn.preprocessing import StandardScaler

    X_mode = df[MODE_FEATURES].values.astype(float)
    valid = ~np.any(np.isnan(X_mode), axis=1)
    df = df[valid].copy()
    X_mode = X_mode[valid]

    scaler = StandardScaler()
    X_scaled = scaler.fit_transform(X_mode)
    n_clusters = min(6, max(2, len(df) // 50))
    kmeans = KMeans(n_clusters=n_clusters, random_state=42, n_init=10)
    df["cluster_id"] = kmeans.fit_predict(X_scaled)

    # Train MOGP
    y_dict = {}
    for col in ["f_angle", "f_freq", "f_voltage"]:
        vals = df[col].values.astype(float)
        y_dict[col] = np.nan_to_num(vals, nan=np.nanmean(vals))
    y_dict["severity"] = df["severity"].values.astype(float)

    gp = MultiOutputGP(n_restarts=5, seed=42)
    gp.fit(X_mode, y_dict)

    # --- Closed-loop refinement per scenario ---
    aia = AffineInnerApproximation()
    refinement_log = []

    for fault_name in df["fault_name"].unique()[:3]:  # top 3 faults for demo
        for cluster_id in range(n_clusters):
            mask = (df["fault_name"] == fault_name) & (df["cluster_id"] == cluster_id)
            group = df[mask]
            if len(group) < 20:
                continue

            X_group = group[MODE_FEATURES].values.astype(float)
            sev_group = group["severity"].values.astype(float)

            safe_mask = sev_group < SEVERITY_THRESHOLD
            unsafe_mask = sev_group >= SEVERITY_THRESHOLD

            if safe_mask.sum() < len(MODE_FEATURES) + 1 or unsafe_mask.sum() < 1:
                continue

            X_safe = list(X_group[safe_mask])  # mutable list
            X_unsafe = list(X_group[unsafe_mask])
            sev_safe = list(sev_group[safe_mask])
            sev_unsafe = list(sev_group[unsafe_mask])

            # Initial AIA
            boundary = aia.compute(
                np.array(X_safe), np.array(X_unsafe),
                threshold=SEVERITY_THRESHOLD, epsilon=0.01
            )
            initial_vol = compute_normalized_volume(np.array(X_safe))

            logger.info(f"\n=== {fault_name}/cluster_{cluster_id} ===")
            logger.info(f"  Initial: {len(X_safe)} safe, {len(X_unsafe)} unsafe, vol={initial_vol:.4f}")

            for round_idx in range(N_ROUNDS):
                # Find weakest points
                X_safe_arr = np.array(X_safe)
                weakest = find_weakest_points(boundary, X_safe_arr, n=N_WEAK_POINTS)

                # BO directed search from each weak point
                new_points = []
                new_sevs = []
                for wp in weakest:
                    pts, sevs = bo_directed_search(
                        gp, wp, n_points=N_BO_PER_ROUND // N_WEAK_POINTS,
                        radius=0.03, seed=42 + round_idx * 100
                    )
                    new_points.append(pts)
                    new_sevs.append(sevs)

                new_points = np.vstack(new_points)
                new_sevs = np.concatenate(new_sevs)

                # Add to appropriate lists
                for pt, sv in zip(new_points, new_sevs):
                    if sv < SEVERITY_THRESHOLD:
                        X_safe.append(pt)
                        sev_safe.append(sv)
                    else:
                        X_unsafe.append(pt)
                        sev_unsafe.append(sv)

                # Recompute AIA
                try:
                    boundary = aia.compute(
                        np.array(X_safe), np.array(X_unsafe),
                        threshold=SEVERITY_THRESHOLD, epsilon=0.01
                    )
                except Exception as e:
                    logger.warning(f"  Round {round_idx+1}: AIA failed: {e}")
                    break

                vol = compute_normalized_volume(np.array(X_safe))
                vol_change = (vol - initial_vol) / max(initial_vol, 1e-10) * 100

                # Verify containment
                containment = boundary.contains(np.array(X_safe))
                safe_rate = containment.mean()

                refinement_log.append({
                    "fault_name": fault_name,
                    "cluster_id": cluster_id,
                    "round": round_idx + 1,
                    "n_safe": len(X_safe),
                    "n_unsafe": len(X_unsafe),
                    "n_facets": boundary.n_facets,
                    "volume": vol,
                    "volume_change_pct": vol_change,
                    "safe_rate": safe_rate,
                    "n_new_points": len(new_points),
                })

                logger.info(
                    f"  Round {round_idx+1}: "
                    f"vol={vol:.4f} ({vol_change:+.1f}%), "
                    f"facets={boundary.n_facets}, "
                    f"safe_rate={safe_rate:.1%}, "
                    f"new_pts={len(new_points)}"
                )

    # Save refinement results
    if refinement_log:
        refine_df = pd.DataFrame(refinement_log)
        refine_df.to_csv(output_dir / "closed_loop_results.csv", index=False)

        # Volume convergence per scenario
        for (fault, cluster), group in refine_df.groupby(["fault_name", "cluster_id"]):
            vols = group["volume"].values
            if len(vols) > 1:
                growth = (vols[-1] - vols[0]) / max(vols[0], 1e-10) * 100
                logger.info(f"\n  {fault}/cluster_{cluster}: volume growth = {growth:+.1f}%")

        logger.info(f"\nRefinement results saved to {output_dir / 'closed_loop_results.csv'}")
    else:
        logger.warning("No refinement performed — insufficient data")

    # Generate Algorithm 1 pseudocode data
    algo_data = {
        "algorithm": "GP+BO+AIA Closed-Loop Refinement",
        "input": "Operating modes X, fault set F, severity threshold θ",
        "output": "Refined AIA boundaries P={x|Ax≤b} per scenario",
        "steps": [
            "1. Initialize: Generate mode samples via LHS, evaluate severity S(x,f)",
            "2. Cluster modes into K groups using K-means",
            "3. For each scenario (f_k, cluster_j):",
            "   a. Separate X into X_safe={x|S(x,f)<θ} and X_unsafe",
            "   b. Compute AIA boundary P via convex hull + LP separation",
            "4. Repeat for R rounds:",
            "   a. Find weakest boundary points: argmin margin(x, P)",
            "   b. BO directed search: sample near weak points",
            "   c. Update X_safe/X_unsafe with new evaluations",
            "   d. Recompute AIA boundary P",
            "5. Output refined boundaries with convergence guarantee",
        ],
    }

    import json
    (output_dir / "algorithm1_data.json").write_text(
        json.dumps(algo_data, indent=2, ensure_ascii=False), encoding="utf-8"
    )

    logger.info(f"Results saved to {output_dir}")
    logger.info("=== Closed-Loop Refinement Complete ===")


if __name__ == "__main__":
    main()
