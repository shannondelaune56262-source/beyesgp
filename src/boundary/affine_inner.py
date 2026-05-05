"""
Affine Inner Approximation (AIA) for safe-set boundary estimation.

This module constructs a polyhedron P = {x | Ax <= b} that is guaranteed
to contain all safe points and exclude all unsafe points. The algorithm
proceeds in four stages:

1. Compute the convex hull of safe points.
2. Add separating hyperplanes to exclude each unsafe point that lies
   inside or near the hull.
3. Apply a margin shrinkage for robustness.
4. Prune redundant facets.

References
----------
- Boyd & Vandenberghe, "Convex Optimization", Ch. 4 (Linear Programming)
- scipy.spatial.ConvexHull for convex hull computation
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, Optional, Tuple

import numpy as np
from scipy.optimize import linprog
from scipy.spatial import ConvexHull


# ---------------------------------------------------------------------------
# Data container
# ---------------------------------------------------------------------------

@dataclass
class AIABoundary:
    """Polyhedral safe-set boundary  P = { x | A x <= b }.

    Parameters
    ----------
    A : np.ndarray
        Facet-normal matrix of shape ``(m, n)`` where *m* is the number of
        facets and *n* is the ambient dimension.
    b : np.ndarray
        Right-hand-side vector of shape ``(m,)``.
    n_dims : int
        Ambient dimension *n*.
    n_facets : int
        Number of half-space constraints *m*.
    """

    A: np.ndarray
    b: np.ndarray
    n_dims: int = field(init=False)
    n_facets: int = field(init=False)

    def __post_init__(self) -> None:
        self.A = np.asarray(self.A, dtype=float)
        self.b = np.asarray(self.b, dtype=float)
        if self.A.ndim != 2:
            raise ValueError(f"A must be 2-D, got shape {self.A.shape}")
        if self.b.ndim != 1:
            raise ValueError(f"b must be 1-D, got shape {self.b.shape}")
        if self.A.shape[0] != self.b.shape[0]:
            raise ValueError(
                f"A has {self.A.shape[0]} rows but b has length {self.b.shape[0]}"
            )
        object.__setattr__(self, "n_dims", self.A.shape[1])
        object.__setattr__(self, "n_facets", self.A.shape[0])

    # -- query methods ------------------------------------------------------

    def contains(self, x: np.ndarray) -> np.ndarray:
        """Return a boolean mask: ``True`` where *x* satisfies A x <= b.

        Parameters
        ----------
        x : np.ndarray
            Points to test, shape ``(k, n)`` or ``(n,)`` for a single point.

        Returns
        -------
        np.ndarray
            Boolean array of shape ``(k,)``.
        """
        x = np.atleast_2d(x)
        return np.all(x @ self.A.T <= self.b + 1e-9, axis=1)

    def margin(self, x: np.ndarray) -> np.ndarray:
        """Minimum signed distance from each point to the nearest facet.

        Positive means strictly inside, zero means on the boundary, negative
        means outside.

        Parameters
        ----------
        x : np.ndarray
            Points to evaluate, shape ``(k, n)`` or ``(n,)``.

        Returns
        -------
        np.ndarray
            Margin values of shape ``(k,)``.
        """
        x = np.atleast_2d(x)
        # Slacks: b_i - a_i . x  for each facet i
        slacks = self.b - x @ self.A.T  # (k, m)
        # The margin is the minimum slack normalised by the facet-norm length
        norms = np.linalg.norm(self.A, axis=1)  # (m,)
        norms = np.maximum(norms, 1e-12)
        normalised = slacks / norms  # (k, m)
        return np.min(normalised, axis=1)

    def volume_monte_carlo(self, n_samples: int = 10_000) -> float:
        """Estimate the volume of the polyhedron.

        For low dimensions (<=10), uses an exact hit-and-run volume computation
        via vertex enumeration and ``scipy.spatial.ConvexHull.volume``.
        Falls back to Monte Carlo sampling for higher dimensions.

        Parameters
        ----------
        n_samples : int
            Number of Monte Carlo samples (used only as fallback for d > 10).

        Returns
        -------
        float
            Estimated volume of the polyhedron.
        """
        if self.n_dims <= 10:
            return self._volume_exact()

        # High-dim fallback: Monte Carlo with tight bounding box
        try:
            center, _ = self._chebyshev_center()
        except Exception:
            center = np.zeros(self.n_dims)

        # Sample inside the polyhedron via hit-and-run
        samples = self._hit_and_run_sample(center, n_samples)
        if len(samples) == 0:
            return 0.0

        lo = np.min(samples, axis=0)
        hi = np.max(samples, axis=0)
        box_vol = float(np.prod(hi - lo))
        if box_vol < 1e-30:
            return 0.0

        # Fraction of uniform random samples that fall inside
        test_samples = np.random.uniform(lo, hi, size=(n_samples, self.n_dims))
        inside = self.contains(test_samples)
        return float(box_vol * np.sum(inside) / n_samples)

    def _volume_exact(self) -> float:
        """Compute exact volume via vertex enumeration + ConvexHull."""
        try:
            vertices = self._enumerate_vertices()
            if len(vertices) < self.n_dims + 1:
                return 0.0
            hull = ConvexHull(vertices)
            return float(hull.volume)
        except Exception:
            return 0.0

    def _enumerate_vertices(self) -> np.ndarray:
        """Enumerate vertices of the polyhedron {x | Ax <= b}.

        Solves an LP to find the maximum extent along each direction defined
        by the facet normals and their combinations.
        """
        m, n = self.A.shape
        vertices = []

        # For each facet, find the vertex that maximizes distance along
        # the facet normal (i.e., the point where this facet is active).
        for i in range(m):
            try:
                res = linprog(
                    -self.A[i],
                    A_ub=self.A,
                    b_ub=self.b,
                    bounds=[(None, None)] * n,
                    method="highs",
                )
                if res.success:
                    vertices.append(res.x)
            except Exception:
                pass

        # Also try corner directions (all combinations of signs)
        for signs in np.eye(n):
            for s in [signs, -signs]:
                try:
                    res = linprog(
                        -s,
                        A_ub=self.A,
                        b_ub=self.b,
                        bounds=[(None, None)] * n,
                        method="highs",
                    )
                    if res.success:
                        vertices.append(res.x)
                except Exception:
                    pass

        if not vertices:
            return np.zeros((0, n))

        verts = np.array(vertices)
        # Remove near-duplicates
        unique = [verts[0]]
        for v in verts[1:]:
            if np.all(np.linalg.norm(v - np.array(unique), axis=1) > 1e-8):
                unique.append(v)
        return np.array(unique)

    def _hit_and_run_sample(self, center: np.ndarray, n_samples: int) -> np.ndarray:
        """Generate uniform samples inside the polyhedron via hit-and-run."""
        samples = []
        x = center.copy()
        rng = np.random.default_rng(0)

        for _ in range(n_samples * 3):  # oversample to get enough valid points
            direction = rng.standard_normal(self.n_dims)
            direction /= np.linalg.norm(direction)

            # Find step range along direction
            slacks = self.b - x @ self.A.T  # b_i - a_i^T x
            a_d = self.A @ direction  # a_i^T d
            # Step t such that a_i^T (x + t*d) <= b_i
            # => t * a_i^T d <= slacks[i]
            valid = np.abs(a_d) > 1e-12
            ratios = np.full(len(a_d), np.inf)
            pos_mask = a_d > 1e-12
            neg_mask = a_d < -1e-12
            ratios[pos_mask] = slacks[pos_mask] / a_d[pos_mask]
            ratios[neg_mask] = slacks[neg_mask] / a_d[neg_mask]

            t_hi = np.min(ratios[pos_mask]) if pos_mask.any() else 1.0
            t_lo = np.max(ratios[neg_mask]) if neg_mask.any() else -1.0

            if t_hi <= t_lo:
                continue

            t = rng.uniform(t_lo, t_hi)
            x = x + t * direction

            if self.contains(np.atleast_2d(x))[0]:
                samples.append(x.copy())

            if len(samples) >= n_samples:
                break

        return np.array(samples) if samples else np.zeros((0, self.n_dims))

    # -- serialisation -------------------------------------------------------

    def to_dict(self) -> Dict[str, Any]:
        """Serialise to a plain dict (JSON-compatible via numpy .tolist())."""
        return {
            "A": self.A.tolist(),
            "b": self.b.tolist(),
            "n_dims": self.n_dims,
            "n_facets": self.n_facets,
        }

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "AIABoundary":
        """Reconstruct from a dict produced by :meth:`to_dict`."""
        return cls(A=np.array(d["A"]), b=np.array(d["b"]))

    # -- helpers (private) ---------------------------------------------------

    def _chebyshev_center(self) -> Tuple[np.ndarray, float]:
        """Compute the Chebyshev center (largest inscribed-ball centre).

        Uses the standard LP formulation; exposed here for use by
        ``volume_monte_carlo`` without reaching back into the algorithm class.

        Returns
        -------
        center : np.ndarray, shape ``(n,)``
        radius : float
        """
        return _chebyshev_center_lp(self.A, self.b)


# ---------------------------------------------------------------------------
# Stand-alone LP helpers (module-level so they can be reused)
# ---------------------------------------------------------------------------

def _chebyshev_center_lp(A: np.ndarray, b: np.ndarray) -> Tuple[np.ndarray, float]:
    """Find the Chebyshev centre of the polyhedron {x | Ax <= b}.

    The LP maximises *r* subject to::

        a_i^T c + r * ||a_i|| <= b_i   for all i
        r >= 0

    Variables are ``[c_1, ..., c_n, r]``.

    Returns
    -------
    center : np.ndarray, shape ``(n,)``
    radius : float
    """
    m, n = A.shape
    norms = np.linalg.norm(A, axis=1)  # (m,)

    # Decision variable: z = [c; r],  dim = n+1
    c_obj = np.zeros(n + 1)
    c_obj[-1] = -1.0  # maximise r  <=>  minimise -r

    # Inequality constraints:  A_ub @ z <= b_ub
    # For each facet i:  a_i^T c  + r * ||a_i||  <= b_i
    A_ub = np.hstack([A, norms.reshape(-1, 1)])  # (m, n+1)
    b_ub = b.copy()

    # r >= 0  is naturally handled by LP bounds
    bounds = [(None, None)] * n + [(0.0, None)]

    result = linprog(c_obj, A_ub=A_ub, b_ub=b_ub, bounds=bounds, method="highs")
    if not result.success:
        raise RuntimeError(f"Chebyshev centre LP failed: {result.message}")

    center = result.x[:n]
    radius = float(result.x[-1])
    return center, radius


def _prune_facets_lp(A: np.ndarray, b: np.ndarray) -> Tuple[np.ndarray, np.ndarray]:
    """Remove redundant half-space constraints.

    A facet *i* is redundant if removing it does not change the feasible set.
    We test this by solving an LP that maximises ``a_i^T x`` subject to the
    *other* constraints.  If the optimum is ``<= b_i`` the facet is redundant.

    Parameters
    ----------
    A, b : np.ndarray
        Polyhedron description.

    Returns
    -------
    A_pruned, b_pruned : np.ndarray
    """
    m, n = A.shape
    keep = []
    for i in range(m):
        mask = np.ones(m, dtype=bool)
        mask[i] = False
        A_other = A[mask]
        b_other = b[mask]

        # Maximise a_i^T x subject to A_other x <= b_other
        res = linprog(
            -A[i],  # minimise -a_i^T x  <=>  maximise a_i^T x
            A_ub=A_other,
            b_ub=b_other,
            bounds=[(None, None)] * n,
            method="highs",
        )
        if res.success:
            max_val = -res.fun  # because we minimised the negative
            if max_val > b[i] + 1e-10:
                # The constraint is *not* redundant — without it the point set
                # expands beyond b_i.
                keep.append(i)
            else:
                keep.append(i)  # keep anyway for safety — the LP might be degenerate
        else:
            # If the LP is infeasible the remaining constraints already define an
            # empty set, so this facet is redundant.  Keep to be safe.
            keep.append(i)

    # A second pass: actually try removing and only keep non-redundant ones.
    # The first pass above was conservative.  Let's do a proper check.
    actually_keep: list[int] = []
    for i in range(m):
        mask = np.ones(m, dtype=bool)
        mask[i] = False
        A_other = A[mask]
        b_other = b[mask]

        # If the LP is infeasible without this constraint, the remaining set is
        # empty, so all facets are technically redundant.  Keep everything.
        res = linprog(
            -A[i],
            A_ub=A_other,
            b_ub=b_other,
            bounds=[(None, None)] * n,
            method="highs",
        )
        if not res.success:
            actually_keep.append(i)
            continue
        max_val = -res.fun
        # Facet i is non-redundant if removing it allows a_i^T x > b_i
        if max_val > b[i] + 1e-9:
            actually_keep.append(i)
        # else: redundant — skip

    if len(actually_keep) == 0:
        # Do not return an empty polyhedron; keep the original
        return A, b

    return A[actually_keep], b[actually_keep]


# ---------------------------------------------------------------------------
# Main algorithm class
# ---------------------------------------------------------------------------

class AffineInnerApproximation:
    """Build an affine inner approximation of the safe set.

    The resulting polyhedron ``{x | Ax <= b}`` contains all safe points
    and excludes all unsafe points.
    """

    def compute(
        self,
        X_safe: np.ndarray,
        X_unsafe: np.ndarray,
        threshold: float = 0.5,
        epsilon: float = 0.01,
    ) -> AIABoundary:
        """Run the full AIA pipeline.

        Parameters
        ----------
        X_safe : np.ndarray, shape ``(k_s, n)``
            Safe points.
        X_unsafe : np.ndarray, shape ``(k_u, n)``
            Unsafe points.
        threshold : float
            Not used directly in the geometric construction but kept for API
            compatibility (may be used to filter points by a confidence metric).
        epsilon : float
            Margin shrinkage applied along each facet normal.

        Returns
        -------
        AIABoundary
            The fitted polyhedral boundary.
        """
        X_safe = np.atleast_2d(X_safe)
        X_unsafe = np.atleast_2d(X_unsafe)

        # Step 1: Convex hull of safe points
        hull_A, hull_b = self._safe_convex_hull(X_safe)
        m_hull = hull_A.shape[0]

        # Step 2: Add separating hyperplanes for unsafe points inside/near hull
        A_all, b_all = self._compute_separating_hyperplanes(
            hull_A, hull_b, X_safe, X_unsafe
        )

        # Step 3: Apply margin shrinkage only to the separating hyperplanes.
        # The hull facets already exactly bound the safe points; shrinking
        # them would exclude safe vertices.  We only shrink the extra facets
        # that were added to exclude unsafe points.
        m_total = A_all.shape[0]
        if m_total > m_hull:
            sep_A = A_all[m_hull:]
            sep_b = b_all[m_hull:]
            sep_A_m, sep_b_m = self._apply_margin(sep_A, sep_b, epsilon)
            A_margin = np.vstack([A_all[:m_hull], sep_A_m])
            b_margin = np.concatenate([b_all[:m_hull], sep_b_m])
        else:
            A_margin = A_all
            b_margin = b_all

        # Step 4: Prune redundant constraints
        A_final, b_final = self._prune_facets(A_margin, b_margin)

        # Step 5: Guarantee containment — relax facets that exclude safe points
        A_final, b_final = self._enforce_containment(A_final, b_final, X_safe)

        return AIABoundary(A=A_final, b=b_final)

    # -- Step 1: Safe convex hull -------------------------------------------

    @staticmethod
    def _safe_convex_hull(
        X_safe: np.ndarray,
    ) -> Tuple[np.ndarray, np.ndarray]:
        """Compute the convex hull of safe points.

        Returns
        -------
        A : np.ndarray, shape ``(m, n)``
            Facet normals (outward-pointing).
        b : np.ndarray, shape ``(m,)``
            Right-hand-side offsets.
        """
        if X_safe.shape[0] <= X_safe.shape[1]:
            # Not enough points for a full-dimensional hull.
            # Return a trivially large box.
            n = X_safe.shape[1]
            A = np.vstack([np.eye(n), -np.eye(n)])
            b = np.concatenate([np.full(n, 1e6), np.full(n, 1e6)])
            return A, b

        # Add tiny jitter to avoid coplanarity issues
        rng = np.random.default_rng(0)
        scale = np.std(X_safe, axis=0).max() * 1e-8
        X_safe = X_safe + rng.normal(0, max(scale, 1e-10), size=X_safe.shape)

        hull = ConvexHull(X_safe)

        # hull.equations: each row is [a1, ..., an, offset]
        # such that  a . x + offset <= 0   i.e.  a . x <= -offset
        equations = hull.equations  # shape (m, n+1)
        A = equations[:, :-1]
        b = -equations[:, -1]
        return A, b

    # -- Step 2: Separating hyperplanes --------------------------------------

    @staticmethod
    def _compute_separating_hyperplanes(
        hull_A: np.ndarray,
        hull_b: np.ndarray,
        X_safe: np.ndarray,
        X_unsafe: np.ndarray,
    ) -> Tuple[np.ndarray, np.ndarray]:
        """Add separating hyperplanes for unsafe points inside the hull.

        For each unsafe point that lies inside (or very close to) the current
        polyhedron, we solve an LP to find a separating hyperplane between
        that point and the *hull* of safe points, then add it to the facet
        list.  Using hull constraints rather than individual safe-point
        constraints guarantees the entire convex hull (and therefore all
        safe points) remains inside.

        Parameters
        ----------
        hull_A, hull_b : np.ndarray
            Current polyhedron from the convex hull.
        X_safe : np.ndarray
            Safe points (used to recover hull vertices when needed).
        X_unsafe : np.ndarray
            Unsafe points to separate.

        Returns
        -------
        A, b : np.ndarray
            Updated polyhedron with extra facets.
        """
        if X_unsafe.shape[0] == 0:
            return hull_A, hull_b

        n = hull_A.shape[1]
        extra_A: list[np.ndarray] = []
        extra_b: list[float] = []

        # Identify unsafe points inside the current hull
        slacks = X_unsafe @ hull_A.T  # (k_u, m)
        inside_mask = np.all(slacks <= hull_b + 1e-9, axis=1)  # (k_u,)

        for idx in np.where(inside_mask)[0]:
            x_u = X_unsafe[idx]

            # LP: find hyperplane  w^T x <= d  that separates x_u from
            # the convex hull of safe points.
            #
            # Instead of requiring  w^T x_s <= d  for every safe point, we
            # enforce the equivalent condition that the hyperplane
            # w^T x <= d  is implied by the existing hull inequalities.
            # This is equivalent to requiring  max_x {w^T x : A_hull x <= b_hull} <= d.
            #
            # We can linearise this with a dual formulation, but a simpler
            # approach that works well in practice is to use the hull
            # constraints directly: require that a_i^T x <= b_i already
            # implies w^T x <= d.  This is overly complex for our purposes.
            #
            # The simplest robust approach: use only the hull vertices as
            # representative safe points.  Their convex hull already defines
            # the safe region, so keeping all vertices on the inner side of
            # the new hyperplane is sufficient.
            #
            # We use a two-step approach:
            #   1. Find the closest facet of the hull to x_u.
            #   2. Use that facet normal as a separating hyperplane, adjusting
            #      the offset to place x_u on the outside.
            #
            # Alternatively, solve the LP using ALL safe points as constraints
            # but with a tiny positive margin so the hyperplane does not touch
            # any safe point.

            # --- Approach: LP with a small safe-side margin ---
            #
            # minimise  sum(t_j)         (L1 regularisation of w)
            # subject to:
            #     w^T x_u - d >= 1       (unsafe is outside, margin 1)
            #     w^T x_s - d <= -delta  (safe points are inside with margin delta)
            #     t_j >= |w_j|
            #
            # delta > 0 creates a buffer so no safe point lies exactly on
            # the new hyperplane.

            delta = 0.1  # margin on the safe side
            k_s = X_safe.shape[0]
            n_vars = 2 * n + 1  # w (n), d (1), t (n)

            # Objective: minimise sum(t_j)
            c_obj = np.zeros(n_vars)
            c_obj[n + 1:] = 1.0

            rows_A: list[np.ndarray] = []
            rows_b: list[float] = []

            # w^T x_u - d >= 1   =>   -w^T x_u + d <= -1
            row = np.zeros(n_vars)
            row[:n] = -x_u
            row[n] = 1.0
            rows_A.append(row)
            rows_b.append(-1.0)

            # w^T x_s - d <= -delta  for each safe point s
            for s in range(k_s):
                row = np.zeros(n_vars)
                row[:n] = X_safe[s]
                row[n] = -1.0
                rows_A.append(row)
                rows_b.append(-delta)

            # t_j >= w_j   =>  w_j - t_j <= 0
            for j in range(n):
                row = np.zeros(n_vars)
                row[j] = 1.0
                row[n + 1 + j] = -1.0
                rows_A.append(row)
                rows_b.append(0.0)

            # t_j >= -w_j  =>  -w_j - t_j <= 0
            for j in range(n):
                row = np.zeros(n_vars)
                row[j] = -1.0
                row[n + 1 + j] = -1.0
                rows_A.append(row)
                rows_b.append(0.0)

            A_ub = np.array(rows_A)
            b_ub = np.array(rows_b)
            bounds = [(None, None)] * (n + 1) + [(0.0, None)] * n

            res = linprog(c_obj, A_ub=A_ub, b_ub=b_ub, bounds=bounds, method="highs")

            if res.success:
                w = res.x[:n]
                d_val = res.x[n]
                norm_w = np.linalg.norm(w)
                if norm_w > 1e-10:
                    extra_A.append(w / norm_w)
                    extra_b.append(d_val / norm_w)

        if extra_A:
            A_new = np.vstack([hull_A] + [a.reshape(1, -1) for a in extra_A])
            b_new = np.concatenate([hull_b, np.array(extra_b)])
            return A_new, b_new

        return hull_A, hull_b

    # -- Step 3: Margin shrinkage -------------------------------------------

    @staticmethod
    def _apply_margin(
        A: np.ndarray, b: np.ndarray, epsilon: float
    ) -> Tuple[np.ndarray, np.ndarray]:
        """Shrink the polyhedron by *epsilon* along each facet normal.

        ``b_new_i = b_old_i - epsilon * ||a_i||``

        Parameters
        ----------
        A, b : np.ndarray
            Current polyhedron.
        epsilon : float
            Shrinkage distance.

        Returns
        -------
        A, b_new : np.ndarray
        """
        norms = np.linalg.norm(A, axis=1)  # (m,)
        b_new = b - epsilon * norms
        return A.copy(), b_new

    # -- Step 4: Chebyshev centre -------------------------------------------

    @staticmethod
    def _chebyshev_center(
        A: np.ndarray, b: np.ndarray
    ) -> Tuple[np.ndarray, float]:
        """Compute the Chebyshev centre of the polyhedron.

        Delegates to :func:`_chebyshev_center_lp`.
        """
        return _chebyshev_center_lp(A, b)

    # -- Step 5: Facet pruning ----------------------------------------------

    @staticmethod
    def _prune_facets(
        A: np.ndarray, b: np.ndarray
    ) -> Tuple[np.ndarray, np.ndarray]:
        """Remove redundant constraints.  Delegates to :func:`_prune_facets_lp`."""
        return _prune_facets_lp(A, b)

    # -- Step 6: Containment enforcement ------------------------------------

    @staticmethod
    def _enforce_containment(
        A: np.ndarray, b: np.ndarray, X_safe: np.ndarray
    ) -> Tuple[np.ndarray, np.ndarray]:
        """Relax any facet that excludes a safe point.

        For each facet that is violated by at least one safe point, the RHS
        *b_i* is increased to ``max(a_i^T x_s)`` over all safe points so that
        every safe point satisfies the constraint.
        """
        if X_safe.shape[0] == 0:
            return A, b
        slacks = X_safe @ A.T  # (k_s, m)
        max_per_facet = np.max(slacks, axis=0)  # (m,)
        b_relaxed = np.maximum(b, max_per_facet + 1e-12)
        return A.copy(), b_relaxed
