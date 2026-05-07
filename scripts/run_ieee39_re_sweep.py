"""IEEE 39-bus high-RE multi-scenario simulation sweep for scalability validation.

Generates modes across 5 RE penetration levels x 9 fault types.
Records severity breakdown (f_angle, f_freq, f_voltage) and interface
transfer flows for each simulation.
"""
import logging
import sys
import time
import io
from pathlib import Path

import numpy as np
import pandas as pd
import yaml

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8")
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.simulator.andes_wrapper import ANDESWrapper
from src.objective.severity import SeverityCalculator
from src.scenario.ieee39_mode_generator import IEEE39ModeGenerator

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s", datefmt="%H:%M:%S")
logger = logging.getLogger(__name__)

# Fault configs from ieee39.yaml fault_configs section.
# For gen_trip_g4 there is no fault_bus; the scenario uses gen_trip="GENROU_4".
FAULT_CONFIGS = [
    ("bus4_ct10",   4,    0.10),
    ("bus14_ct10",  14,   0.10),
    ("bus16_ct10",  16,   0.10),
    ("bus26_ct10",  26,   0.10),
    ("bus20_ct15",  20,   0.15),
    ("bus8_ct15",   8,    0.15),
    ("bus4_ct25",   4,    0.25),
    ("bus16_ct25",  16,   0.25),
    ("gen_trip_g4", None, None),
]


def load_ieee39_config() -> dict:
    """Load IEEE 39-bus system configuration from ieee39.yaml."""
    config_path = Path(__file__).resolve().parents[1] / "configs" / "test_systems" / "ieee39.yaml"
    with open(config_path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def build_system_config(cfg: dict) -> dict:
    """Build system_config dict for ANDESWrapper from ieee39.yaml data."""
    generators = []
    for g in cfg["generators"]:
        generators.append({
            "name": g["name"],
            "bus": g["bus"],
            "area": g["area"],
            "p_mw": g["p_mw"],
            "sn_mva": g["sn_mva"],
            "h_s": g["h_s"],
            "type": g["type"],
        })

    areas = {}
    for area_name, area_data in cfg["areas"].items():
        areas[area_name] = {
            "buses": area_data["buses"],
            "gen_buses": area_data["gen_buses"],
            "generators": area_data["generators"],
            "loads": area_data["loads"],
            "load_mw": area_data["load_mw"],
            "gen_mw": area_data["gen_mw"],
        }

    return {
        "generators": generators,
        "areas": areas,
    }


def main():
    output_dir = Path("data/processed/ieee39_re_sweep")
    output_dir.mkdir(parents=True, exist_ok=True)

    # Load IEEE 39 config for tie_lines and system_config
    cfg = load_ieee39_config()
    tie_lines = cfg["tie_lines"]
    system_config = build_system_config(cfg)

    # Generate modes across all RE penetration levels
    re_penetration_levels = [0.0, 0.15, 0.30, 0.45, 0.60]
    gen = IEEE39ModeGenerator(
        n_modes=200,
        seed=42,
        re_penetration_levels=re_penetration_levels,
    )
    df_modes = gen.generate()
    df_modes = gen.filter_feasible(df_modes)
    logger.info(f"Generated {len(df_modes)} feasible modes across RE penetration levels")

    # Initialize ANDES wrapper with IEEE 39 case
    logger.info("Initializing ANDES wrapper for IEEE 39-bus...")
    wrapper = ANDESWrapper(
        case_path="ieee39/ieee39_full.xlsx",
        config={
            "tf": 15.0,
            "tstep": 0.02,
            "timeout": 120,
            "base_mva": 100.0,
        },
        tie_lines=tie_lines,
        system_config=system_config,
    )
    calculator = SeverityCalculator()

    all_results = []
    n_total = len(df_modes) * len(FAULT_CONFIGS)
    checkpoint_path = output_dir / "ieee39_re_sweep_checkpoint.csv"

    start_time = time.time()
    for mode_idx, (_, mode_row) in enumerate(df_modes.iterrows()):
        for fault_name, f_bus, ct in FAULT_CONFIGS:
            # Build scenario from mode parameters
            gen_scaling = gen._build_gen_scaling(mode_row)
            load_scaling = {
                "west": float(mode_row["load_level_west"]),
                "east": float(mode_row["load_level_east"]),
            }
            re_devices = gen._build_re_devices(mode_row)

            scenario = {
                "fault_time": 1.0,
                "load_scaling": load_scaling,
                "gen_scaling": gen_scaling,
                "re_devices": re_devices,
            }

            # Handle fault vs gen_trip scenarios
            if f_bus is not None:
                scenario["fault_bus"] = f_bus
                scenario["clear_time"] = 1.0 + ct
            else:
                # gen_trip_g4: no fault, just generator trip
                scenario["gen_trip"] = "GENROU_4"

            try:
                result = wrapper.evaluate(scenario)
            except Exception as e:
                logger.warning(f"Mode {mode_idx} fault {fault_name} failed: {e}")
                result = None

            # Base row data
            row_data = {
                "mode_idx": mode_idx,
                "re_penetration": float(mode_row["re_penetration"]),
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
                "initial_flow_MW": float("nan"),
                "final_flow_MW": float("nan"),
                "max_flow_MW": float("nan"),
                "sim_time": result.sim_time if result else 0.0,
            }

            # Store mode features
            mode_feature_cols = [
                "re_penetration", "re_west_fraction", "re_dispatch_west", "re_dispatch_east",
                "load_level_west", "load_level_east", "gen_dispatch",
                "total_re_mw", "west_re_mw", "east_re_mw",
                "west_import_demand", "east_export_surplus",
                "inertia_proxy", "transfer_demand", "distribution_mode",
            ]
            for col in mode_feature_cols:
                if col in mode_row.index:
                    val = mode_row[col]
                    row_data[col] = (
                        float(val) if isinstance(val, (np.floating, float))
                        else int(val) if isinstance(val, (np.integer, int))
                        else str(val)
                    )

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

                # Extract interface transfer flows from tie lines
                if result.tie_line_flows is not None:
                    initial_flow = sum(
                        tl_flow.get("initial_P_MW", 0.0)
                        for tl_flow in result.tie_line_flows.values()
                    )
                    final_flow = sum(
                        tl_flow.get("final_P_MW", 0.0)
                        for tl_flow in result.tie_line_flows.values()
                    )
                    max_flow = sum(
                        tl_flow.get("max_P_MW", 0.0)
                        for tl_flow in result.tie_line_flows.values()
                    )
                    row_data["initial_flow_MW"] = initial_flow
                    row_data["final_flow_MW"] = final_flow
                    row_data["max_flow_MW"] = max_flow

            all_results.append(row_data)

        # Checkpoint every 50 modes
        if (mode_idx + 1) % 50 == 0:
            elapsed = time.time() - start_time
            progress = len(all_results) / n_total * 100
            logger.info(f"  Progress: {mode_idx+1}/{len(df_modes)} modes ({progress:.1f}%), "
                       f"{len(all_results)} sims, {elapsed:.0f}s elapsed")
            pd.DataFrame(all_results).to_csv(checkpoint_path, index=False)

    # Save final results
    results_df = pd.DataFrame(all_results)
    results_df.to_csv(output_dir / "ieee39_re_sweep_results.csv", index=False)

    # Summary
    n_success = results_df["success"].sum()
    elapsed = time.time() - start_time
    logger.info(f"\n=== IEEE 39 RE Sweep Complete ===")
    logger.info(f"Total: {len(results_df)} simulations, {n_success} successful ({n_success/len(results_df)*100:.1f}%)")
    logger.info(f"Time: {elapsed:.0f}s ({elapsed/60:.1f} min)")

    # Per RE penetration level summary
    for pen in re_penetration_levels:
        mask = results_df["re_penetration"] == pen
        sub = results_df[mask]
        n_ok = sub["success"].sum()
        if n_ok > 0:
            ok = sub[sub["success"]]
            logger.info(
                f"  RE {pen:.0%}: {n_ok}/{len(sub)} success, "
                f"severity={ok['severity'].mean():.3f}+/-{ok['severity'].std():.3f}, "
                f"f_angle={ok['f_angle'].mean():.3f}, f_freq={ok['f_freq'].mean():.3f}, "
                f"f_voltage={ok['f_voltage'].mean():.3f}, "
                f"initial_flow={ok['initial_flow_MW'].mean():.1f} MW, "
                f"max_flow={ok['max_flow_MW'].mean():.1f} MW"
            )

    logger.info(f"Results saved to {output_dir}")


if __name__ == "__main__":
    main()
