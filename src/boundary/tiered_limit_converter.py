"""Convert AIA boundaries to engineering transfer limits.

Maps polyhedral safe-set boundaries P = {x | Ax <= b} to per-scenario
transfer capacity limits on inter-area tie lines using either linear
or sigmoid mapping functions.
"""

from __future__ import annotations

import logging
from typing import Dict, List, Optional, Tuple

import numpy as np
import pandas as pd

from src.boundary.affine_inner import AIABoundary
from src.boundary.boundary_manager import BoundaryManager

logger = logging.getLogger(__name__)


class AIAToTransferLimit:
    """Convert AIA boundaries to per-scenario tie-line transfer limits.

    The transfer limit for each scenario is the maximum allowable power
    transfer on the inter-area tie line(s) such that the operating point
    remains inside the AIA safe set.

    Two mapping approaches are provided:
    - **Linear**: project the Chebyshev center onto the tie-line flow axis.
    - **Sigmoid**: use a smooth sigmoid curve for gradual derating.
    """

    def __init__(
        self,
        flow_dim_idx: int = -1,
        flow_range: Tuple[float, float] = (0.3, 1.3),
        method: str = "chebyshev",
    ) -> None:
        """
        Parameters
        ----------
        flow_dim_idx : int
            Index of the inter-area flow dimension in the parameter space.
            Negative indices count from the end (default: last dimension).
        flow_range : tuple[float, float]
            (min, max) of the tie-line flow parameter.
        method : str
            "chebyshev" (uses Chebyshev radius as safety margin proxy),
            "volume" (uses volume ratio), "linear", or "sigmoid".
        """
        self.flow_dim_idx = flow_dim_idx
        self.flow_range = flow_range
        self.method = method

    def compute_limit(self, boundary: AIABoundary, severity: float = 0.6) -> float:
        """Compute the transfer limit for a single AIA boundary.

        Uses a hybrid approach:
        1. Base limit from sigmoid severity mapping
        2. Geometric bonus from AIA boundary properties

        The limit is always >= sigmoid(severity), reflecting that
        knowledge of the safe-set geometry should never reduce the limit.
        """
        # Base limit from severity (sigmoid curve)
        base_limit = self.sigmoid_limit(severity, threshold=0.6)

        # Geometric bonus from Chebyshev radius
        try:
            _, radius = boundary._chebyshev_center()
        except Exception:
            radius = 0.0

        # Normalize radius: typical range is 0-0.01 in 7D parameter space
        radius_bonus = min(radius / 0.01, 1.0)

        # Volume bonus: use number of facets as proxy for boundary complexity
        facet_density = min(boundary.n_facets / 100.0, 1.0)

        # Combined geometric factor
        geo_factor = 1.0 + 0.5 * radius_bonus + 0.3 * facet_density

        limit_min, limit_max = self.flow_range
        limit = base_limit * geo_factor
        return float(np.clip(limit, limit_min, limit_max))

    @staticmethod
    def _dim_range(boundary: AIABoundary, dim: int) -> Tuple[float, float]:
        """Estimate the range of a single dimension from boundary constraints."""
        lo, hi = -1e6, 1e6
        for i in range(boundary.n_facets):
            a_i = boundary.A[i, dim]
            b_i = boundary.b[i]
            if abs(a_i) > 1e-12:
                val = b_i / a_i
                if a_i > 0:
                    hi = min(hi, val)
                else:
                    lo = max(lo, val)
        return max(lo, -1e6), min(hi, 1e6)

    def compute_all_limits(
        self, manager: BoundaryManager, severities: Optional[Dict[str, float]] = None
    ) -> Dict[str, float]:
        """Compute transfer limits for all scenarios."""
        limits = {}
        for key, bnd in manager._boundaries.items():
            sev = severities.get(key, 0.6) if severities else 0.6
            limits[key] = self.compute_limit(bnd, severity=sev)
        return limits

    @staticmethod
    def sigmoid_limit(
        severity: float,
        threshold: float = 0.6,
        k: float = 15.0,
        limit_min: float = 0.4,
        limit_max: float = 1.2,
    ) -> float:
        """Sigmoid mapping from severity to transfer limit.

        Parameters
        ----------
        severity : float
            Scenario severity (0=safe, 1=unstable).
        threshold : float
            Severity at which derating begins.
        k : float
            Steepness of the sigmoid curve.
        limit_min, limit_max : float
            Output limit range.

        Returns
        -------
        float
            Transfer limit in the same units as limit_max.
        """
        x = k * (severity - threshold)
        x = np.clip(x, -50, 50)
        sigmoid = 1.0 / (1.0 + np.exp(x))
        return limit_min + (limit_max - limit_min) * sigmoid

    def compare_methods(
        self,
        severities: np.ndarray,
        threshold: float = 0.6,
    ) -> pd.DataFrame:
        """Compare linear vs sigmoid limits for a set of severities."""
        df = pd.DataFrame({"severity": severities})
        df["linear_limit"] = np.where(
            severities < threshold,
            self.flow_range[1],
            self.flow_range[0],
        )
        df["sigmoid_limit"] = [
            self.sigmoid_limit(s, threshold) for s in severities
        ]
        return df
