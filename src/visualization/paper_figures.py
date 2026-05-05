"""Publication-quality figure generation for the full analysis pipeline.

Generates: clustering scatter plots, BO efficiency comparison, tiered limits,
GP prediction scatter, dimension-efficiency plots.
"""

import json
import logging
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import seaborn as sns

logger = logging.getLogger(__name__)

sns.set_style("whitegrid")
sns.set_context("paper", font_scale=1.2)
COLORS = sns.color_palette("deep")


def generate_all_figures(results_dir: str, output_dir: str = "data/figures"):
    """Generate all paper figures from saved experiment results."""
    results_path = Path(results_dir)
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)

    # Check for mode analysis results
    analysis_csv = Path("data/processed/mode_analysis/mode_analysis_full.csv")
    if analysis_csv.exists():
        df = pd.read_csv(analysis_csv, index_col=0)
        plot_clustering_scatter(df, output_path / "fig1_clustering_pca.pdf")
        plot_severity_distribution(df, output_path / "fig2_severity_by_cluster.pdf")

    # Check for tiered limits
    limits_csv = Path("data/processed/mode_analysis/tiered_limits.csv")
    if limits_csv.exists():
        limits_df = pd.read_csv(limits_csv)
        plot_tiered_limits(limits_df, output_path / "fig3_tiered_limits.pdf")

    # BO convergence from experiment results
    for exp_dir in sorted(results_path.iterdir()):
        if not exp_dir.is_dir():
            continue
        exp_name = exp_dir.name
        convergence_data = _load_convergence_data(exp_dir)
        if convergence_data:
            plot_convergence_curves(
                convergence_data,
                output_path / f"{exp_name}_convergence.pdf",
                title=f"Convergence: {exp_name}",
            )

    # GP prediction scatter
    for exp_dir in sorted(results_path.iterdir()):
        gp_file = exp_dir / "gp_validation.json"
        if gp_file.exists():
            with open(gp_file) as f:
                gp_data = json.load(f)
            plot_gp_scatter(gp_data, output_path / "fig_gp_scatter.pdf")

    logger.info(f"All figures saved to: {output_path}")


def _load_convergence_data(exp_dir: Path) -> dict:
    """Load convergence curves from experiment directory."""
    data = {}
    for method_dir in sorted(exp_dir.iterdir()):
        if not method_dir.is_dir():
            continue
        curves = []
        for seed_dir in sorted(method_dir.iterdir()):
            result_file = seed_dir / "result.json"
            if result_file.exists():
                with open(result_file) as f:
                    result = json.load(f)
                curves.append(result["convergence"])
        if curves:
            data[method_dir.name] = curves
    return data


def plot_clustering_scatter(df: pd.DataFrame, output_path: Path):
    """PCA 2D scatter plot colored by cluster, marking boundary points."""
    if "PC1" not in df.columns or "PC2" not in df.columns:
        logger.warning("No PCA columns, skipping clustering scatter")
        return

    fig, ax = plt.subplots(figsize=(8, 6))

    # Plot clusters
    clusters = sorted(df["cluster"].unique())
    for i, c in enumerate(clusters):
        mask = df["cluster"] == c
        ax.scatter(
            df.loc[mask, "PC1"], df.loc[mask, "PC2"],
            c=[COLORS[i % len(COLORS)]],
            alpha=0.5, s=20, label=f"Cluster {c}",
        )

    # Mark boundary points
    boundary = df[df["is_boundary"] == True]
    if len(boundary) > 0:
        ax.scatter(
            boundary["PC1"], boundary["PC2"],
            facecolors="none", edgecolors="red", s=40,
            linewidths=0.8, label="Boundary",
        )

    ax.set_xlabel("PC1")
    ax.set_ylabel("PC2")
    ax.set_title("Operating Mode Clustering (PCA Projection)")
    ax.legend(loc="best", fontsize=8)
    fig.tight_layout()
    fig.savefig(output_path, dpi=300, bbox_inches="tight")
    plt.close(fig)
    logger.info(f"Saved: {output_path}")


def plot_severity_distribution(df: pd.DataFrame, output_path: Path):
    """Severity distribution by cluster (box + violin plot)."""
    if "cluster" not in df.columns or "severity" not in df.columns:
        return

    fig, ax = plt.subplots(figsize=(8, 5))
    clusters = sorted(df["cluster"].unique())
    data_by_cluster = [df.loc[df["cluster"] == c, "severity"].dropna().values for c in clusters]

    parts = ax.violinplot(data_by_cluster, positions=range(len(clusters)), showmeans=True)
    for pc in parts["bodies"]:
        pc.set_alpha(0.3)

    ax.set_xticks(range(len(clusters)))
    ax.set_xticklabels([f"C{c}" for c in clusters])
    ax.set_xlabel("Cluster")
    ax.set_ylabel("Severity")
    ax.set_title("Severity Distribution by Cluster")
    fig.tight_layout()
    fig.savefig(output_path, dpi=300, bbox_inches="tight")
    plt.close(fig)
    logger.info(f"Saved: {output_path}")


def plot_tiered_limits(limits_df: pd.DataFrame, output_path: Path):
    """Tiered limits vs uniform limit bar chart."""
    fig, ax = plt.subplots(figsize=(8, 5))

    x = np.arange(len(limits_df))
    width = 0.35

    bars1 = ax.bar(x - width/2, limits_df["transfer_limit_mw"], width,
                    label="Tiered Limit", color=COLORS[0])
    bars2 = ax.bar(x + width/2, limits_df["uniform_limit_mw"], width,
                    label="Uniform Limit", color=COLORS[1], alpha=0.7)

    ax.set_xticks(x)
    ax.set_xticklabels([f"C{int(c)}" for c in limits_df["cluster_id"]])
    ax.set_xlabel("Cluster")
    ax.set_ylabel("Transfer Limit (MW)")
    ax.set_title("Tiered vs Uniform Safety Limits")
    ax.legend()

    for bar, pct in zip(bars1, limits_df["improvement_pct"]):
        if pct > 0:
            ax.text(bar.get_x() + bar.get_width()/2, bar.get_height() + 2,
                    f"+{pct:.1f}%", ha="center", fontsize=8, color="green")

    fig.tight_layout()
    fig.savefig(output_path, dpi=300, bbox_inches="tight")
    plt.close(fig)
    logger.info(f"Saved: {output_path}")


def plot_convergence_curves(
    results_by_method: dict[str, list],
    output_path: Path,
    title: str = "Convergence Comparison",
):
    """BO convergence curves: mean ± std for each method."""
    fig, ax = plt.subplots(figsize=(7, 4.5))

    for i, (method, curves) in enumerate(results_by_method.items()):
        curves = np.array(curves)
        mean = np.mean(curves, axis=0)
        std = np.std(curves, axis=0)
        x = np.arange(1, len(mean) + 1)

        ax.plot(x, mean, label=method.upper(), linewidth=1.5, color=COLORS[i % len(COLORS)])
        ax.fill_between(x, mean - std, mean + std, alpha=0.15, color=COLORS[i % len(COLORS)])

    ax.set_xlabel("Number of Evaluations")
    ax.set_ylabel("Best Severity Found")
    ax.set_title(title)
    ax.legend(loc="lower right")
    ax.set_xlim(left=1)

    fig.tight_layout()
    fig.savefig(output_path, dpi=300, bbox_inches="tight")
    plt.close(fig)
    logger.info(f"Saved: {output_path}")


def plot_gp_scatter(gp_data: dict, output_path: Path):
    """GP prediction vs actual severity scatter plot."""
    actual = np.array(gp_data["actual"])
    predicted = np.array(gp_data["predicted"])

    fig, ax = plt.subplots(figsize=(6, 6))
    ax.scatter(actual, predicted, alpha=0.5, s=15)

    lims = [min(actual.min(), predicted.min()), max(actual.max(), predicted.max())]
    ax.plot(lims, lims, "k--", alpha=0.5, label="Perfect prediction")

    ax.set_xlabel("Actual Severity")
    ax.set_ylabel("GP Predicted Severity")
    ax.set_title(f"GP Surrogate Accuracy (R²={gp_data.get('r2', 0):.3f})")
    ax.legend()
    ax.set_aspect("equal")

    fig.tight_layout()
    fig.savefig(output_path, dpi=300, bbox_inches="tight")
    plt.close(fig)
    logger.info(f"Saved: {output_path}")


def plot_dimension_efficiency(dim_results: dict, output_path: Path):
    """BO efficiency vs dimensionality plot."""
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(12, 5))

    dims = sorted(dim_results.keys())

    # Left: BO best severity by dimension
    for method in ["bo", "random", "lhs", "ga"]:
        vals = [dim_results[d].get(method, {}).get("best_severity", 0) for d in dims]
        ax1.plot(dims, vals, marker="o", label=method.upper())

    ax1.set_xlabel("Dimension")
    ax1.set_ylabel("Best Severity Found")
    ax1.set_title("Best Severity vs Dimension")
    ax1.legend()

    # Right: BO efficiency (evals to reach 90% of best)
    for method in ["bo", "random", "lhs", "ga"]:
        vals = [dim_results[d].get(method, {}).get("evals_90pct", np.nan) for d in dims]
        ax2.plot(dims, vals, marker="s", label=method.upper())

    ax2.set_xlabel("Dimension")
    ax2.set_ylabel("Evaluations to 90% of Best")
    ax2.set_title("Sampling Efficiency vs Dimension")
    ax2.legend()

    fig.tight_layout()
    fig.savefig(output_path, dpi=300, bbox_inches="tight")
    plt.close(fig)
    logger.info(f"Saved: {output_path}")


def plot_binding_constraint_map(df: pd.DataFrame, output_path: Path):
    """PCA scatter plot colored by binding constraint type per cluster."""
    if "PC1" not in df.columns or "cluster" not in df.columns:
        logger.warning("Missing PCA or cluster columns")
        return

    fig, ax = plt.subplots(figsize=(8, 6))

    constraint_colors = {"angle": COLORS[0], "voltage": COLORS[1], "freq": COLORS[2]}
    clusters = sorted(df["cluster"].unique())

    for c in clusters:
        mask = df["cluster"] == c
        if "binding_constraint" in df.columns:
            bc = df.loc[mask, "binding_constraint"].iloc[0] if mask.sum() > 0 else "angle"
        else:
            bc = "angle"
        color = constraint_colors.get(bc, COLORS[3])
        ax.scatter(
            df.loc[mask, "PC1"], df.loc[mask, "PC2"],
            c=[color], alpha=0.5, s=20, label=f"C{c} ({bc})",
        )

    ax.set_xlabel("PC1")
    ax.set_ylabel("PC2")
    ax.set_title("Binding Constraint per Cluster")
    ax.legend(loc="best", fontsize=8)
    fig.tight_layout()
    fig.savefig(output_path, dpi=300, bbox_inches="tight")
    plt.close(fig)
    logger.info(f"Saved: {output_path}")


def plot_per_constraint_limits(limits_df: pd.DataFrame, output_path: Path):
    """Grouped bar chart: per-constraint limits per cluster."""
    fig, ax = plt.subplots(figsize=(10, 5))

    x = np.arange(len(limits_df))
    width = 0.2

    if "limit_angle_mw" in limits_df.columns:
        ax.bar(x - 1.5*width, limits_df["limit_angle_mw"], width,
               label="Angle Limit", color=COLORS[0], alpha=0.8)
    if "limit_voltage_mw" in limits_df.columns:
        ax.bar(x - 0.5*width, limits_df["limit_voltage_mw"], width,
               label="Voltage Limit", color=COLORS[1], alpha=0.8)
    if "limit_freq_mw" in limits_df.columns:
        ax.bar(x + 0.5*width, limits_df["limit_freq_mw"], width,
               label="Freq Limit", color=COLORS[2], alpha=0.8)
    if "uniform_limit_mw" in limits_df.columns:
        ax.axhline(y=limits_df["uniform_limit_mw"].iloc[0], color="red",
                   linestyle="--", label="Uniform Limit")

    ax.set_xticks(x)
    ax.set_xticklabels([f"C{int(c)}" for c in limits_df["cluster_id"]])
    ax.set_xlabel("Cluster")
    ax.set_ylabel("Transfer Limit (MW)")
    ax.set_title("Per-Constraint Transfer Limits by Cluster")
    ax.legend()
    fig.tight_layout()
    fig.savefig(output_path, dpi=300, bbox_inches="tight")
    plt.close(fig)
    logger.info(f"Saved: {output_path}")
