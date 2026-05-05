"""High-RE multi-scenario simulation sweep for paper experiment data.

Generates 200 modes x 7 fault types x 4 RE levels = 5600 simulations.
Records severity breakdown (f_angle, f_freq, f_voltage) for each simulation.
"""
import logging
import sys
import time
import io
from pathlib import Path

import numpy as np
import pandas as pd

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8")
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.simulator.andes_wrapper import ANDESWrapper
from src.objective.severity import SeverityCalculator
from src.scenario.mode_generator import ModeGenerator

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s", datefmt="%H:%M:%S")
logger = logging.getLogger(__name__)

FAULT_CONFIGS = [
    ("angle_bus7", 7, 0.10),
    ("angle_bus8", 8, 0.10),
    ("voltage_bus9", 9, 0.10),
    ("voltage_bus10", 10, 0.10),
    ("freq_bus2", 2, 0.10),
    ("freq_bus4", 4, 0.15),
    ("severe_bus7", 7, 0.20),
]


def main():
    output_dir = Path("data/processed/re_sweep")
    output_dir.mkdir(parents=True, exist_ok=True)

    # Generate modes across all RE levels
    gen = ModeGenerator(n_modes=200, seed=42, re_levels=[0, 1, 2, 3, 4])
    df_modes = gen.generate()
    df_modes = gen.filter_feasible(df_modes)
    logger.info(f"Generated {len(df_modes)} feasible modes across RE levels")

    # Initialize ANDES
    logger.info("Initializing ANDES wrapper...")
    wrapper = ANDESWrapper(
        case_path="kundur/kundur_full.xlsx",
        config={"tf": 10.0, "tstep": 0.02, "timeout": 60},
    )
    calculator = SeverityCalculator()

    all_results = []
    n_total = len(df_modes) * len(FAULT_CONFIGS)
    checkpoint_path = output_dir / "re_sweep_checkpoint.csv"

    start_time = time.time()
    for mode_idx, (_, mode_row) in enumerate(df_modes.iterrows()):
        for fault_name, f_bus, ct in FAULT_CONFIGS:
            scenario = {
                "fault_bus": f_bus,
                "fault_time": 1.0,
                "clear_time": 1.0 + ct,
                "load_scaling": {
                    "area1": max(float(mode_row["load_area1"]) * (1.0 - float(mode_row["solar_area1_pct"])), 0.3),
                    "area2": max(float(mode_row["load_area2"]) * (1.0 - float(mode_row["solar_area2_pct"])), 0.3),
                },
                "gen_scaling": {
                    "GENROU_1": max(float(mode_row.get("gen_scaling_gen1", 0.7)), 0.3),
                    "GENROU_2": max(float(mode_row.get("gen_scaling_gen2", 0.8)), 0.3),
                    "GENROU_3": max(float(mode_row.get("gen_scaling_gen3", 0.6)), 0.3),
                    "GENROU_4": max(float(mode_row.get("gen_scaling_gen4", 0.4)), 0.3),
                },
            }

            # Get RE devices for this mode's level
            re_level = int(mode_row.get("re_level", 0))
            from src.simulator.andes_wrapper import RE_LEVEL_CONFIGS
            from src.scenario.mode_generator import RE_LEVEL_MAP
            if re_level > 0 and re_level in RE_LEVEL_CONFIGS:
                scenario["re_devices"] = RE_LEVEL_CONFIGS[re_level]

            # Apply gen displacement from RE level
            re_cfg = RE_LEVEL_MAP.get(re_level, RE_LEVEL_MAP[0])
            gf1 = re_cfg["gen_factor_a1"]
            gf2 = re_cfg["gen_factor_a2"]
            scenario["gen_scaling"] = {
                "GENROU_1": max(gf1 * (1.0 - mode_row["wind_area1_pct"]), 0.3),
                "GENROU_2": max((1.0 + mode_row["gen_dispatch_bias"]) * gf1, 0.3),
                "GENROU_3": max(gf2 * (1.0 - mode_row["wind_area2_pct"]) * 0.6, 0.3),
                "GENROU_4": max(gf2 * (1.0 - mode_row["wind_area2_pct"]) * 0.4, 0.3),
            }

            try:
                result = wrapper.evaluate(scenario)
            except Exception as e:
                logger.warning(f"Mode {mode_idx} fault {fault_name} failed: {e}")
                result = None

            row_data = {
                "mode_idx": mode_idx,
                "re_level": re_level,
                "fault_name": fault_name,
                "fault_bus": f_bus,
                "clear_time": ct,
                "success": result.success if result else False,
                "stable": result.stable if result else False,
                "severity": 0.0,
                "f_angle": float("nan"),
                "f_freq": float("nan"),
                "f_voltage": float("nan"),
                "V_min": float("nan"),
                "max_angle_deg": float("nan"),
                "max_freq_dev_hz": float("nan"),
                "sim_time": result.sim_time if result else 0.0,
            }

            # Store mode features
            for col in ["wind_area1_pct", "wind_area2_pct", "solar_area1_pct", "solar_area2_pct",
                        "load_area1", "load_area2", "gen_dispatch_bias"]:
                row_data[col] = float(mode_row[col])

            if result and result.success:
                # Compute severity breakdown
                try:
                    sev_info = calculator.compute_with_breakdown(result)
                    row_data["severity"] = sev_info["severity"]
                    row_data["f_angle"] = sev_info.get("f_angle", float("nan"))
                    row_data["f_freq"] = sev_info.get("f_freq", float("nan"))
                    row_data["f_voltage"] = sev_info.get("f_voltage", float("nan"))
                except Exception:
                    pass

                # Extract physical metrics
                if result.bus_voltages is not None:
                    row_data["V_min"] = float(np.min(result.bus_voltages))
                if result.rotor_angles is not None:
                    spread = np.max(result.rotor_angles, axis=1) - np.min(result.rotor_angles, axis=1)
                    row_data["max_angle_deg"] = float(np.max(np.rad2deg(spread)))
                if result.rotor_speeds is not None:
                    row_data["max_freq_dev_hz"] = float(np.max(np.abs(result.rotor_speeds - 1.0)) * 60.0)

            all_results.append(row_data)

        # Checkpoint every 10 modes
        if (mode_idx + 1) % 10 == 0:
            elapsed = time.time() - start_time
            progress = len(all_results) / n_total * 100
            logger.info(f"  Progress: {mode_idx+1}/{len(df_modes)} modes ({progress:.1f}%), "
                       f"{len(all_results)} sims, {elapsed:.0f}s elapsed")
            pd.DataFrame(all_results).to_csv(checkpoint_path, index=False)

    # Save final results
    results_df = pd.DataFrame(all_results)
    results_df.to_csv(output_dir / "re_sweep_results.csv", index=False)

    # Summary
    n_success = results_df["success"].sum()
    elapsed = time.time() - start_time
    logger.info(f"\n=== RE Sweep Complete ===")
    logger.info(f"Total: {len(results_df)} simulations, {n_success} successful ({n_success/len(results_df)*100:.1f}%)")
    logger.info(f"Time: {elapsed:.0f}s ({elapsed/60:.1f} min)")

    # Per RE level summary
    for level in range(5):
        mask = results_df["re_level"] == level
        sub = results_df[mask]
        n_ok = sub["success"].sum()
        if n_ok > 0:
            ok = sub[sub["success"]]
            logger.info(
                f"  RE Level {level}: {n_ok}/{len(sub)} success, "
                f"severity={ok['severity'].mean():.3f}±{ok['severity'].std():.3f}, "
                f"f_angle={ok['f_angle'].mean():.3f}, f_freq={ok['f_freq'].mean():.3f}, "
                f"f_voltage={ok['f_voltage'].mean():.3f}"
            )

    logger.info(f"Results saved to {output_dir}")


if __name__ == "__main__":
    main()
