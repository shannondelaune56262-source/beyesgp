"""Generate all paper figures from Round 3 experiment results."""
import json
import sys
import io

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import seaborn as sns
from pathlib import Path
from scipy.special import expit as sigmoid
from sklearn.cluster import KMeans
from sklearn.preprocessing import StandardScaler

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")

sns.set_style("whitegrid")
sns.set_context("paper", font_scale=1.2)
COLORS = sns.color_palette("deep")

output_dir = Path("data/figures")
output_dir.mkdir(parents=True, exist_ok=True)


def fig_gp_joint_scatter():
    with open("data/processed/gp_validation/gp_validation_joint.json") as f:
        gp = json.load(f)
    actual = np.array(gp["actual"])
    predicted = np.array(gp["predicted"])

    fig, ax = plt.subplots(figsize=(6, 6))
    ax.scatter(actual, predicted, alpha=0.3, s=10, c=COLORS[0])
    lims = [min(actual.min(), predicted.min()) - 0.02, max(actual.max(), predicted.max()) + 0.02]
    ax.plot(lims, lims, "k--", alpha=0.5, label="Perfect prediction")
    ax.set_xlabel("Actual Severity")
    ax.set_ylabel("GP Predicted Severity")
    ax.set_title(f"GP Surrogate: Joint 9D (R$^2$={gp['r2']:.3f})")
    ax.legend()
    ax.set_aspect("equal")
    fig.tight_layout()
    fig.savefig(output_dir / "fig_gp_joint_scatter.pdf", dpi=300, bbox_inches="tight")
    fig.savefig(output_dir / "fig_gp_joint_scatter.png", dpi=150, bbox_inches="tight")
    plt.close(fig)
    print("Saved fig_gp_joint_scatter")


def fig_gp_r2_comparison():
    with open("data/processed/gp_validation/gp_validation_joint.json") as f:
        gp_joint = json.load(f)
    with open("data/processed/gp_validation/gp_validation_mode_only.json") as f:
        gp_mode = json.load(f)

    targets = ["Severity", "f_angle", "f_voltage", "f_freq"]
    r2_mode = [
        gp_mode["r2"],
        gp_mode["constraint_r2"].get("f_angle", 0),
        gp_mode["constraint_r2"].get("f_voltage", 0),
        gp_mode["constraint_r2"].get("f_freq", 0),
    ]
    r2_joint = [
        gp_joint["r2"],
        gp_joint["constraint_r2"].get("f_angle", 0),
        gp_joint["constraint_r2"].get("f_voltage", 0),
        gp_joint["constraint_r2"].get("f_freq", 0),
    ]

    fig, ax = plt.subplots(figsize=(10, 5))
    x = np.arange(len(targets))
    width = 0.35
    ax.bar(x - width / 2, r2_mode, width, label="Mode-only (7D)", color=COLORS[1], alpha=0.8)
    bars2 = ax.bar(x + width / 2, r2_joint, width, label="Joint (9D)", color=COLORS[0], alpha=0.8)
    ax.set_xticks(x)
    ax.set_xticklabels(targets)
    ax.set_ylabel("R$^2$")
    ax.set_title("GP Surrogate Accuracy: Mode-only vs Joint Features")
    ax.legend()
    ax.axhline(y=0, color="gray", linewidth=0.5)
    for bar, val in zip(bars2, r2_joint):
        ax.text(
            bar.get_x() + bar.get_width() / 2, bar.get_height() + 0.02,
            f"{val:.2f}", ha="center", fontsize=8,
        )
    fig.tight_layout()
    fig.savefig(output_dir / "fig_gp_r2_comparison.pdf", dpi=300, bbox_inches="tight")
    fig.savefig(output_dir / "fig_gp_r2_comparison.png", dpi=150, bbox_inches="tight")
    plt.close(fig)
    print("Saved fig_gp_r2_comparison")


def fig_fault_severity_violin():
    df = pd.read_csv("data/processed/heterogeneous_fault_sweep/heterogeneous_fault_results.csv")
    fault_types = ["angle_dominated", "voltage_dominated", "freq_dominated", "severe_combined"]
    fault_labels = ["Angle\n(Bus 7)", "Voltage\n(Bus 9)", "Freq\n(Bus 2)", "Severe\n(Bus 7 ct=0.20)"]
    sev_cols = [f"{ft}_severity" for ft in fault_types]

    fig, ax = plt.subplots(figsize=(8, 5))
    data = [df[col].dropna().values for col in sev_cols]
    parts = ax.violinplot(data, positions=range(len(fault_types)), showmeans=True)
    for i, pc in enumerate(parts["bodies"]):
        pc.set_alpha(0.4)
        pc.set_facecolor(COLORS[i % len(COLORS)])
    ax.set_xticks(range(len(fault_types)))
    ax.set_xticklabels(fault_labels)
    ax.set_ylabel("Severity")
    ax.set_title("Severity Distribution by Fault Type")
    fig.tight_layout()
    fig.savefig(output_dir / "fig_fault_severity_violin.pdf", dpi=300, bbox_inches="tight")
    fig.savefig(output_dir / "fig_fault_severity_violin.png", dpi=150, bbox_inches="tight")
    plt.close(fig)
    print("Saved fig_fault_severity_violin")


def fig_worst_fault_distribution():
    df = pd.read_csv("data/processed/heterogeneous_fault_sweep/heterogeneous_fault_results.csv")
    wf = df["worst_fault"].value_counts()
    fault_order = [
        "severe_combined", "voltage_dominated", "angle_dominated",
        "voltage_dominated_v2", "freq_dominated", "angle_dominated_v2", "freq_dominated_v2",
    ]
    fault_short = [
        "Severe\n(Bus7,ct=0.20)", "Voltage\n(Bus9)", "Angle\n(Bus7)",
        "Voltage\n(Bus10)", "Freq\n(Bus2)", "Angle\n(Bus8)", "Freq\n(Bus4)",
    ]
    counts = [wf.get(f, 0) for f in fault_order]

    fig, ax = plt.subplots(figsize=(8, 5))
    bars = ax.bar(range(len(fault_order)), counts, color=COLORS[:7])
    ax.set_xticks(range(len(fault_order)))
    ax.set_xticklabels(fault_short, fontsize=8)
    ax.set_ylabel("Number of Modes")
    ax.set_title("Worst Fault Distribution (150 Modes)")
    for bar, cnt in zip(bars, counts):
        if cnt > 0:
            ax.text(bar.get_x() + bar.get_width() / 2, bar.get_height() + 1, str(cnt), ha="center", fontsize=9)
    fig.tight_layout()
    fig.savefig(output_dir / "fig_worst_fault_distribution.pdf", dpi=300, bbox_inches="tight")
    fig.savefig(output_dir / "fig_worst_fault_distribution.png", dpi=150, bbox_inches="tight")
    plt.close(fig)
    print("Saved fig_worst_fault_distribution")


def fig_tiered_limits_comparison():
    df = pd.read_csv("data/processed/heterogeneous_fault_sweep/heterogeneous_fault_results.csv")
    feature_cols = [
        "wind_area1_pct", "wind_area2_pct", "solar_area1_pct", "solar_area2_pct",
        "load_area1", "load_area2", "gen_dispatch_bias",
    ]
    X = df[feature_cols].values
    scaler = StandardScaler()
    X_scaled = scaler.fit_transform(X)
    km = KMeans(n_clusters=6, random_state=42, n_init=10)
    df["cluster"] = km.fit_predict(X_scaled)

    max_limit, min_limit = 400.0, 100.0

    def linear_limit(sev, margin=0.10):
        return max_limit - (max_limit - min_limit) * min(sev + margin, 1.0)

    def sigmoid_limit(sev, k=10, midpoint=0.7):
        return max_limit - (max_limit - min_limit) * sigmoid(k * (sev - midpoint))

    clusters = sorted(df["cluster"].unique())
    fig, ax = plt.subplots(figsize=(10, 5))
    x = np.arange(len(clusters))
    width = 0.25

    lin_vals = [linear_limit(df.loc[df["cluster"] == c, "angle_dominated_severity"].max()) for c in clusters]
    sig_vals = [sigmoid_limit(df.loc[df["cluster"] == c, "angle_dominated_severity"].max()) for c in clusters]
    pf_vals = [sigmoid_limit(df.loc[df["cluster"] == c, "voltage_dominated_severity"].max()) for c in clusters]

    ax.bar(x - width, lin_vals, width, label="Linear (bus 7)", color=COLORS[1], alpha=0.8)
    ax.bar(x, sig_vals, width, label="Sigmoid (bus 7)", color=COLORS[0], alpha=0.8)
    ax.bar(x + width, pf_vals, width, label="Sigmoid (bus 9)", color=COLORS[2], alpha=0.8)
    ax.axhline(y=100, color="red", linestyle="--", label="Uniform Limit")

    ax.set_xticks(x)
    ax.set_xticklabels([f"C{c}" for c in clusters])
    ax.set_xlabel("Cluster")
    ax.set_ylabel("Transfer Limit (MW)")
    ax.set_title("Tiered Limits: Linear vs Sigmoid vs Per-Fault")
    ax.legend()
    fig.tight_layout()
    fig.savefig(output_dir / "fig_tiered_limits_comparison.pdf", dpi=300, bbox_inches="tight")
    fig.savefig(output_dir / "fig_tiered_limits_comparison.png", dpi=150, bbox_inches="tight")
    plt.close(fig)
    print("Saved fig_tiered_limits_comparison")


if __name__ == "__main__":
    fig_gp_joint_scatter()
    fig_gp_r2_comparison()
    fig_fault_severity_violin()
    fig_worst_fault_distribution()
    fig_tiered_limits_comparison()
    print(f"\nAll figures saved to {output_dir}")
