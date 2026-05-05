"""Supplementary N-2/N-3 tie-line fault simulations.

Runs tie_line_n2_fault and tie_line_n3_fault for all 150 modes
and merges results into the existing heterogeneous_fault_results.csv.
"""

import logging
import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.simulator.andes_wrapper import ANDESWrapper
from src.objective.severity import SeverityCalculator

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s", datefmt="%H:%M:%S")
logger = logging.getLogger(__name__)

NEW_FAULTS = {
    "tie_line_n3_fault": {
        "fault_bus": 7, "clear_duration": 0.10,
        "line_trips": [
            {"line_idx": "Line_4", "time": 1.0},
            {"line_idx": "Line_5", "time": 1.0},
            {"line_idx": "Line_6", "time": 1.0},
        ],
        "description": "Bus 7-8 tie-line triple-circuit simultaneous fault (N-3)",
    },
    "tie_line_n2_fault": {
        "fault_bus": 7, "clear_duration": 0.10,
        "line_trips": [
            {"line_idx": "Line_4", "time": 1.0},
            {"line_idx": "Line_5", "time": 1.0},
        ],
        "description": "Bus 7-8 tie-line double-circuit simultaneous fault (N-2)",
    },
}


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
        "line_trips": fault_cfg.get("line_trips"),
    }


def main():
    results_path = Path("data/processed/heterogeneous_fault_sweep/heterogeneous_fault_results.csv")
    df = pd.read_csv(results_path)
    logger.info(f"Loaded {len(df)} existing rows")

    wrapper = ANDESWrapper(
        case_path="kundur/kundur_full.xlsx",
        config={"tf": 10.0, "tstep": 0.02, "timeout": 60},
    )
    calc = SeverityCalculator()

    total = len(df) * len(NEW_FAULTS)
    logger.info(f"Supplementary simulations: {len(df)} modes x {len(NEW_FAULTS)} faults = {total}")

    t_start = time.time()
    n_done = 0

    for fault_name, fault_cfg in NEW_FAULTS.items():
        sev_col = f"{fault_name}_severity"
        fa_col = f"{fault_name}_f_angle"
        ff_col = f"{fault_name}_f_freq"
        fv_col = f"{fault_name}_f_voltage"
        ok_col = f"{fault_name}_success"

        df[sev_col] = np.nan
        df[fa_col] = np.nan
        df[ff_col] = np.nan
        df[fv_col] = np.nan
        df[ok_col] = False

        for idx, row in df.iterrows():
            scenario = _build_scenario(row, fault_cfg)
            try:
                result = wrapper.evaluate(scenario)
                sev_info = calc.compute_with_breakdown(result)
                df.at[idx, sev_col] = sev_info.get("severity", np.nan)
                df.at[idx, fa_col] = sev_info.get("f_angle", np.nan)
                df.at[idx, ff_col] = sev_info.get("f_freq", np.nan)
                df.at[idx, fv_col] = sev_info.get("f_voltage", np.nan)
                df.at[idx, ok_col] = result.success
            except Exception as e:
                logger.warning(f"  [{idx}] {fault_name} failed: {e}")
                df.at[idx, sev_col] = 1.0
                df.at[idx, ok_col] = False

            n_done += 1
            if (n_done) % 50 == 0 or n_done == total:
                elapsed = time.time() - t_start
                rate = n_done / elapsed
                eta = (total - n_done) / rate
                logger.info(f"[{n_done}/{total}] rate={rate:.1f}/s ETA={eta/60:.0f}min")

    # Recompute max_severity and worst_fault including new faults
    all_fault_cols = [c for c in df.columns if c.endswith("_severity") and not c.startswith("max_")]
    for idx, row in df.iterrows():
        sevs = {c.replace("_severity", ""): row[c] for c in all_fault_cols if pd.notna(row[c])}
        if sevs:
            df.at[idx, "max_severity"] = max(sevs.values())
            df.at[idx, "worst_fault"] = max(sevs, key=sevs.get)

    # Save updated results
    df.to_csv(results_path, index=False)
    logger.info(f"Saved {len(df)} rows with N-2/N-3 results to {results_path}")

    # Statistics
    for fault_name in NEW_FAULTS:
        col = f"{fault_name}_severity"
        ok = df[col].dropna()
        logger.info(f"  {fault_name}: mean={ok.mean():.3f}, std={ok.std():.3f}, "
                    f"min={ok.min():.3f}, max={ok.max():.3f}")

    logger.info(f"\nWorst fault distribution (updated):")
    print(df["worst_fault"].value_counts().to_string())


if __name__ == "__main__":
    main()
