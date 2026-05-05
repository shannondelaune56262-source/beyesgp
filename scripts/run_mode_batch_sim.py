"""Batch simulation of operating modes for clustering analysis.

Runs ANDES TDS for each operating mode, computes severity, and saves results.
Supports checkpointing (resume from last completed mode) and progress logging.
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

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger(__name__)


def run_batch(
    n_modes: int = 50,
    start_idx: int = 0,
    fault_bus: int = 7,
    fault_time: float = 1.0,
    clear_duration: float = 0.10,
    output_dir: str = "data/processed/mode_sweep",
):
    """Run batch simulation of operating modes.

    Args:
        n_modes: Number of modes to simulate (from the LHS pool).
        start_idx: Start index (for resuming).
        fault_bus: Fault location.
        fault_time: Fault start time.
        clear_duration: Fault duration (clear_time = fault_time + clear_duration).
        output_dir: Output directory.
    """
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)

    clear_time = fault_time + clear_duration

    # Generate modes (oversample then filter for feasibility)
    gen = ModeGenerator(n_modes=int(n_modes * 2), seed=42)
    df = gen.generate()
    df = gen.filter_feasible(df)
    df = df.head(n_modes)  # Trim to requested count
    df = df.reset_index(drop=True)
    df.index.name = "mode_id"
    logger.info(f"Using {len(df)} feasible modes")

    # Check for existing checkpoint
    checkpoint_path = output_path / "checkpoint.csv"
    if checkpoint_path.exists():
        existing = pd.read_csv(checkpoint_path, index_col="mode_id")
        start_idx = len(existing)
        logger.info(f"Resuming from checkpoint: {start_idx} modes already done")
    else:
        existing = None

    # Initialize ANDES wrapper (triggers codegen pre-warm)
    logger.info("Initializing ANDES wrapper...")
    wrapper = ANDESWrapper(
        case_path="kundur/kundur_full.xlsx",
        config={"tf": 10.0, "tstep": 0.02, "timeout": 60},
    )
    calculator = SeverityCalculator()

    # Build scenarios
    scenarios = gen.to_scenarios(
        df, fault_bus=fault_bus, fault_time=fault_time, clear_time=clear_time
    )

    # Results storage
    results_rows = []
    if existing is not None:
        for _, row in existing.iterrows():
            results_rows.append(row.to_dict())

    # Run simulations
    total = len(scenarios)
    batch_start = time.time()
    n_success = sum(1 for r in results_rows if r.get("success", False))
    n_fail = sum(1 for r in results_rows if not r.get("success", False))

    logger.info(f"Starting simulations: {start_idx} done, {total - start_idx} remaining")

    for i in range(start_idx, total):
        mode = df.iloc[i]
        scenario = scenarios[i]

        t0 = time.time()
        try:
            result = wrapper.evaluate(scenario)
            severity_info = calculator.compute_with_breakdown(result)
            elapsed = time.time() - t0

            row = {
                "mode_id": i,
                "success": result.success,
                "stable": result.stable,
                "severity": severity_info["severity"],
                "f_angle": severity_info["f_angle"],
                "f_freq": severity_info["f_freq"],
                "f_voltage": severity_info["f_voltage"],
                "angle_sep_deg": severity_info.get("angle_sep_deg", np.nan),
                "freq_dev_hz": severity_info.get("freq_dev_hz", np.nan),
                "voltage_dip": severity_info.get("voltage_dip", np.nan),
                "sim_time": elapsed,
            }
            if result.success:
                n_success += 1
            else:
                n_fail += 1

        except Exception as e:
            elapsed = time.time() - t0
            row = {
                "mode_id": i,
                "success": False,
                "stable": False,
                "severity": 1.0,
                "f_angle": np.nan,
                "f_freq": np.nan,
                "f_voltage": np.nan,
                "angle_sep_deg": np.nan,
                "freq_dev_hz": np.nan,
                "voltage_dip": np.nan,
                "sim_time": elapsed,
                "error": str(e),
            }
            n_fail += 1

        results_rows.append(row)

        # Progress logging every 10 modes
        if (i + 1) % 10 == 0 or i == total - 1:
            elapsed_total = time.time() - batch_start
            rate = (i + 1 - start_idx) / elapsed_total if elapsed_total > 0 else 0
            eta = (total - i - 1) / rate if rate > 0 else 0
            logger.info(
                f"[{i+1}/{total}] sev={row['severity']:.3f} "
                f"stable={row['stable']} "
                f"OK={n_success} FAIL={n_fail} "
                f"rate={rate:.1f}/s ETA={eta/60:.0f}min"
            )

            # Save checkpoint
            checkpoint_df = pd.DataFrame(results_rows)
            checkpoint_df.to_csv(checkpoint_path)

    # Merge mode definitions with simulation results
    results_df = pd.DataFrame(results_rows)

    # Join with mode parameter columns (both indexed by sequential mode_id)
    full_df = pd.concat([df.reset_index(drop=True), results_df.drop(columns=["mode_id"], errors="ignore")], axis=1)

    # Save final results
    final_path = output_path / "mode_sweep_results.csv"
    full_df.to_csv(final_path)

    # Summary
    logger.info(f"\n{'='*60}")
    logger.info(f"Batch simulation complete")
    logger.info(f"  Total: {len(full_df)}")
    logger.info(f"  Success: {n_success} ({100*n_success/total:.1f}%)")
    logger.info(f"  Failed: {n_fail} ({100*n_fail/total:.1f}%)")
    logger.info(f"  Stable: {full_df['stable'].sum()}")
    logger.info(f"  Unstable: {(~full_df['stable']).sum()}")
    if n_success > 0:
        success_df = full_df[full_df["success"]]
        logger.info(f"  Severity: mean={success_df['severity'].mean():.3f}, "
                     f"std={success_df['severity'].std():.3f}, "
                     f"max={success_df['severity'].max():.3f}")
    logger.info(f"  Results saved to: {final_path}")
    total_time = time.time() - batch_start
    logger.info(f"  Total time: {total_time/60:.1f} min")

    return full_df


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Batch mode simulation")
    parser.add_argument("--n-modes", type=int, default=50, help="Number of modes to simulate")
    parser.add_argument("--fault-bus", type=int, default=7)
    parser.add_argument("--clear-duration", type=float, default=0.10,
                        help="Fault clearing duration in seconds")
    args = parser.parse_args()

    run_batch(
        n_modes=args.n_modes,
        fault_bus=args.fault_bus,
        clear_duration=args.clear_duration,
    )
