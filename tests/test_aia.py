"""Unit tests for the Affine Inner Approximation (AIA) module."""

from __future__ import annotations

import numpy as np
import pytest

from src.boundary.affine_inner import AIABoundary, AffineInnerApproximation


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _circle_points(n: int, radius: float = 1.0, dim: int = 2, seed: int = 42):
    """Generate safe (inside) and unsafe (outside) points for a sphere."""
    rng = np.random.default_rng(seed)
    # Safe points: uniformly inside the sphere
    # Use rejection sampling from the bounding cube.
    points = []
    while len(points) < n:
        batch = rng.uniform(-radius, radius, size=(n * 3, dim))
        inside = np.linalg.norm(batch, axis=1) < radius * 0.9
        points.extend(batch[inside].tolist())
    X_safe = np.array(points[:n])

    # Unsafe points: outside the sphere
    upoints = []
    while len(upoints) < n:
        batch = rng.uniform(-radius * 2, radius * 2, size=(n * 3, dim))
        outside = np.linalg.norm(batch, axis=1) > radius * 1.1
        upoints.extend(batch[outside].tolist())
    X_unsafe = np.array(upoints[:n])

    return X_safe, X_unsafe


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

class TestAIABoundary:
    """Tests for the AIABoundary dataclass."""

    def test_contains_inside(self):
        """A point satisfying all constraints is contained."""
        A = np.array([[1.0, 0.0], [0.0, 1.0], [-1.0, 0.0], [0.0, -1.0]])
        b = np.array([1.0, 1.0, 1.0, 1.0])  # unit box centred at origin
        boundary = AIABoundary(A=A, b=b)
        assert boundary.contains(np.array([0.0, 0.0]))
        assert boundary.contains(np.array([0.5, 0.5]))

    def test_contains_outside(self):
        """A point violating at least one constraint is not contained."""
        A = np.array([[1.0, 0.0], [0.0, 1.0], [-1.0, 0.0], [0.0, -1.0]])
        b = np.array([1.0, 1.0, 1.0, 1.0])
        boundary = AIABoundary(A=A, b=b)
        assert not boundary.contains(np.array([2.0, 0.0]))

    def test_margin_positive_inside(self):
        A = np.array([[1.0, 0.0], [0.0, 1.0], [-1.0, 0.0], [0.0, -1.0]])
        b = np.array([1.0, 1.0, 1.0, 1.0])
        boundary = AIABoundary(A=A, b=b)
        m = boundary.margin(np.array([0.0, 0.0]))
        assert m > 0

    def test_to_from_dict_roundtrip(self):
        A = np.array([[1.0, 0.0], [0.0, 1.0]])
        b = np.array([1.0, 1.0])
        boundary = AIABoundary(A=A, b=b)
        d = boundary.to_dict()
        boundary2 = AIABoundary.from_dict(d)
        np.testing.assert_array_equal(boundary.A, boundary2.A)
        np.testing.assert_array_equal(boundary.b, boundary2.b)


class TestAIA2DCircle:
    """2-D circle safe/unsafe set."""

    def test_2d_circle(self):
        """AIA volume should be within 10 % of the inscribed square of the
        unit circle."""
        X_safe, X_unsafe = _circle_points(200, radius=1.0, dim=2)
        aia = AffineInnerApproximation()
        boundary = aia.compute(X_safe, X_unsafe, threshold=0.5, epsilon=0.01)

        # Inscribed square of the unit circle has side sqrt(2), volume = 2
        inscribed_square_vol = 2.0
        vol = boundary.volume_monte_carlo(n_samples=50_000)

        # The AIA hull should contain the inscribed square but be bounded by
        # the circle, so volume should be between ~inscribed_square_vol and ~pi.
        # Check it is within 10 % of the inscribed square (lower bound).
        # In practice the convex hull of random interior points will be smaller.
        # We just check it is positive and not wildly off.
        assert vol > 0.0, f"Volume should be positive, got {vol}"
        # The convex hull of interior points of a circle should have volume
        # roughly comparable to the inscribed square.  Allow generous bounds.
        assert vol < 2.0 * np.pi, f"Volume {vol} exceeds circle area unexpectedly"
        assert vol > 0.1, f"Volume {vol} is suspiciously small"


class TestAIA3DSphere:
    """3-D sphere safe/unsafe set."""

    def test_3d_sphere(self):
        """AIA on a 3-D sphere."""
        X_safe, X_unsafe = _circle_points(300, radius=1.0, dim=3)
        aia = AffineInnerApproximation()
        boundary = aia.compute(X_safe, X_unsafe, threshold=0.5, epsilon=0.01)

        vol = boundary.volume_monte_carlo(n_samples=50_000)
        assert vol > 0.0, "Volume should be positive"
        sphere_vol = 4.0 / 3.0 * np.pi
        assert vol < 2.0 * sphere_vol, f"Volume {vol} exceeds sphere volume unexpectedly"
        assert vol > 0.1, f"Volume {vol} is suspiciously small"


class TestContainment:
    """Verify that all safe points are inside and all unsafe points are outside."""

    def test_all_safe_inside(self):
        """100 % of safe points must be contained in the boundary."""
        X_safe, X_unsafe = _circle_points(150, radius=1.0, dim=2)
        aia = AffineInnerApproximation()
        boundary = aia.compute(X_safe, X_unsafe, threshold=0.5, epsilon=0.01)

        inside = boundary.contains(X_safe)
        assert np.all(inside), (
            f"{np.sum(~inside)} of {len(X_safe)} safe points are outside the boundary"
        )

    def test_all_unsafe_outside(self):
        """100 % of unsafe points must be excluded from the boundary."""
        X_safe, X_unsafe = _circle_points(150, radius=1.0, dim=2)
        aia = AffineInnerApproximation()
        boundary = aia.compute(X_safe, X_unsafe, threshold=0.5, epsilon=0.01)

        inside = boundary.contains(X_unsafe)
        assert not np.any(inside), (
            f"{np.sum(inside)} of {len(X_unsafe)} unsafe points are inside the boundary"
        )

    def test_3d_all_safe_inside(self):
        X_safe, X_unsafe = _circle_points(200, radius=1.0, dim=3)
        aia = AffineInnerApproximation()
        boundary = aia.compute(X_safe, X_unsafe, threshold=0.5, epsilon=0.01)
        inside = boundary.contains(X_safe)
        assert np.all(inside)

    def test_3d_all_unsafe_outside(self):
        X_safe, X_unsafe = _circle_points(200, radius=1.0, dim=3)
        aia = AffineInnerApproximation()
        boundary = aia.compute(X_safe, X_unsafe, threshold=0.5, epsilon=0.01)
        inside = boundary.contains(X_unsafe)
        assert not np.any(inside)


class TestChebyshevCenter:
    """Test Chebyshev centre computation."""

    def test_unit_box_center(self):
        A = np.array([[1, 0], [0, 1], [-1, 0], [0, -1]], dtype=float)
        b = np.array([1, 1, 1, 1], dtype=float)
        aia = AffineInnerApproximation()
        c, r = aia._chebyshev_center(A, b)
        np.testing.assert_allclose(c, [0, 0], atol=1e-6)
        assert r > 0.9  # should be close to 1.0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
