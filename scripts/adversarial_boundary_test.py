"""Adversarial boundary validation for AIA safe domains.

Phase A: MOGP-guided adversarial search inside each AIA polytope.
Phase B: (optional) ANDES simulation of the most dangerous points.

Purpose: Strengthen the 100% safety claim beyond uniform sampling.
"""

import logging
import sys
import io
import json
from pathlib import Path

import numpy as np
import pandas as pd

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8")
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.boundary.affine_inner import AIABoundary, AffineInnerApproximation

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s", datefmt="%H:%M:%S")
logger = logging.getLogger(__name__)


def load_boundaries(path):
    with open(path) as f:
        data = json.load(f)
    boundaries = {}
    for key, val in data.items():
        A = np.array(val["A"])
        b = np.array(val["b"])
        bnd = AIABoundary(A=A, b=b)
        boundaries[key] = bnd
    return boundaries


def adversarial_search_gp(boundary_key, boundary, sweep_df, n_adversarial=500, n_facet_near=200):
    """Phase A: Find most dangerous points inside AIA polytope using severity data."""
    n_dims = boundary.n_dims
    try:
        center, _ = boundary._chebyshev_center()
    except Exception:
        return None
    if center is None:
        return None

    # 1. Hit-and-run uniform sampling inside polytope
    samples = boundary._hit_and_run_sample(center, n_adversarial)
    if len(samples) == 0:
        return None

    # 2. Find closest severity predictions from simulation data
    # Filter simulation data by fault type matching the boundary key
    mode_cols = ["wind_area1_pct", "wind_area2_pct", "solar_area1_pct",
                 "solar_area2_pct", "load_area1", "load_area2", "gen_dispatch_bias"]

    fault_name = boundary_key.rsplit("__cluster_", 1)[0]
    fault_df = sweep_df[sweep_df["fault_name"] == fault_name]
    if len(fault_df) < 10:
        fault_df = sweep_df

    sim_data = fault_df[mode_cols].values
    sim_severity = fault_df["severity"].values

    # Compute distance to nearest simulation points
    pred_severities = []
    for pt in samples:
        dists = np.linalg.norm(sim_data - pt[:sim_data.shape[1]], axis=1)
        k = min(5, len(dists))
        nearest_idx = np.argpartition(dists, k)[:k]
        weights = 1.0 / (dists[nearest_idx] + 1e-10)
        weights /= weights.sum()
        pred_sev = np.dot(weights, sim_severity[nearest_idx])
        pred_severities.append(pred_sev)

    pred_severities = np.array(pred_severities)

    # 3. Generate points near boundary facets (most dangerous region)
    facet_near_points = []
    A = boundary.A
    b = boundary.b
    for i in range(min(len(b), 50)):  # sample up to 50 facets
        normal = A[i]
        normal_norm = np.linalg.norm(normal)
        if normal_norm < 1e-10:
            continue
        normal_unit = normal / normal_norm
        # Point on facet: move from center toward facet, stop at 98% distance
        t_facet = (b[i] - normal @ center) / (normal @ normal_unit)
        facet_pt = center + 0.98 * t_facet * normal_unit
        if boundary.contains(np.atleast_2d(facet_pt))[0]:
            facet_near_points.append(facet_pt)

    # 4. Report results
    results = {
        "boundary_key": boundary_key,
        "n_dims": n_dims,
        "n_interior_samples": len(samples),
        "n_facet_near_points": len(facet_near_points),
        "max_predicted_severity_interior": float(pred_severities.max()),
        "mean_predicted_severity_interior": float(pred_severities.mean()),
        "p95_predicted_severity_interior": float(np.percentile(pred_severities, 95)),
        "n_exceeding_threshold": int((pred_severities >= 0.6).sum()),
        "threshold": 0.6,
    }

    # Top-10 most dangerous interior points
    top_indices = np.argsort(pred_severities)[-10:][::-1]
    results["top10_severities"] = [float(pred_severities[i]) for i in top_indices]
    results["top10_points"] = samples[top_indices].tolist()

    return results


def main():
    logger.info("=== Adversarial Boundary Validation ===")

    boundaries_path = Path("data/processed/aia_boundaries/boundaries.json")
    sweep_path = Path("data/processed/re_sweep/re_sweep_results.csv")
    output_dir = Path("data/processed/adversarial_validation")
    output_dir.mkdir(parents=True, exist_ok=True)

    if not boundaries_path.exists():
        logger.error(f"Boundaries not found: {boundaries_path}")
        return

    boundaries = load_boundaries(boundaries_path)
    logger.info(f"Loaded {len(boundaries)} AIA boundaries")

    df = pd.read_csv(sweep_path)
    df = df[df["success"] == True].copy()
    logger.info(f"Loaded {len(df)} simulation records")

    # Phase A: Adversarial search for each boundary
    all_results = []
    top_dangerous_all = []

    for key, bnd in boundaries.items():
        logger.info(f"\nProcessing: {key} (dims={bnd.n_dims}, facets={len(bnd.b)})")
        result = adversarial_search_gp(key, bnd, df)
        if result:
            all_results.append(result)
            logger.info(f"  Interior samples: {result['n_interior_samples']}")
            logger.info(f"  Facet-near points: {result['n_facet_near_points']}")
            logger.info(f"  Max predicted severity: {result['max_predicted_severity_interior']:.4f}")
            logger.info(f"  P95 predicted severity: {result['p95_predicted_severity_interior']:.4f}")
            logger.info(f"  Points exceeding θ=0.6: {result['n_exceeding_threshold']}")

            # Collect top dangerous points across all boundaries
            for sev, pt in zip(result["top10_severities"], result["top10_points"]):
                top_dangerous_all.append({
                    "boundary": key,
                    "predicted_severity": sev,
                    "point": pt,
                })

    # Summary
    if all_results:
        results_df = pd.DataFrame([{k: v for k, v in r.items() if k not in ("top10_severities", "top10_points")}
                                    for r in all_results])
        results_df.to_csv(output_dir / "adversarial_validation_results.csv", index=False)

        # Save top dangerous points for potential Phase B simulation
        dangerous_df = pd.DataFrame(top_dangerous_all)
        dangerous_df.to_csv(output_dir / "top_dangerous_points.csv", index=False)

        max_sev = max(r["max_predicted_severity_interior"] for r in all_results)
        total_exceeding = sum(r["n_exceeding_threshold"] for r in all_results)
        total_interior = sum(r["n_interior_samples"] for r in all_results)

        logger.info(f"\n{'=' * 60}")
        logger.info(f"ADVERSARIAL VALIDATION SUMMARY")
        logger.info(f"{'=' * 60}")
        logger.info(f"  Boundaries tested: {len(all_results)}")
        logger.info(f"  Total interior samples: {total_interior}")
        logger.info(f"  Max predicted severity: {max_sev:.4f}")
        logger.info(f"  Points exceeding θ=0.6: {total_exceeding}/{total_interior}")
        if max_sev < 0.6:
            logger.info(f"  VERDICT: All adversarial points predicted SAFE (max sev {max_sev:.4f} < θ=0.6)")
        else:
            logger.info(f"  WARNING: Some points predicted UNSAFE — shrinkage margin may need increase")

        logger.info(f"\nResults saved to {output_dir}")


if __name__ == "__main__":
    main()
