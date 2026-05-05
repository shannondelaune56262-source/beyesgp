"""RE scenario constraint dominance analysis.

Analyzes how different RE penetration levels change constraint dominance patterns:
- Per RE_level: f_angle/f_freq/f_voltage mean, std, range
- Per fault type: constraint contribution breakdown
- Entropy weight variation across RE levels
- Physical interpretation: inertia reduction → frequency activation,
  constant-power RE → voltage support degradation

Produces data for Figure 5 (box plots) and Figure 8 (entropy weight trends).
"""

import logging
import sys
import io
from pathlib import Path

import numpy as np
import pandas as pd

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8")
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s", datefmt="%H:%M:%S")
logger = logging.getLogger(__name__)


def compute_entropy_weights(values: np.ndarray) -> np.ndarray:
    """Compute entropy-based weights from a matrix of constraint values.

    values: shape (n_samples, n_constraints)
    Returns: weights of shape (n_constraints,)
    """
    n, m = values.shape
    weights = np.zeros(m)

    for j in range(m):
        col = values[:, j]
        col_range = col.max() - col.min()
        if col_range < 1e-10:
            weights[j] = 0.0
            continue

        # Normalize to [0, 1]
        normalized = (col - col.min()) / col_range

        # Entropy
        p = normalized / (normalized.sum() + 1e-10)
        p = np.clip(p, 1e-10, None)
        entropy = -np.sum(p * np.log(p)) / np.log(n)

        # Divergence
        weights[j] = 1.0 - entropy

    # Normalize weights
    total = weights.sum()
    if total > 0:
        weights /= total
    else:
        weights = np.ones(m) / m

    return weights


def main():
    output_dir = Path("data/processed/re_analysis")
    output_dir.mkdir(parents=True, exist_ok=True)

    sweep_path = "data/processed/re_sweep/re_sweep_results.csv"
    if not Path(sweep_path).exists():
        logger.error(f"RE sweep data not found at {sweep_path}")
        return

    df = pd.read_csv(sweep_path)
    df = df[df["success"] == True].copy()
    logger.info(f"Loaded {len(df)} successful simulations")

    constraint_cols = ["f_angle", "f_freq", "f_voltage"]
    mode_features = [
        "wind_area1_pct", "wind_area2_pct", "solar_area1_pct", "solar_area2_pct",
        "load_area1", "load_area2", "gen_dispatch_bias",
    ]

    # --- 1. Per RE-level constraint statistics ---
    logger.info("\n=== Per RE Level Constraint Statistics ===")
    re_stats = []

    for level in sorted(df["re_level"].unique()):
        sub = df[df["re_level"] == level]
        row = {"re_level": int(level), "n_samples": len(sub)}

        for col in constraint_cols:
            vals = sub[col].dropna().values
            if len(vals) > 0:
                row[f"{col}_mean"] = vals.mean()
                row[f"{col}_std"] = vals.std()
                row[f"{col}_min"] = vals.min()
                row[f"{col}_max"] = vals.max()
                row[f"{col}_range"] = vals.max() - vals.min()
            else:
                row[f"{col}_mean"] = float("nan")

        row["severity_mean"] = sub["severity"].mean()
        row["severity_std"] = sub["severity"].std()
        re_stats.append(row)

        logger.info(
            f"  RE Level {level} ({len(sub)} sims): "
            f"f_angle={row.get('f_angle_mean', 0):.3f}±{row.get('f_angle_std', 0):.3f}, "
            f"f_freq={row.get('f_freq_mean', 0):.3f}±{row.get('f_freq_std', 0):.3f}, "
            f"f_voltage={row.get('f_voltage_mean', 0):.3f}±{row.get('f_voltage_std', 0):.3f}"
        )

    re_stats_df = pd.DataFrame(re_stats)
    re_stats_df.to_csv(output_dir / "re_level_constraint_stats.csv", index=False)

    # --- 2. Per fault type constraint statistics ---
    logger.info("\n=== Per Fault Type Constraint Statistics ===")
    fault_stats = []

    for fault in df["fault_name"].unique():
        sub = df[df["fault_name"] == fault]
        row = {"fault_name": fault, "n_samples": len(sub)}

        for col in constraint_cols:
            vals = sub[col].dropna().values
            if len(vals) > 0:
                row[f"{col}_mean"] = vals.mean()
                row[f"{col}_std"] = vals.std()
                row[f"{col}_range"] = vals.max() - vals.min()

        fault_stats.append(row)

    fault_stats_df = pd.DataFrame(fault_stats)
    fault_stats_df.to_csv(output_dir / "fault_constraint_stats.csv", index=False)

    # --- 3. Entropy weights by RE level ---
    logger.info("\n=== Entropy Weights by RE Level ===")
    entropy_weights = []

    for level in sorted(df["re_level"].unique()):
        sub = df[df["re_level"] == level]
        vals = sub[constraint_cols].dropna().values

        if len(vals) > 5:
            weights = compute_entropy_weights(vals)
            entropy_weights.append({
                "re_level": int(level),
                "w_angle": weights[0],
                "w_freq": weights[1],
                "w_voltage": weights[2],
            })
            logger.info(f"  RE Level {level}: w_angle={weights[0]:.3f}, "
                        f"w_freq={weights[1]:.3f}, w_voltage={weights[2]:.3f}")

    if entropy_weights:
        ew_df = pd.DataFrame(entropy_weights)
        ew_df.to_csv(output_dir / "entropy_weights_by_re.csv", index=False)

    # --- 4. Cross-tabulation: RE_level x fault_type ---
    logger.info("\n=== Cross-tabulation: Severity by (RE_level, Fault) ===")
    cross_sev = df.pivot_table(
        values="severity",
        index="re_level",
        columns="fault_name",
        aggfunc="mean",
    )
    cross_sev.to_csv(output_dir / "severity_cross_table.csv")

    # --- 5. Constraint dominance classification ---
    logger.info("\n=== Constraint Dominance Analysis ===")
    for level in sorted(df["re_level"].unique()):
        sub = df[df["re_level"] == level]
        stds = {col: sub[col].std() for col in constraint_cols}
        dominant = max(stds, key=stds.get)
        total_std = sum(stds.values())

        logger.info(
            f"  RE Level {level}: dominant={dominant} (std={stds[dominant]:.4f}), "
            f"contribution={stds[dominant]/total_std*100:.1f}%"
        )
        logger.info(f"    std: angle={stds['f_angle']:.4f}, freq={stds['f_freq']:.4f}, "
                    f"voltage={stds['f_voltage']:.4f}")

    # --- 6. Identify constraint regime transitions ---
    logger.info("\n=== Constraint Regime Transitions ===")
    if len(re_stats) >= 2:
        # Check if voltage std increases with RE level
        voltage_stds = [r.get("f_voltage_std", 0) for r in re_stats]
        freq_stds = [r.get("f_freq_std", 0) for r in re_stats]
        angle_stds = [r.get("f_angle_std", 0) for r in re_stats]

        # Voltage variability trend
        if voltage_stds[-1] > 3 * voltage_stds[0] and voltage_stds[0] > 0:
            logger.info("  Voltage constraint variability increases >3x with RE penetration ✓")
        else:
            logger.info(f"  Voltage constraint variability: {voltage_stds[0]:.4f} → {voltage_stds[-1]:.4f} "
                        f"(ratio={voltage_stds[-1]/max(voltage_stds[0],1e-10):.1f}x)")

        # Frequency sensitivity
        if freq_stds[-1] > freq_stds[0] * 1.5:
            logger.info("  Frequency constraint becomes more variable with RE ✓")

    # --- 7. Box plot data export ---
    boxplot_data = df[["re_level", "fault_name"] + constraint_cols + ["severity"]].copy()
    boxplot_data.to_csv(output_dir / "boxplot_data.csv", index=False)

    logger.info(f"\nAll analysis results saved to {output_dir}")
    logger.info("=== RE Constraint Analysis Complete ===")


if __name__ == "__main__":
    main()
