"""Stability criteria checks (individual and combined)."""

import numpy as np

from src.simulator.andes_wrapper import SimulationResult


def check_rotor_angle_stability(result: SimulationResult, threshold: float = 180.0) -> bool:
    """Check if max relative rotor angle stays below threshold."""
    if result.rotor_angles is None:
        return result.stable
    max_per_t = np.max(result.rotor_angles, axis=1) - np.min(result.rotor_angles, axis=1)
    return bool(np.all(max_per_t < np.deg2rad(threshold)))


def check_frequency_stability(
    result: SimulationResult, freq_nominal: float = 60.0, tolerance: float = 2.0
) -> bool:
    """Check if frequency stays within [f_nom - tol, f_nom + tol]."""
    if result.rotor_speeds is None:
        return result.stable
    freq = result.rotor_speeds * freq_nominal
    return bool(np.all(np.abs(freq - freq_nominal) < tolerance))


def check_voltage_stability(result: SimulationResult, v_min: float = 0.9) -> bool:
    """Check if all bus voltages stay above v_min."""
    if result.bus_voltages is None:
        return result.stable
    return bool(np.all(result.bus_voltages > v_min))


def classify_stability(result: SimulationResult, freq_nominal: float = 60.0) -> dict:
    """Comprehensive stability classification."""
    return {
        "rotor_angle_stable": check_rotor_angle_stability(result),
        "frequency_stable": check_frequency_stability(result, freq_nominal),
        "voltage_stable": check_voltage_stability(result),
        "overall_stable": result.stable,
    }
