"""Joint mode x fault parameter sweep for GP training data.

Collects simulation data across multiple operating modes AND fault parameters
to build a combined feature set for GP surrogate training.
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
from src.objective.severity import SeverityCalculator

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s", datefmt="%H:%M:%S")
logger = logging.getLogger(__name__)

# Fault parameter grid
FAULT_BUSES = [2, 3, 4, 5, 6, 7, 8, 9, 10]
CLEAR_TIMES = [0.05, 0.10, 0.15, 0.20, 0.30]


def main():
    output_dir = Path("data/processed/joint_sweep")
    output_dir.mkdir(parents=True, exist_ok=True)

    n_modes = 100

    # Generate feasible modes
    gen = ModeGenerator(n_modes=int(n_modes * 2), seed=42)
    mode_df = gen.generate()
    mode_df = gen.filter_feasible(mode_df)
    mode_df = mode_df.head(n_modes)
    logger.info(f"Using {len(mode_df)} feasible modes")

    # Initialize ANDES
    logger.info("Initializing ANDES wrapper...")
    wrapper = ANDESWrapper(
        case_path="kundur/kundur_full.xlsx",
        config={"tf": 10.0, "tstep": 0.02, "timeout": 60},
    )
    calculator = SeverityCalculator()

    # Build fault parameter combinations
    fault_configs = [(fb, ct) for fb in FAULT_BUSES for ct in CLEAR_TIMES]
    total = len(mode_df) * len(fault_configs)
    logger.info(f"Total simulations: {len(mode_df)} modes x {len(fault_configs)} faults = {total}")

    checkpoint_path = output_dir / "joint_sweep_checkpoint.csv"
    results = []

    # Load checkpoint
    start_mode = 0
    if checkpoint_path.exists():
        existing = pd.read_csv(checkpoint_path)
        results = existing.to_dict("records")
        start_mode = len(results) // len(fault_configs)
        logger.info(f"Resuming from checkpoint: {len(results)} done, starting at mode {start_mode}")

    t_start = time.time()
    n_success = 0
    n_fail = 0

    for mode_idx, (mode_id, mode) in enumerate(mode_df.iterrows()):
        if mode_idx < start_mode:
            continue

        for fb, ct in fault_configs:
            scenario = {
                "fault_bus": fb,
                "fault_time": 1.0,
                "clear_time": 1.0 + ct,
                "load_scaling": {
                    "area1": max(float(mode["load_area1"]) * (1.0 - float(mode["solar_area1_pct"])), 0.3),
                    "area2": max(float(mode["load_area2"]) * (1.0 - float(mode["solar_area2_pct"])), 0.3),
                },
                "gen_scaling": {
                    "GENROU_1": max(1.0 - float(mode["wind_area1_pct"]), 0.3),
                    "GENROU_3": max((1.0 - float(mode["wind_area2_pct"])) * 0.6, 0.3),
                    "GENROU_4": max((1.0 - float(mode["wind_area2_pct"])) * 0.4, 0.3),
                    "GENROU_2": max(1.0 + float(mode["gen_dispatch_bias"]), 0.3),
                },
                "line_trip": None,
            }

            try:
                result = wrapper.evaluate(scenario)
                sev_info = calculator.compute_with_breakdown(result)
                row = {
                    "mode_id": mode_idx,
                    "fault_bus": fb,
                    "clear_time": ct,
                    "wind_area1_pct": float(mode["wind_area1_pct"]),
                    "wind_area2_pct": float(mode["wind_area2_pct"]),
                    "solar_area1_pct": float(mode["solar_area1_pct"]),
                    "solar_area2_pct": float(mode["solar_area2_pct"]),
                    "load_area1": float(mode["load_area1"]),
                    "load_area2": float(mode["load_area2"]),
                    "gen_dispatch_bias": float(mode["gen_dispatch_bias"]),
                    "success": result.success,
                    "stable": result.stable,
                    "severity": sev_info["severity"],
                    "f_angle": sev_info["f_angle"],
                    "f_freq": sev_info["f_freq"],
                    "f_voltage": sev_info["f_voltage"],
                }
                if result.success:
                    n_success += 1
                else:
                    n_fail += 1

            except Exception as e:
                row = {
                    "mode_id": mode_idx,
                    "fault_bus": fb,
                    "clear_time": ct,
                    "wind_area1_pct": float(mode["wind_area1_pct"]),
                    "wind_area2_pct": float(mode["wind_area2_pct"]),
                    "solar_area1_pct": float(mode["solar_area1_pct"]),
                    "solar_area2_pct": float(mode["solar_area2_pct"]),
                    "load_area1": float(mode["load_area1"]),
                    "load_area2": float(mode["load_area2"]),
                    "gen_dispatch_bias": float(mode["gen_dispatch_bias"]),
                    "success": False,
                    "stable": False,
                    "severity": 1.0,
                    "f_angle": np.nan,
                    "f_freq": np.nan,
                    "f_voltage": np.nan,
                    "error": str(e),
                }
                n_fail += 1

            results.append(row)

        # Checkpoint every mode
        if (mode_idx + 1) % 5 == 0 or mode_idx == len(mode_df) - 1:
            elapsed = time.time() - t_start
            rate = len(fault_configs) * min(mode_idx + 1 - start_mode, 1) / max(elapsed, 1)
            logger.info(
                f"[{mode_idx+1}/{len(mode_df)}] OK={n_success} FAIL={n_fail} "
                f"elapsed={elapsed/60:.1f}min"
            )
            pd.DataFrame(results).to_csv(checkpoint_path, index=False)

    # Save final
    df = pd.DataFrame(results)
    df.to_csv(output_dir / "joint_sweep_results.csv", index=False)

    ok_df = df[df["success"]]
    logger.info(f"\n{'='*50}")
    logger.info(f"Joint sweep complete: {len(df)} total, {len(ok_df)} success ({100*len(ok_df)/len(df):.1f}%)")
    if len(ok_df) > 0:
        logger.info(f"Severity: mean={ok_df['severity'].mean():.3f}, std={ok_df['severity'].std():.3f}")
        logger.info(f"f_angle: mean={ok_df['f_angle'].mean():.3f}")
        logger.info(f"f_voltage: mean={ok_df['f_voltage'].mean():.3f}")
        logger.info(f"f_freq: mean={ok_df['f_freq'].mean():.3f}")
    logger.info(f"Results saved to {output_dir}")


if __name__ == "__main__":
    main()
