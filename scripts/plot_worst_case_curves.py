"""Plot rotor angle and voltage curves for the most severe operating modes.

Runs dedicated ANDES simulations using the existing ANDESWrapper and extracts
full time-series from SimulationResult for the worst-case and a stable case.

Outputs: fig18_rotor_angle_curves.pdf, fig19_voltage_curves.pdf
"""
import io
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib import rcParams

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8")
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.simulator.andes_wrapper import ANDESWrapper, REDeviceConfig
from src.scenario.ieee39_mode_generator import IEEE39ModeGenerator, GENERATORS
import yaml

# CSEE journal style
rcParams['font.family'] = 'serif'
rcParams['font.size'] = 10
rcParams['axes.linewidth'] = 0.8
rcParams['figure.dpi'] = 300


def load_ieee39_config():
    config_path = Path(__file__).resolve().parents[1] / "configs" / "test_systems" / "ieee39.yaml"
    with open(config_path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def build_system_config(cfg):
    generators = []
    for g in cfg["generators"]:
        generators.append({
            "name": g["name"], "bus": g["bus"], "area": g["area"],
            "p_mw": g["p_mw"], "sn_mva": g["sn_mva"], "h_s": g["h_s"], "type": g["type"],
        })
    areas = {}
    for area_name, area_data in cfg["areas"].items():
        areas[area_name] = {
            "buses": area_data["buses"], "gen_buses": area_data["gen_buses"],
            "generators": area_data["generators"], "loads": area_data["loads"],
            "load_mw": area_data["load_mw"], "gen_mw": area_data["gen_mw"],
        }
    return {"generators": generators, "areas": areas}


def build_scenario(mode_row, fault_bus, clear_time_offset):
    """Build scenario dict from mode row parameters."""
    total_re_mw = float(mode_row["total_re_mw"])
    west_frac = float(mode_row["re_west_fraction"])
    west_dispatch = float(mode_row.get("re_dispatch_west", 0.7))
    east_dispatch = float(mode_row.get("re_dispatch_east", 0.7))

    re_placement = {
        "west": [{"bus": 4, "weight": 0.42}, {"bus": 8, "weight": 0.33}, {"bus": 6, "weight": 0.25}],
        "east": [{"bus": 20, "weight": 0.46}, {"bus": 16, "weight": 0.31}, {"bus": 28, "weight": 0.23}],
    }

    west_re_total = total_re_mw * west_frac
    east_re_total = total_re_mw * (1.0 - west_frac)
    devices = []
    for ri in re_placement["west"]:
        p = west_re_total * ri["weight"] * west_dispatch
        if p > 0.1:
            devices.append(REDeviceConfig(bus=ri["bus"], p_mw=round(p, 2)))
    for ri in re_placement["east"]:
        p = east_re_total * ri["weight"] * east_dispatch
        if p > 0.1:
            devices.append(REDeviceConfig(bus=ri["bus"], p_mw=round(p, 2)))

    gen_dispatch = int(mode_row.get("gen_dispatch", 0))
    west_re_mw = total_re_mw * west_frac
    east_re_mw = total_re_mw * (1.0 - west_frac)
    west_gen_base = sum(g["p_mw"] for g in GENERATORS["west"])
    east_gen_base = sum(g["p_mw"] for g in GENERATORS["east"])
    if gen_dispatch == 0: wb, eb = 1.0, 1.0
    elif gen_dispatch == 1: wb, eb = 1.08, 0.92
    elif gen_dispatch == 2: wb, eb = 0.92, 1.08
    else: wb, eb = 1.05, 1.05
    gen_scaling = {}
    for g in GENERATORS["west"]:
        gen_scaling[g["name"]] = max(0.3, wb * (1.0 - west_re_mw / west_gen_base))
    for g in GENERATORS["east"]:
        gen_scaling[g["name"]] = max(0.3, eb * (1.0 - east_re_mw / east_gen_base))

    return {
        "fault_bus": fault_bus,
        "fault_time": 1.0,
        "clear_time": 1.0 + clear_time_offset,
        "load_scaling": {"west": float(mode_row["load_level_west"]),
                         "east": float(mode_row["load_level_east"])},
        "gen_scaling": gen_scaling,
        "re_devices": devices if devices else None,
    }


GEN_NAMES = ["GENROU_1", "GENROU_2", "GENROU_3", "GENROU_4", "GENROU_5",
             "GENROU_6", "GENROU_7", "GENROU_8", "GENROU_9", "GENROU_10"]
WEST_GENS = {"GENROU_1", "GENROU_2", "GENROU_3", "GENROU_8", "GENROU_10"}
EAST_GENS = {"GENROU_4", "GENROU_5", "GENROU_6", "GENROU_7", "GENROU_9"}

# Key buses for voltage monitoring (fault bus + tie-line buses + load buses)
KEY_BUS_INDICES = [3, 5, 7, 13, 15, 19, 25, 27, 28]  # 0-based for Bus 4,6,8,14,16,20,26,28,29
KEY_BUS_NAMES = ["Bus 4", "Bus 6", "Bus 8", "Bus 14", "Bus 16",
                 "Bus 20", "Bus 26", "Bus 28", "Bus 29"]


def plot_rotor_angle_curves(results, labels, output_path):
    """Plot rotor angle swing curves (relative to COI) for multiple cases."""
    n_cases = len(results)
    fig, axes = plt.subplots(1, n_cases, figsize=(6 * n_cases, 5))
    if n_cases == 1:
        axes = [axes]

    for ax, result, label in zip(axes, results, labels):
        t = result.time_vector
        angles = result.rotor_angles  # (n_t, n_gen) in radians

        if angles is None or t is None:
            ax.text(0.5, 0.5, "No data", transform=ax.transAxes, ha='center')
            ax.set_title(label)
            continue

        # Compute COI angle
        angles_deg = np.rad2deg(angles)
        coi_angle = np.mean(angles_deg, axis=1, keepdims=True)
        relative_angles = angles_deg - coi_angle

        for i, name in enumerate(GEN_NAMES[:angles.shape[1]]):
            if name in WEST_GENS:
                ls, lw, alpha = "-", 1.3, 0.9
            else:
                ls, lw, alpha = "--", 1.3, 0.9
            ax.plot(t, relative_angles[:, i], ls, linewidth=lw, label=name, alpha=alpha)

        ax.axvline(x=1.0, color='red', linestyle=':', linewidth=1.2, alpha=0.7)
        ax.axhline(y=0, color='gray', linestyle='-', linewidth=0.4, alpha=0.3)
        ax.set_xlabel("Time (s)")
        ax.set_ylabel("Rotor Angle (deg, rel. to COI)")
        ax.set_title(label, fontsize=11, fontweight='bold')
        ax.legend(fontsize=7, ncol=2, loc='best')
        ax.grid(True, alpha=0.3)
        ax.set_xlim([0, min(15.0, max(t))])

    plt.tight_layout()
    plt.savefig(output_path, bbox_inches='tight', dpi=300)
    plt.close()
    print(f"Saved: {output_path}")


def plot_voltage_curves(results, labels, output_path):
    """Plot voltage recovery curves for key buses."""
    n_cases = len(results)
    fig, axes = plt.subplots(1, n_cases, figsize=(6 * n_cases, 5))
    if n_cases == 1:
        axes = [axes]

    for ax, result, label in zip(axes, results, labels):
        t = result.time_vector
        voltages = result.bus_voltages  # (n_t, n_bus) in p.u.

        if voltages is None or t is None:
            ax.text(0.5, 0.5, "No data", transform=ax.transAxes, ha='center')
            ax.set_title(label)
            continue

        for bus_idx, bus_name in zip(KEY_BUS_INDICES, KEY_BUS_NAMES):
            if bus_idx < voltages.shape[1]:
                ax.plot(t, voltages[:, bus_idx], linewidth=1.1, label=bus_name, alpha=0.85)

        ax.axhline(y=0.80, color='red', linestyle='--', linewidth=0.8, alpha=0.5)
        ax.axhline(y=0.90, color='orange', linestyle='--', linewidth=0.6, alpha=0.4)
        ax.axhline(y=1.0, color='gray', linestyle=':', linewidth=0.5, alpha=0.4)
        ax.axhline(y=1.10, color='red', linestyle='--', linewidth=0.8, alpha=0.5)
        ax.axvline(x=1.0, color='red', linestyle=':', linewidth=1.2, alpha=0.7)
        ax.set_xlabel("Time (s)")
        ax.set_ylabel("Voltage (p.u.)")
        ax.set_title(label, fontsize=11, fontweight='bold')
        ax.legend(fontsize=7, ncol=2, loc='best')
        ax.grid(True, alpha=0.3)
        ax.set_ylim([0.0, 1.3])
        ax.set_xlim([0, min(15.0, max(t))])

    plt.tight_layout()
    plt.savefig(output_path, bbox_inches='tight', dpi=300)
    plt.close()
    print(f"Saved: {output_path}")


def plot_freq_curves(results, labels, output_path):
    """Plot frequency deviation curves for all generators."""
    n_cases = len(results)
    fig, axes = plt.subplots(1, n_cases, figsize=(6 * n_cases, 5))
    if n_cases == 1:
        axes = [axes]

    for ax, result, label in zip(axes, results, labels):
        t = result.time_vector
        speeds = result.rotor_speeds  # (n_t, n_gen) in p.u.

        if speeds is None or t is None:
            ax.text(0.5, 0.5, "No data", transform=ax.transAxes, ha='center')
            ax.set_title(label)
            continue

        freq_hz = speeds * 60.0  # Convert to Hz

        for i, name in enumerate(GEN_NAMES[:speeds.shape[1]]):
            if name in WEST_GENS:
                ls, lw, alpha = "-", 1.3, 0.9
            else:
                ls, lw, alpha = "--", 1.3, 0.9
            ax.plot(t, freq_hz[:, i], ls, linewidth=lw, label=name, alpha=alpha)

        ax.axhline(y=60.0, color='gray', linestyle='-', linewidth=0.5, alpha=0.4)
        ax.axvline(x=1.0, color='red', linestyle=':', linewidth=1.2, alpha=0.7)
        ax.set_xlabel("Time (s)")
        ax.set_ylabel("Frequency (Hz)")
        ax.set_title(label, fontsize=11, fontweight='bold')
        ax.legend(fontsize=7, ncol=2, loc='best')
        ax.grid(True, alpha=0.3)
        ax.set_xlim([0, min(15.0, max(t))])

    plt.tight_layout()
    plt.savefig(output_path, bbox_inches='tight', dpi=300)
    plt.close()
    print(f"Saved: {output_path}")


def main():
    output_dir = Path("paper/figures")
    output_dir.mkdir(parents=True, exist_ok=True)

    cfg = load_ieee39_config()
    tie_lines = cfg["tie_lines"]
    system_config = build_system_config(cfg)

    wrapper = ANDESWrapper(
        case_path="ieee39/ieee39_full.xlsx",
        config={"tf": 15.0, "tstep": 0.02, "timeout": 120, "base_mva": 100.0},
        tie_lines=tie_lines,
        system_config=system_config,
    )

    checkpoint = pd.read_csv("data/processed/ieee39_re_sweep/ieee39_re_sweep_checkpoint.csv")
    mode_cols = ["re_penetration", "re_west_fraction", "re_dispatch_west", "re_dispatch_east",
                 "load_level_west", "load_level_east", "gen_dispatch",
                 "total_re_mw", "west_re_mw", "east_re_mw"]

    # === Case 1: Most severe (unstable) ===
    worst = checkpoint.loc[checkpoint["severity"].idxmax()]
    worst_mode = pd.Series({c: worst[c] for c in mode_cols})
    print(f"Worst: mode={worst['mode_idx']}, fault={worst['fault_name']}, sev={worst['severity']:.4f}")
    print(f"  RE={worst['re_penetration']:.0%}, west_frac={worst['re_west_fraction']:.3f}, "
          f"load_w={worst['load_level_west']:.3f}, load_e={worst['load_level_east']:.3f}")

    scenario_worst = build_scenario(worst_mode, fault_bus=16, clear_time_offset=0.25)
    result_worst = wrapper.evaluate(scenario_worst)
    print(f"  Result: success={result_worst.success}, stable={result_worst.stable}, "
          f"sev={result_worst.severity:.4f}")

    # === Case 2: Stable case for comparison (V_min > 0.8 to ensure truly stable) ===
    stable_cases = checkpoint[(checkpoint["stable"] == True) & (checkpoint["V_min"] > 0.8)]
    if len(stable_cases) == 0:
        stable_cases = checkpoint[(checkpoint["stable"] == True) & (checkpoint["V_min"] > 0.5)]
    if len(stable_cases) > 0:
        # Pick the highest-severity truly stable case
        best_stable = stable_cases.loc[stable_cases["severity"].idxmax()]
    else:
        best_stable = checkpoint.loc[checkpoint["severity"].idxmin()]

    stable_mode = pd.Series({c: best_stable[c] for c in mode_cols})
    print(f"\nStable: mode={best_stable['mode_idx']}, fault={best_stable['fault_name']}, "
          f"sev={best_stable['severity']:.4f}, V_min={best_stable['V_min']:.4f}")

    if pd.isna(best_stable["fault_bus"]):
        # gen_trip case
        scenario_stable = build_scenario(stable_mode, fault_bus=4, clear_time_offset=0.10)
        scenario_stable.pop("fault_bus", None)
        scenario_stable["gen_trip"] = "GENROU_4"
    else:
        fb_stable = int(best_stable["fault_bus"])
        ct_stable = float(best_stable["clear_time"])
        scenario_stable = build_scenario(stable_mode, fault_bus=fb_stable, clear_time_offset=ct_stable)
    result_stable = wrapper.evaluate(scenario_stable)
    print(f"  Result: success={result_stable.success}, stable={result_stable.stable}, "
          f"sev={result_stable.severity:.4f}")

    # === Plot rotor angle curves (relative to COI) ===
    label_w = f"(a) Unstable: Bus16 ct=0.25s (sev={worst['severity']:.3f})"
    label_s = f"(b) Stable: {best_stable['fault_name']} (sev={best_stable['severity']:.3f})"

    plot_rotor_angle_curves(
        [result_worst, result_stable],
        [label_w, label_s],
        output_dir / "fig18_rotor_angle_curves.pdf"
    )

    # === Plot voltage curves ===
    plot_voltage_curves(
        [result_worst, result_stable],
        [label_w, label_s],
        output_dir / "fig19_voltage_curves.pdf"
    )

    # === Plot frequency curves ===
    plot_freq_curves(
        [result_worst, result_stable],
        [label_w, label_s],
        output_dir / "fig20_frequency_curves.pdf"
    )

    # Print summary for paper
    print(f"\n=== Paper Summary ===")
    if result_worst.rotor_angles is not None:
        angles_w = np.rad2deg(result_worst.rotor_angles)
        max_spread = np.max(np.max(angles_w, axis=1) - np.min(angles_w, axis=1))
        print(f"Worst case: max angle spread = {max_spread:.1f} deg")
    if result_worst.bus_voltages is not None:
        vmin = np.min(result_worst.bus_voltages)
        print(f"Worst case: minimum voltage = {vmin:.4f} p.u.")
    if result_stable.rotor_angles is not None:
        angles_s = np.rad2deg(result_stable.rotor_angles)
        max_spread_s = np.max(np.max(angles_s, axis=1) - np.min(angles_s, axis=1))
        print(f"Stable case: max angle spread = {max_spread_s:.1f} deg")
    if result_stable.bus_voltages is not None:
        vmin_s = np.min(result_stable.bus_voltages)
        print(f"Stable case: minimum voltage = {vmin_s:.4f} p.u.")

    print("\nDone!")


if __name__ == "__main__":
    main()
