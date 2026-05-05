"""Tests for MultiOutputGP surrogate model."""

import numpy as np
import pytest

from src.optimizer.multi_output_gp import MultiOutputGP


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def rng():
    """Deterministic random number generator for reproducible tests."""
    return np.random.default_rng(42)


@pytest.fixture
def clean_synthetic_data(rng):
    """Synthetic data with a clear functional relationship and low noise.

    Each output is a different sinusoidal function of the single input.
    """
    n_train, n_test = 80, 40
    X_train = rng.uniform(0, 2 * np.pi, size=(n_train, 1))
    X_test = rng.uniform(0, 2 * np.pi, size=(n_test, 1))

    noise_scale = 0.02
    y_train = {
        "f_angle":   np.sin(X_train[:, 0]) + rng.normal(0, noise_scale, n_train),
        "f_freq":    np.cos(X_train[:, 0]) + rng.normal(0, noise_scale, n_train),
        "f_voltage": np.sin(2 * X_train[:, 0]) + rng.normal(0, noise_scale, n_train),
    }
    y_train["severity"] = (
        0.5 * y_train["f_angle"]
        + 0.25 * y_train["f_freq"]
        + 0.25 * y_train["f_voltage"]
    )

    y_test = {
        "f_angle":   np.sin(X_test[:, 0]),
        "f_freq":    np.cos(X_test[:, 0]),
        "f_voltage": np.sin(2 * X_test[:, 0]),
    }
    y_test["severity"] = (
        0.5 * y_test["f_angle"]
        + 0.25 * y_test["f_freq"]
        + 0.25 * y_test["f_voltage"]
    )

    return X_train, X_test, y_train, y_test


@pytest.fixture
def noisy_synthetic_data(rng):
    """Noisy synthetic data for basic fit/predict verification."""
    n_train, n_test = 60, 30
    X_train = rng.uniform(0, 2 * np.pi, size=(n_train, 1))
    X_test = rng.uniform(0, 2 * np.pi, size=(n_test, 1))

    noise_scale = 0.1
    y_train = {
        "f_angle":   np.sin(X_train[:, 0]) + rng.normal(0, noise_scale, n_train),
        "f_freq":    np.cos(X_train[:, 0]) + rng.normal(0, noise_scale, n_train),
        "f_voltage": np.sin(X_train[:, 0] * 0.5) + rng.normal(0, noise_scale, n_train),
    }
    y_train["severity"] = (
        0.5 * y_train["f_angle"]
        + 0.25 * y_train["f_freq"]
        + 0.25 * y_train["f_voltage"]
    )

    y_test = {
        "f_angle":   np.sin(X_test[:, 0]),
        "f_freq":    np.cos(X_test[:, 0]),
        "f_voltage": np.sin(X_test[:, 0] * 0.5),
    }
    y_test["severity"] = (
        0.5 * y_test["f_angle"]
        + 0.25 * y_test["f_freq"]
        + 0.25 * y_test["f_voltage"]
    )

    return X_train, X_test, y_train, y_test


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

class TestFitPredict:
    """Basic fit and predict smoke tests."""

    def test_predict_returns_correct_keys(self, noisy_synthetic_data):
        X_train, X_test, y_train, _ = noisy_synthetic_data
        mogp = MultiOutputGP(n_restarts=2, seed=0)
        mogp.fit(X_train, y_train)
        preds = mogp.predict(X_test)

        for key in ("f_angle", "f_freq", "f_voltage", "severity"):
            assert key in preds, f"Missing key '{key}' in predictions"
            assert "mean" in preds[key]
            assert "std" in preds[key]
            assert preds[key]["mean"].shape == (X_test.shape[0],)
            assert preds[key]["std"].shape == (X_test.shape[0],)

    def test_predict_before_fit_raises(self):
        mogp = MultiOutputGP()
        with pytest.raises(RuntimeError, match="fitted"):
            mogp.predict(np.array([[0.0]]))

    def test_predict_composite_before_fit_raises(self):
        mogp = MultiOutputGP()
        with pytest.raises(RuntimeError, match="fitted"):
            mogp.predict_composite(
                np.array([[0.0]]),
                {"f_angle": 0.5, "f_freq": 0.25, "f_voltage": 0.25},
            )

    def test_missing_y_dict_key_raises(self):
        mogp = MultiOutputGP()
        X = np.array([[0.0], [1.0]])
        y_dict = {"f_angle": np.array([0.0, 1.0])}  # missing keys
        with pytest.raises(KeyError, match="f_freq"):
            mogp.fit(X, y_dict)

    def test_std_is_non_negative(self, noisy_synthetic_data):
        X_train, X_test, y_train, _ = noisy_synthetic_data
        mogp = MultiOutputGP(n_restarts=2, seed=0)
        mogp.fit(X_train, y_train)
        preds = mogp.predict(X_test)
        for key in preds:
            assert np.all(preds[key]["std"] >= 0), f"Negative std for '{key}'"


class TestR2:
    """R-squared quality checks on clean data."""

    def test_r2_above_threshold(self, clean_synthetic_data):
        X_train, X_test, y_train, y_test = clean_synthetic_data
        mogp = MultiOutputGP(n_restarts=3, seed=0)
        mogp.fit(X_train, y_train)
        scores = mogp.r2_per_output(X_test, y_test)

        for key in ("f_angle", "f_freq", "f_voltage", "severity"):
            assert key in scores, f"Missing R² score for '{key}'"
            assert scores[key] > 0.8, (
                f"R² for '{key}' is {scores[key]:.4f}, expected > 0.8"
            )


class TestUncertainty:
    """Verify that uncertainty is higher in sparse regions."""

    def test_uncertainty_higher_in_sparse_region(self, rng):
        # Train on a narrow band; test includes points far from training.
        X_train = rng.uniform(1.0, 2.0, size=(40, 1))
        y_train = {
            "f_angle":   np.sin(X_train[:, 0]) + rng.normal(0, 0.01, 40),
            "f_freq":    np.cos(X_train[:, 0]) + rng.normal(0, 0.01, 40),
            "f_voltage": np.sin(X_train[:, 0]) + rng.normal(0, 0.01, 40),
        }
        y_train["severity"] = (
            0.5 * y_train["f_angle"]
            + 0.25 * y_train["f_freq"]
            + 0.25 * y_train["f_voltage"]
        )

        mogp = MultiOutputGP(n_restarts=2, seed=0)
        mogp.fit(X_train, y_train)

        # Dense region (within training support) vs sparse (far outside).
        X_dense = np.linspace(1.2, 1.8, 20).reshape(-1, 1)
        X_sparse = np.linspace(5.0, 6.0, 20).reshape(-1, 1)

        preds_dense = mogp.predict(X_dense)
        preds_sparse = mogp.predict(X_sparse)

        for key in ("f_angle", "f_freq", "f_voltage"):
            mean_std_dense = np.mean(preds_dense[key]["std"])
            mean_std_sparse = np.mean(preds_sparse[key]["std"])
            assert mean_std_sparse > mean_std_dense, (
                f"Expected higher uncertainty in sparse region for '{key}': "
                f"sparse={mean_std_sparse:.4f} vs dense={mean_std_dense:.4f}"
            )


class TestComposite:
    """Verify composite severity calculation with weighted sum."""

    def test_composite_matches_weighted_sum(self, noisy_synthetic_data):
        X_train, X_test, y_train, _ = noisy_synthetic_data
        mogp = MultiOutputGP(n_restarts=2, seed=0)
        mogp.fit(X_train, y_train)

        weights = {"f_angle": 0.5, "f_freq": 0.25, "f_voltage": 0.25}
        composite = mogp.predict_composite(X_test, weights)
        preds = mogp.predict(X_test)

        # Expected mean = weighted sum of individual means.
        expected_mean = (
            weights["f_angle"] * preds["f_angle"]["mean"]
            + weights["f_freq"] * preds["f_freq"]["mean"]
            + weights["f_voltage"] * preds["f_voltage"]["mean"]
        )
        np.testing.assert_allclose(
            composite["mean"],
            expected_mean,
            atol=1e-10,
            err_msg="Composite mean does not match weighted sum of individual means",
        )

        # Expected std = sqrt of sum of (w_i * std_i)^2.
        expected_std = np.sqrt(
            (weights["f_angle"] * preds["f_angle"]["std"]) ** 2
            + (weights["f_freq"] * preds["f_freq"]["std"]) ** 2
            + (weights["f_voltage"] * preds["f_voltage"]["std"]) ** 2
        )
        np.testing.assert_allclose(
            composite["std"],
            expected_std,
            atol=1e-10,
            err_msg="Composite std does not match propagated uncertainty",
        )

    def test_composite_missing_weight_raises(self, noisy_synthetic_data):
        X_train, X_test, y_train, _ = noisy_synthetic_data
        mogp = MultiOutputGP(n_restarts=2, seed=0)
        mogp.fit(X_train, y_train)

        with pytest.raises(KeyError, match="f_freq"):
            mogp.predict_composite(
                X_test,
                {"f_angle": 0.5, "f_voltage": 0.5},  # missing f_freq
            )


class TestActiveLearning:
    """Verify acquisition selects high-uncertainty points."""

    def test_selects_high_uncertainty_points(self, rng):
        # Train on a narrow band.
        X_train = rng.uniform(0.5, 1.5, size=(30, 1))
        y_train = {
            "f_angle":   np.sin(X_train[:, 0]) + rng.normal(0, 0.01, 30),
            "f_freq":    np.cos(X_train[:, 0]) + rng.normal(0, 0.01, 30),
            "f_voltage": np.sin(X_train[:, 0]) + rng.normal(0, 0.01, 30),
        }
        y_train["severity"] = (
            0.5 * y_train["f_angle"]
            + 0.25 * y_train["f_freq"]
            + 0.25 * y_train["f_voltage"]
        )

        mogp = MultiOutputGP(n_restarts=2, seed=0)
        mogp.fit(X_train, y_train)

        # Pool with a mix of in-support and out-of-support points.
        X_pool = np.linspace(-3, 5, 100).reshape(-1, 1)
        indices = mogp.active_learning_acquisition(X_pool, n=10)

        assert len(indices) == 10
        assert indices.dtype == np.intp or np.issubdtype(indices.dtype, np.integer)

        # The selected points should be far from the training band [0.5, 1.5].
        selected_x = X_pool[indices]
        mean_abs_dist = np.mean(np.abs(selected_x - 1.0))
        # Points in the training band have distance ~0 from 1.0.
        # We expect selected points to be well outside, mean dist > 1.0.
        assert mean_abs_dist > 1.0, (
            f"Active learning selected points too close to training data: "
            f"mean distance = {mean_abs_dist:.4f}"
        )

    def test_n_larger_than_pool(self, rng):
        X_train = rng.uniform(0, 1, size=(20, 1))
        y_train = {
            "f_angle":   np.sin(X_train[:, 0]),
            "f_freq":    np.cos(X_train[:, 0]),
            "f_voltage": np.sin(X_train[:, 0]),
        }
        y_train["severity"] = y_train["f_angle"]

        mogp = MultiOutputGP(n_restarts=1, seed=0)
        mogp.fit(X_train, y_train)

        X_pool = np.array([[0.0], [0.5], [1.0]])
        indices = mogp.active_learning_acquisition(X_pool, n=10)
        # Should return at most len(X_pool) indices.
        assert len(indices) == 3


class TestSerialization:
    """Verify get_state / set_state round-trip."""

    def test_state_roundtrip(self, noisy_synthetic_data):
        X_train, X_test, y_train, _ = noisy_synthetic_data
        mogp = MultiOutputGP(n_restarts=2, seed=0)
        mogp.fit(X_train, y_train)

        preds_original = mogp.predict(X_test)
        state = mogp.get_state()

        # Create new instance and restore.
        mogp2 = MultiOutputGP()
        mogp2.set_state(state)
        preds_restored = mogp2.predict(X_test)

        for key in ("f_angle", "f_freq", "f_voltage", "severity"):
            np.testing.assert_allclose(
                preds_original[key]["mean"],
                preds_restored[key]["mean"],
                atol=1e-10,
                err_msg=f"Mean mismatch for '{key}' after state round-trip",
            )
            np.testing.assert_allclose(
                preds_original[key]["std"],
                preds_restored[key]["std"],
                atol=1e-10,
                err_msg=f"Std mismatch for '{key}' after state round-trip",
            )

    def test_unfitted_state(self):
        mogp = MultiOutputGP(n_restarts=3, seed=7)
        state = mogp.get_state()
        assert state["fitted"] is False
        assert state["models"] == {}
