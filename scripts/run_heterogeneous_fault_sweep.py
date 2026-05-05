"""Heterogeneous fault set sweep: test each mode under multiple fault types.

Gemini research insight: different fault locations trigger different constraints.
- Bus 7/8 faults → angle-dominated (inter-area oscillation)
- Bus 9/10 faults → voltage-dominated (load center, weak reactive support)
- Bus 2/3/4 faults → frequency-dominated (generator bus, active power imbalance)

Final severity = max across all fault types (worst-case principle).
"""

import logging
import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.scenario.mode_generator import ModeGenerator
from src.simulator.andes_wrapper import ANDESWrapper
from src.objective.severity import SeverityCalculator, EntropyWeightedSeverityCalculator

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s", datefmt="%H:%M:%S")
logger = logging.getLogger(__name__)

# Heterogeneous fault set design
FAULT_SETS = {
    "angle_dominated": {
        "fault_bus": 7, "clear_duration": 0.10,
        "line_trip": None,
        "description": "Bus 7 fault (tie-line area) → angle instability",
    },
    "angle_dominated_v2": {
        "fault_bus": 8, "clear_duration": 0.10,
        "line_trip": None,
        "description": "Bus 8 fault (tie-line area) → angle instability",
    },
    "voltage_dominated": {
        "fault_bus": 9, "clear_duration": 0.10,
        "line_trip": None,
        "description": "Bus 9 fault (load center) → voltage instability",
    },
    "voltage_dominated_v2": {
        "fault_bus": 10, "clear_duration": 0.10,
        "line_trip": None,
        "description": "Bus 10 fault (load center) → voltage instability",
    },
    "freq_dominated": {
        "fault_bus": 2, "clear_duration": 0.10,
        "line_trip": None,
        "description": "Bus 2 fault (generator bus) → frequency instability",
    },
    "freq_dominated_v2": {
        "fault_bus": 4, "clear_duration": 0.15,
        "line_trip": None,
        "description": "Bus 4 fault (generator bus, longer clearing) → freq + angle",
    },
    "severe_combined": {
        "fault_bus": 7, "clear_duration": 0.20,
        "line_trip": None,
        "description": "Bus 7 severe fault (long clearing) → angle + voltage",
    },
    # 同杆双回同时接地故障 (N-2): 联络线跳2回
    "tie_line_n2_fault": {
        "fault_bus": 7, "clear_duration": 0.10,
        "line_trips": [
            {"line_idx": "Line_4", "time": 1.0},
            {"line_idx": "Line_5", "time": 1.0},
        ],
        "description": "Bus 7-8 tie-line double-circuit simultaneous fault (N-2)",
    },
}


def main():
    output_dir = Path("data/processed/heterogeneous_fault_sweep")
    output_dir.mkdir(parents=True, exist_ok=True)

    n_modes = 150

    # Generate feasible modes
    gen = ModeGenerator(n_modes=int(n_modes * 2), seed=42)
    mode_df = gen.generate()
    mode_df = gen.filter_feasible(mode_df)
    mode_df = mode_df.head(n_modes).reset_index(drop=True)
    logger.info(f"Using {len(mode_df)} feasible modes")

    # Initialize ANDES
    logger.info("Initializing ANDES wrapper...")
    wrapper = ANDESWrapper(
        case_path="kundur/kundur_full.xlsx",
        config={"tf": 10.0, "tstep": 0.02, "timeout": 60},
    )
    base_calc = SeverityCalculator()

    fault_names = list(FAULT_SETS.keys())
    total = len(mode_df) * len(fault_names)
    logger.info(f"Total simulations: {len(mode_df)} modes × {len(fault_names)} faults = {total}")

    results = []
    t_start = time.time()
    n_done = 0

    for mode_idx, (_, mode) in enumerate(mode_df.iterrows()):
        mode_results = {}

        for fault_name, fault_cfg in FAULT_SETS.items():
            scenario = _build_scenario(mode, fault_cfg)
            try:
                result = wrapper.evaluate(scenario)
                sev_info = base_calc.compute_with_breakdown(result)
                mode_results[fault_name] = sev_info
                sev_info["success"] = result.success
                sev_info["fault_name"] = fault_name
            except Exception as e:
                mode_results[fault_name] = {
                    "severity": 1.0, "f_angle": np.nan, "f_freq": np.nan,
                    "f_voltage": np.nan, "success": False, "fault_name": fault_name,
                    "error": str(e),
                }

            n_done += 1

        # Compute max severity across all faults (WCS principle)
        sevs = [r.get("severity", 1.0) for r in mode_results.values()]
        max_sev = max(sevs)
        worst_fault = max(mode_results.keys(), key=lambda k: mode_results[k].get("severity", 0))

        # Also compute per-fault breakdown
        row = {
            "mode_id": mode_idx,
            "max_severity": max_sev,
            "worst_fault": worst_fault,
            "wind_area1_pct": float(mode["wind_area1_pct"]),
            "wind_area2_pct": float(mode["wind_area2_pct"]),
            "solar_area1_pct": float(mode["solar_area1_pct"]),
            "solar_area2_pct": float(mode["solar_area2_pct"]),
            "load_area1": float(mode["load_area1"]),
            "load_area2": float(mode["load_area2"]),
            "gen_dispatch_bias": float(mode["gen_dispatch_bias"]),
            "total_re_pct": float(mode["total_re_pct"]),
        }

        for fault_name, r in mode_results.items():
            prefix = fault_name
            row[f"{prefix}_severity"] = r.get("severity", np.nan)
            row[f"{prefix}_f_angle"] = r.get("f_angle", np.nan)
            row[f"{prefix}_f_freq"] = r.get("f_freq", np.nan)
            row[f"{prefix}_f_voltage"] = r.get("f_voltage", np.nan)
            row[f"{prefix}_success"] = r.get("success", False)

        results.append(row)

        if (mode_idx + 1) % 10 == 0 or mode_idx == len(mode_df) - 1:
            elapsed = time.time() - t_start
            rate = n_done / elapsed
            eta = (total - n_done) / rate
            logger.info(
                f"[{mode_idx+1}/{len(mode_df)}] max_sev={max_sev:.3f} "
                f"worst={worst_fault} rate={rate:.1f}/s ETA={eta/60:.0f}min"
            )

    # Save results
    df = pd.DataFrame(results)
    df.to_csv(output_dir / "heterogeneous_fault_results.csv", index=False)

    # Analyze: which fault dominates per mode
    logger.info(f"\n{'='*60}")
    logger.info("Heterogeneous Fault Sweep Analysis")

    # Per-fault severity statistics
    for fault_name in fault_names:
        col = f"{fault_name}_severity"
        if col in df.columns:
            ok = df[col].dropna()
            logger.info(f"  {fault_name}: mean={ok.mean():.3f}, std={ok.std():.3f}, "
                       f"min={ok.min():.3f}, max={ok.max():.3f}")

    # Per-fault voltage variance
    logger.info("\nPer-fault f_voltage statistics:")
    for fault_name in fault_names:
        col = f"{fault_name}_f_voltage"
        if col in df.columns:
            ok = df[col].dropna()
            logger.info(f"  {fault_name}: mean={ok.mean():.3f}, std={ok.std():.4f}")

    # Per-fault frequency variance
    logger.info("\nPer-fault f_freq statistics:")
    for fault_name in fault_names:
        col = f"{fault_name}_f_freq"
        if col in df.columns:
            ok = df[col].dropna()
            logger.info(f"  {fault_name}: mean={ok.mean():.3f}, std={ok.std():.3f}")

    # Worst fault distribution
    worst_counts = df["worst_fault"].value_counts()
    logger.info(f"\nWorst fault distribution:")
    for fault_name, count in worst_counts.items():
        logger.info(f"  {fault_name}: {count} modes ({100*count/len(df):.1f}%)")

    # Entropy-weighted severity analysis
    logger.info("\n--- Entropy-Weighted Severity Analysis ---")
    # Collect all successful breakdowns from bus 7 fault for entropy fitting
    breakdowns = []
    for _, row in df.iterrows():
        sev = row.get("angle_dominated_severity", np.nan)
        if not np.isnan(sev):
            breakdowns.append({
                "f_angle": row.get("angle_dominated_f_angle", 0),
                "f_freq": row.get("angle_dominated_f_freq", 0),
                "f_voltage": row.get("angle_dominated_f_voltage", 0),
            })

    entropy_calc = EntropyWeightedSeverityCalculator()
    entropy_calc.fit_weights(breakdowns)
    logger.info(f"Entropy weights (bus 7 fault): "
               f"w_angle={entropy_calc.w_angle:.3f}, "
               f"w_freq={entropy_calc.w_freq:.3f}, "
               f"w_voltage={entropy_calc.w_voltage:.3f}")

    # Collect breakdowns from bus 9 fault for comparison
    breakdowns_9 = []
    for _, row in df.iterrows():
        sev = row.get("voltage_dominated_severity", np.nan)
        if not np.isnan(sev):
            breakdowns_9.append({
                "f_angle": row.get("voltage_dominated_f_angle", 0),
                "f_freq": row.get("voltage_dominated_f_freq", 0),
                "f_voltage": row.get("voltage_dominated_f_voltage", 0),
            })

    if breakdowns_9:
        entropy_calc_9 = EntropyWeightedSeverityCalculator()
        entropy_calc_9.fit_weights(breakdowns_9)
        logger.info(f"Entropy weights (bus 9 fault): "
                   f"w_angle={entropy_calc_9.w_angle:.3f}, "
                   f"w_freq={entropy_calc_9.w_freq:.3f}, "
                   f"w_voltage={entropy_calc_9.w_voltage:.3f}")

    logger.info(f"\nResults saved to {output_dir}")


def _build_scenario(mode: pd.Series, fault_cfg: dict) -> dict:
    wind_a1 = float(mode.get("wind_area1_pct", 0.0))
    wind_a2 = float(mode.get("wind_area2_pct", 0.0))
    solar_a1 = float(mode.get("solar_area1_pct", 0.0))
    solar_a2 = float(mode.get("solar_area2_pct", 0.0))
    load_a1 = float(mode.get("load_area1", 1.0))
    load_a2 = float(mode.get("load_area2", 1.0))
    bias = float(mode.get("gen_dispatch_bias", 0.0))

    fault_time = 1.0
    clear_time = fault_time + fault_cfg["clear_duration"]

    return {
        "fault_bus": fault_cfg["fault_bus"],
        "fault_time": fault_time,
        "clear_time": clear_time,
        "load_scaling": {
            "area1": max(load_a1 * (1.0 - solar_a1), 0.3),
            "area2": max(load_a2 * (1.0 - solar_a2), 0.3),
        },
        "gen_scaling": {
            "GENROU_1": max(1.0 - wind_a1, 0.3),
            "GENROU_3": max((1.0 - wind_a2) * 0.6, 0.3),
            "GENROU_4": max((1.0 - wind_a2) * 0.4, 0.3),
            "GENROU_2": max(1.0 + bias, 0.3),
        },
        "line_trip": fault_cfg.get("line_trip"),
        "line_trips": fault_cfg.get("line_trips"),
    }


if __name__ == "__main__":
    main()
