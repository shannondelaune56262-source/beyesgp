"""Extract and post-process time-series data from simulation results."""

import numpy as np

from src.simulator.andes_wrapper import SimulationResult


class ResultExtractor:
    """Post-process ANDES simulation results for severity calculation."""

    def __init__(self, freq_nominal: float = 60.0):
        self.freq_nominal = freq_nominal

    def max_angle_separation(self, result: SimulationResult) -> float:
        """Compute maximum rotor angle separation across all generators.

        Returns the maximum angular difference (in degrees) between
        any two generators at any point in time.
        """
        if result.rotor_angles is None:
            return 180.0 if not result.stable else 0.0

        angles_rad = result.rotor_angles  # (n_t, n_gen)
        # Per-timestep max spread
        max_per_t = np.max(angles_rad, axis=1) - np.min(angles_rad, axis=1)
        return float(np.rad2deg(np.max(max_per_t)))

    def max_frequency_deviation(self, result: SimulationResult) -> float:
        """Compute maximum frequency deviation from nominal (Hz)."""
        if result.rotor_speeds is None:
            return self.freq_nominal if not result.stable else 0.0

        # omega is in per-unit; convert to Hz
        freq = result.rotor_speeds * self.freq_nominal
        deviation = np.max(np.abs(freq - self.freq_nominal))
        return float(deviation)

    def max_voltage_dip(self, result: SimulationResult) -> float:
        """Compute maximum bus voltage dip (1 - V_min) during simulation."""
        if result.bus_voltages is None:
            return 1.0 if not result.stable else 0.0

        # Minimum voltage across all buses and timesteps
        v_min = np.min(result.bus_voltages)
        dip = 1.0 - v_min
        return float(max(dip, 0.0))

    def extract_all(self, result: SimulationResult) -> dict:
        """Extract all metrics from a simulation result.

        Returns:
            Dict with angle_sep, freq_dev, voltage_dip, stable, sim_time.
        """
        return {
            "angle_sep": self.max_angle_separation(result),
            "freq_dev": self.max_frequency_deviation(result),
            "voltage_dip": self.max_voltage_dip(result),
            "stable": result.stable,
            "sim_time": result.sim_time,
        }
