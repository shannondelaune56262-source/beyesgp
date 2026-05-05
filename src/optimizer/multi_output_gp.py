"""Multi-Output Gaussian Process surrogate model for severity prediction.

Simultaneously predicts f_angle, f_freq, and f_voltage severity components
with uncertainty quantification using independent sklearn GP regressors.

This provides a simpler, BoTorch-free alternative for multi-output GP
regression that is sufficient for the severity surrogate use case.
"""

import copy
import logging
from typing import Optional

import numpy as np
from sklearn.gaussian_process import GaussianProcessRegressor
from sklearn.gaussian_process.kernels import Matern, WhiteKernel
from sklearn.metrics import r2_score

logger = logging.getLogger(__name__)

# Keys expected in the training target dictionary.
OUTPUT_KEYS = ("f_angle", "f_freq", "f_voltage", "severity")


class MultiOutputGP:
    """Independent multi-output Gaussian Process surrogate model.

    Fits a separate GP for each severity component (f_angle, f_freq,
    f_voltage, severity) so that predictions come with per-output
    uncertainty estimates.  A composite prediction with propagated
    uncertainty is also supported.

    Args:
        kernel: Base kernel type.  Currently only ``"matern52"`` is
            supported (Matern kernel with nu=2.5).
        noise: Initial noise level for the WhiteKernel component.
        n_restarts: Number of optimizer restarts during GP fitting.
        seed: Random seed for reproducibility.
    """

    def __init__(
        self,
        kernel: str = "matern52",
        noise: float = 1e-4,
        n_restarts: int = 5,
        seed: int = 42,
    ):
        if kernel != "matern52":
            raise ValueError(
                f"Unsupported kernel '{kernel}'. Only 'matern52' is supported."
            )
        self.kernel_name = kernel
        self.noise = noise
        self.n_restarts = n_restarts
        self.seed = seed

        # Internal state -- populated by ``fit``.
        self._models: dict[str, GaussianProcessRegressor] = {}
        self._fitted = False

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _make_kernel(self):
        """Build a fresh Matern(2.5) + WhiteKernel instance."""
        return Matern(nu=2.5) + WhiteKernel(noise_level=self.noise)

    def _make_regressor(self) -> GaussianProcessRegressor:
        """Build a fresh GaussianProcessRegressor with current settings."""
        return GaussianProcessRegressor(
            kernel=self._make_kernel(),
            n_restarts_optimizer=self.n_restarts,
            random_state=self.seed,
            normalize_y=True,
        )

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def fit(self, X: np.ndarray, y_dict: dict[str, np.ndarray]) -> None:
        """Fit independent GP models for each severity output.

        Args:
            X: Training inputs, shape ``(n_samples, n_features)``.
            y_dict: Dictionary mapping output names to 1-D target arrays
                of shape ``(n_samples,)``.  Must contain at least the
                keys ``"f_angle"``, ``"f_freq"``, ``"f_voltage"``, and
                ``"severity"``.
        """
        for key in OUTPUT_KEYS:
            if key not in y_dict:
                raise KeyError(
                    f"y_dict is missing required key '{key}'. "
                    f"Expected keys: {OUTPUT_KEYS}"
                )

        self._models = {}
        for key in OUTPUT_KEYS:
            logger.info("Fitting GP for output '%s' ...", key)
            gp = self._make_regressor()
            gp.fit(X, y_dict[key])
            self._models[key] = gp
            logger.info(
                "  '%s' GP fitted (log-marginal-likelihood=%.4f)",
                key,
                gp.log_marginal_likelihood_value_,
            )

        self._fitted = True

    def predict(self, X: np.ndarray) -> dict[str, dict[str, np.ndarray]]:
        """Predict mean and standard deviation for each output.

        Args:
            X: Input points, shape ``(n_samples, n_features)``.

        Returns:
            Dictionary keyed by output name.  Each value is a dict::

                {
                    "mean": np.ndarray,   # shape (n_samples,)
                    "std":  np.ndarray,   # shape (n_samples,)
                }

        Raises:
            RuntimeError: If the model has not been fitted yet.
        """
        if not self._fitted:
            raise RuntimeError("Model must be fitted before prediction.")

        result: dict[str, dict[str, np.ndarray]] = {}
        for key in OUTPUT_KEYS:
            mean, std = self._models[key].predict(X, return_std=True)
            result[key] = {"mean": mean, "std": std}
        return result

    def predict_composite(
        self,
        X: np.ndarray,
        weights: dict[str, float],
    ) -> dict[str, np.ndarray]:
        """Compute weighted composite severity with propagated uncertainty.

        The composite severity is::

            S = w_angle * f_angle + w_freq * f_freq + w_voltage * f_voltage

        Uncertainty is propagated under the independence assumption::

            std(S) = sqrt(sum_i  (w_i * std_i)^2 )

        Args:
            X: Input points, shape ``(n_samples, n_features)``.
            weights: Dictionary with keys ``"f_angle"``, ``"f_freq"``,
                ``"f_voltage"`` mapping to their float weights.

        Returns:
            Dictionary with keys ``"mean"`` and ``"std"``, each a
            1-D array of shape ``(n_samples,)``.

        Raises:
            RuntimeError: If the model has not been fitted yet.
        """
        if not self._fitted:
            raise RuntimeError("Model must be fitted before prediction.")

        preds = self.predict(X)

        component_keys = ("f_angle", "f_freq", "f_voltage")
        for k in component_keys:
            if k not in weights:
                raise KeyError(f"weights dict is missing key '{k}'.")

        # Weighted mean.
        composite_mean = np.zeros(X.shape[0])
        for k in component_keys:
            composite_mean += weights[k] * preds[k]["mean"]

        # Propagated uncertainty (independence assumption).
        variance_sum = np.zeros(X.shape[0])
        for k in component_keys:
            variance_sum += (weights[k] * preds[k]["std"]) ** 2
        composite_std = np.sqrt(variance_sum)

        return {"mean": composite_mean, "std": composite_std}

    def r2_per_output(
        self,
        X_test: np.ndarray,
        y_test_dict: dict[str, np.ndarray],
    ) -> dict[str, float]:
        """Compute R-squared for each output on test data.

        Args:
            X_test: Test inputs, shape ``(n_samples, n_features)``.
            y_test_dict: Dictionary mapping output names to true target
                arrays of shape ``(n_samples,)``.

        Returns:
            Dictionary mapping each output name to its R-squared value.
        """
        preds = self.predict(X_test)
        scores: dict[str, float] = {}
        for key in OUTPUT_KEYS:
            if key in y_test_dict:
                scores[key] = float(
                    r2_score(y_test_dict[key], preds[key]["mean"])
                )
        return scores

    def active_learning_acquisition(
        self,
        X_pool: np.ndarray,
        n: int = 10,
    ) -> np.ndarray:
        """Select points from the pool with highest total uncertainty.

        The acquisition value for each point is the sum of predicted
        standard deviations across the three severity components
        (f_angle, f_freq, f_voltage).

        Args:
            X_pool: Candidate input points, shape ``(n_pool, n_features)``.
            n: Number of points to select.

        Returns:
            Array of integer indices (shape ``(n,)``) into ``X_pool``
            corresponding to the highest-uncertainty points.
        """
        preds = self.predict(X_pool)

        # Sum of stds across severity components (not severity itself).
        component_keys = ("f_angle", "f_freq", "f_voltage")
        total_uncertainty = np.zeros(X_pool.shape[0])
        for key in component_keys:
            total_uncertainty += preds[key]["std"]

        n_select = min(n, len(X_pool))
        return np.argsort(total_uncertainty)[::-1][:n_select]

    def get_state(self) -> dict:
        """Return serializable state of the model.

        The fitted GP model objects are deep-copied so that the returned
        state is fully independent of the current model.

        Returns:
            Dictionary containing all information needed to restore the
            model via ``set_state``.
        """
        return {
            "kernel_name": self.kernel_name,
            "noise": self.noise,
            "n_restarts": self.n_restarts,
            "seed": self.seed,
            "fitted": self._fitted,
            "models": copy.deepcopy(self._models) if self._fitted else {},
        }

    def set_state(self, state: dict) -> None:
        """Restore model from a previously saved state.

        Args:
            state: Dictionary produced by ``get_state``.
        """
        self.kernel_name = state["kernel_name"]
        self.noise = state["noise"]
        self.n_restarts = state["n_restarts"]
        self.seed = state["seed"]
        self._fitted = state["fitted"]
        self._models = copy.deepcopy(state["models"]) if self._fitted else {}
