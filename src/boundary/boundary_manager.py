"""Multi-scenario boundary manager for safe-set AIA boundaries.

Manages one AIA boundary per (fault_type, cluster_id) pair and provides
aggregate safety queries across all scenarios.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import numpy as np
import pandas as pd

from src.boundary.affine_inner import AIABoundary, AffineInnerApproximation

logger = logging.getLogger(__name__)


class BoundaryManager:
    """Manage AIA boundaries keyed by (fault_name, cluster_id).

    Each scenario has its own polyhedral boundary P = {x | Ax <= b}.
    A point is globally safe only if it is inside *every* scenario boundary.
    """

    def __init__(self) -> None:
        self._boundaries: Dict[str, AIABoundary] = {}
        # key format: "{fault_name}__cluster_{id}"

    @staticmethod
    def _make_key(fault_name: str, cluster_id: int) -> str:
        return f"{fault_name}__cluster_{cluster_id}"

    # ------------------------------------------------------------------
    # Construction
    # ------------------------------------------------------------------

    def compute_all_boundaries(
        self,
        modes_df: pd.DataFrame,
        features: List[str],
        severity_col: str = "severity",
        threshold: float = 0.6,
        fault_col: str = "fault_name",
        cluster_col: str = "cluster_id",
        epsilon: float = 0.01,
    ) -> None:
        """Compute AIA boundaries for each (fault, cluster) group.

        Parameters
        ----------
        modes_df : pd.DataFrame
            Must contain columns for features, severity, fault_name, cluster_id.
        features : list[str]
            Column names used as the parameter-space coordinates.
        severity_col : str
            Column whose value determines safe (< threshold) vs unsafe.
        threshold : float
            Severity threshold for safe/unsafe split.
        fault_col, cluster_col : str
            Grouping columns.
        epsilon : float
            Margin shrinkage for the AIA algorithm.
        """
        aia = AffineInnerApproximation()
        groups = modes_df.groupby([fault_col, cluster_col])
        n_computed = 0

        for (fault, cluster), group in groups:
            X = group[features].values
            sev = group[severity_col].values
            safe_mask = sev < threshold
            unsafe_mask = sev >= threshold

            n_safe = int(safe_mask.sum())
            n_unsafe = int(unsafe_mask.sum())

            if n_safe < features.__len__() + 1 or n_unsafe == 0:
                logger.debug(
                    f"Skipping {fault}/cluster_{cluster}: "
                    f"safe={n_safe}, unsafe={n_unsafe} (insufficient)"
                )
                continue

            X_safe = X[safe_mask]
            X_unsafe = X[unsafe_mask]

            try:
                boundary = aia.compute(X_safe, X_unsafe, threshold=threshold, epsilon=epsilon)
                key = self._make_key(fault, cluster)
                self._boundaries[key] = boundary
                n_computed += 1
            except Exception as e:
                logger.warning(f"AIA failed for {fault}/cluster_{cluster}: {e}")

        logger.info(f"Computed {n_computed} boundaries from {len(groups)} groups")

    # ------------------------------------------------------------------
    # Query
    # ------------------------------------------------------------------

    def is_safe(self, x: np.ndarray, fault_name: str, cluster_id: int) -> bool:
        """Check if point *x* is safe for a specific scenario."""
        key = self._make_key(fault_name, cluster_id)
        bnd = self._boundaries.get(key)
        if bnd is None:
            return True  # no boundary → unconstrained (optimistic)
        return bool(bnd.contains(np.atleast_2d(x))[0])

    def is_safe_all(self, x: np.ndarray) -> bool:
        """Check if point *x* is safe across ALL scenarios."""
        x = np.atleast_2d(x)
        for bnd in self._boundaries.values():
            if not bnd.contains(x)[0]:
                return False
        return True

    def get_binding_scenario(self, x: np.ndarray) -> Optional[str]:
        """Return the key of the tightest (most binding) scenario."""
        x = np.atleast_2d(x)
        min_margin = float("inf")
        binding_key = None
        for key, bnd in self._boundaries.items():
            m = bnd.margin(x)[0]
            if m < min_margin:
                min_margin = m
                binding_key = key
        return binding_key

    # ------------------------------------------------------------------
    # Update
    # ------------------------------------------------------------------

    def add_critical_points(
        self,
        points: np.ndarray,
        severities: np.ndarray,
        fault_name: str,
        cluster_id: int,
        features: List[str],
        threshold: float = 0.6,
        epsilon: float = 0.01,
    ) -> None:
        """Re-compute a specific boundary including new critical points.

        Merges existing data (if we stored raw points) with new evaluations
        and rebuilds the AIA for that scenario.
        """
        key = self._make_key(fault_name, cluster_id)
        # For simplicity: just recompute if boundary exists, or compute fresh
        safe_mask = severities < threshold
        unsafe_mask = severities >= threshold
        if safe_mask.sum() < len(features) + 1 or unsafe_mask.sum() == 0:
            return

        aia = AffineInnerApproximation()
        boundary = aia.compute(
            points[safe_mask], points[unsafe_mask], threshold=threshold, epsilon=epsilon
        )
        self._boundaries[key] = boundary

    # ------------------------------------------------------------------
    # Summary
    # ------------------------------------------------------------------

    def summary(self) -> pd.DataFrame:
        """Return a summary DataFrame of all boundaries."""
        rows = []
        for key, bnd in self._boundaries.items():
            parts = key.split("__cluster_")
            fault = parts[0]
            cluster = int(parts[1]) if len(parts) > 1 else 0
            rows.append({
                "fault_name": fault,
                "cluster_id": cluster,
                "n_dims": bnd.n_dims,
                "n_facets": bnd.n_facets,
                "volume_estimate": bnd.volume_monte_carlo(n_samples=5000),
            })
        return pd.DataFrame(rows)

    # ------------------------------------------------------------------
    # Persistence
    # ------------------------------------------------------------------

    def save(self, path: str | Path) -> None:
        """Serialise all boundaries to JSON."""
        path = Path(path)
        data = {}
        for key, bnd in self._boundaries.items():
            data[key] = bnd.to_dict()
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(data, indent=2), encoding="utf-8")
        logger.info(f"Saved {len(self._boundaries)} boundaries to {path}")

    @classmethod
    def load(cls, path: str | Path) -> "BoundaryManager":
        """Load boundaries from JSON."""
        path = Path(path)
        data = json.loads(path.read_text(encoding="utf-8"))
        mgr = cls()
        for key, d in data.items():
            mgr._boundaries[key] = AIABoundary.from_dict(d)
        logger.info(f"Loaded {len(mgr._boundaries)} boundaries from {path}")
        return mgr

    @property
    def n_boundaries(self) -> int:
        return len(self._boundaries)

    @property
    def keys(self) -> List[str]:
        return list(self._boundaries.keys())
