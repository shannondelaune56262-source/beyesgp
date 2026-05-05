"""Composite severity metric for worst-case scenario search."""

import numpy as np

from src.simulator.andes_wrapper import SimulationResult
from src.simulator.result_extractor import ResultExtractor


class SeverityCalculator:
    """Computes composite severity score from simulation results.

    S(x) = w_angle * f_angle + w_freq * f_freq + w_voltage * f_voltage

    All components are normalized to [0, 1], where 1 = most severe.
    """

    def __init__(
        self,
        w_angle: float = 0.5,
        w_freq: float = 0.25,
        w_voltage: float = 0.25,
        angle_threshold: float = 180.0,
        freq_nominal: float = 60.0,
        freq_deviation: float = 2.0,
    ):
        self.w_angle = w_angle
        self.w_freq = w_freq
        self.w_voltage = w_voltage
        self.angle_threshold = angle_threshold
        self.freq_nominal = freq_nominal
        self.freq_deviation = freq_deviation
        self.extractor = ResultExtractor(freq_nominal=freq_nominal)

    def compute(self, result: SimulationResult) -> float:
        if not result.success:
            return 1.0
        info = self.compute_with_breakdown(result)
        return info["severity"]

    def _angle_severity(self, max_angle_sep_deg: float) -> float:
        return min(max_angle_sep_deg / self.angle_threshold, 1.0)

    def _freq_severity(self, freq_dev_hz: float) -> float:
        return min(freq_dev_hz / self.freq_deviation, 1.0)

    def _voltage_severity(self, voltage_dip: float) -> float:
        return min(max(voltage_dip, 0.0), 1.0)

    def compute_with_breakdown(self, result: SimulationResult) -> dict:
        if not result.success:
            return {
                "severity": 1.0,
                "f_angle": 1.0,
                "f_freq": 1.0,
                "f_voltage": 1.0,
                "stable": False,
            }

        metrics = self.extractor.extract_all(result)
        f_angle = self._angle_severity(metrics["angle_sep"])
        f_freq = self._freq_severity(metrics["freq_dev"])
        f_voltage = self._voltage_severity(metrics["voltage_dip"])
        severity = (
            self.w_angle * f_angle
            + self.w_freq * f_freq
            + self.w_voltage * f_voltage
        )

        return {
            "severity": min(severity, 1.0),
            "f_angle": f_angle,
            "f_freq": f_freq,
            "f_voltage": f_voltage,
            "angle_sep_deg": metrics["angle_sep"],
            "freq_dev_hz": metrics["freq_dev"],
            "voltage_dip": metrics["voltage_dip"],
            "stable": metrics["stable"],
        }


class EntropyWeightedSeverityCalculator:
    """Severity calculator with entropy-based dynamic weights.

    Instead of fixed weights (w_angle=0.5, w_freq=0.25, w_voltage=0.25),
    computes weights from the information entropy of each constraint's
    distribution across a batch of results. Constraints with higher
    variance (more discriminative) get higher weights.

    Based on Gemini research suggestion: w_i proportional to H(phi_i).
    """

    def __init__(
        self,
        angle_threshold: float = 180.0,
        freq_nominal: float = 60.0,
        freq_deviation: float = 2.0,
        fallback_weights: tuple = (0.5, 0.25, 0.25),
    ):
        self.angle_threshold = angle_threshold
        self.freq_nominal = freq_nominal
        self.freq_deviation = freq_deviation
        self.fallback_weights = fallback_weights
        self.w_angle, self.w_freq, self.w_voltage = fallback_weights
        self.extractor = ResultExtractor(freq_nominal=freq_nominal)
        self._weights_fitted = False

    def fit_weights(self, breakdowns: list[dict]) -> None:
        """Compute entropy-based weights from a batch of severity breakdowns.

        Args:
            breakdowns: List of dicts from compute_with_breakdown().
        """
        if len(breakdowns) < 10:
            return

        f_angles = np.array([b["f_angle"] for b in breakdowns])
        f_freqs = np.array([b["f_freq"] for b in breakdowns])
        f_voltages = np.array([b["f_voltage"] for b in breakdowns])

        entropies = []
        for vals in [f_angles, f_freqs, f_voltages]:
            entropies.append(self._differential_entropy(vals))

        total = sum(entropies)
        if total < 1e-10:
            self.w_angle, self.w_freq, self.w_voltage = self.fallback_weights
        else:
            self.w_angle = entropies[0] / total
            self.w_freq = entropies[1] / total
            self.w_voltage = entropies[2] / total

        self._weights_fitted = True

    def _differential_entropy(self, x: np.ndarray) -> float:
        """Estimate differential entropy via variance (Gaussian approximation).

        H(X) ≈ 0.5 * ln(2πe * Var(X))
        For our purposes, std is sufficient (monotonic with entropy).
        """
        std = np.std(x)
        if std < 1e-10:
            return 1e-10
        return std

    def compute(self, result: SimulationResult) -> float:
        if not result.success:
            return 1.0
        info = self.compute_with_breakdown(result)
        return info["severity"]

    def compute_with_breakdown(self, result: SimulationResult) -> dict:
        if not result.success:
            return {
                "severity": 1.0,
                "f_angle": 1.0,
                "f_freq": 1.0,
                "f_voltage": 1.0,
                "stable": False,
            }

        metrics = self.extractor.extract_all(result)
        f_angle = min(metrics["angle_sep"] / self.angle_threshold, 1.0)
        f_freq = min(metrics["freq_dev"] / self.freq_deviation, 1.0)
        f_voltage = min(max(metrics["voltage_dip"], 0.0), 1.0)

        severity = (
            self.w_angle * f_angle
            + self.w_freq * f_freq
            + self.w_voltage * f_voltage
        )

        return {
            "severity": min(severity, 1.0),
            "f_angle": f_angle,
            "f_freq": f_freq,
            "f_voltage": f_voltage,
            "angle_sep_deg": metrics["angle_sep"],
            "freq_dev_hz": metrics["freq_dev"],
            "voltage_dip": metrics["voltage_dip"],
            "stable": metrics["stable"],
            "w_angle": self.w_angle,
            "w_freq": self.w_freq,
            "w_voltage": self.w_voltage,
        }
