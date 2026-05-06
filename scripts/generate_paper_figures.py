"""Generate all paper figures for CSEE journal submission.

Produces:
- Figure 3: MOGP R² comparison (bar chart)
- Figure 4: BO convergence curves
- Figure 5: RE impact on constraints (box plots)
- Figure 6: AIA boundary 2D projection with severity heatmap
- Figure 7: Transfer limit comparison (bar chart)
- Figure 8: Closed-loop volume convergence

All figures use CSEE format: bilingual titles, 300dpi PDF output.
"""

import logging
import sys
import io
import json
from pathlib import Path

import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.colors import LinearSegmentedColormap
from matplotlib.collections import LineCollection

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8")
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s", datefmt="%H:%M:%S")
logger = logging.getLogger(__name__)

from src.visualization.style_config import (
    apply_csee_style, PALETTE, CLUSTER_COLORS, save_figure,
    SAFETY_CMAP_COLORS, FIGURE_DIR,
)

apply_csee_style()

OUTPUT_DIR = FIGURE_DIR
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)


def fig3_mogp_r2():
    """Figure 3: MOGP R² comparison across feature sets."""
    path = "data/processed/mogp_validation/mogp_comparison.csv"
    if not Path(path).exists():
        logger.warning(f"Missing data for Figure 3: {path}")
        return

    df = pd.read_csv(path)
    outputs = ["f_angle", "f_freq", "f_voltage", "severity"]
    output_labels_cn = ["功角指标", "频率指标", "电压指标", "综合严重度"]
    output_labels_en = ["Angle Index", "Freq Index", "Voltage Index", "Severity"]

    fig, axes = plt.subplots(1, 4, figsize=(14, 3.5), sharey=True)

    for idx, (out, cn, en) in enumerate(zip(outputs, output_labels_cn, output_labels_en)):
        ax = axes[idx]
        col = f"{out}_r2_mean"
        col_std = f"{out}_r2_std"

        if col not in df.columns:
            continue

        x = np.arange(len(df))
        bars = ax.bar(x, df[col], yerr=df.get(col_std, 0), capsize=3,
                      color=["#2196F3", "#4CAF50", "#FF9800"][:len(df)],
                      alpha=0.8, edgecolor="black", linewidth=0.5)

        # Add value labels
        for bar, val in zip(bars, df[col]):
            if not np.isnan(val):
                ax.text(bar.get_x() + bar.get_width()/2, bar.get_height() + 0.02,
                        f"{val:.3f}", ha="center", va="bottom", fontsize=6)

        ax.set_xticks(x)
        ax.set_xticklabels(df["feature_set"], rotation=30, ha="right", fontsize=7)
        ax.set_ylabel("R²" if idx == 0 else "")
        ax.set_ylim(0, 1.15)
        ax.axhline(y=0.7, color="red", linestyle="--", linewidth=0.5, alpha=0.5, label="R²=0.7")
        ax.set_title(f"{cn}\n({en})", fontsize=8)
    plt.tight_layout()
    save_figure(fig, "fig7_gp_r2")
    plt.close(fig)
    logger.info("Figure 3 saved")


def fig4_bo_convergence():
    """Figure 4: BO convergence curves comparison."""
    path = "data/processed/boundary_exploration/convergence_comparison.csv"
    if not Path(path).exists():
        logger.warning(f"Missing data for Figure 4: {path}")
        return

    df = pd.read_csv(path)

    fig, ax = plt.subplots(figsize=(7, 4.5))
    colors = {"BO": PALETTE["bo"], "Random": PALETTE["random"], "LHS": PALETTE["lhs"]}
    labels = {"BO": "贝叶斯优化(BO)", "Random": "随机搜索(Random)", "LHS": "拉丁超立方(LHS)"}

    for method in ["BO", "Random", "LHS"]:
        sub = df[df["method"] == method]
        if sub.empty:
            continue

        grouped = sub.groupby("step")["best_distance_to_threshold"]
        mean = grouped.mean()
        std = grouped.std().fillna(0)
        steps = mean.index

        ax.plot(steps, mean, label=labels.get(method, method),
                color=colors.get(method, "gray"), linewidth=1.5, marker="o", markersize=3)
        ax.fill_between(steps, mean - std, mean + std,
                        color=colors.get(method, "gray"), alpha=0.15)

    ax.set_xlabel("评估次数 / Evaluations", fontsize=9)
    ax.set_ylabel("与阈值的最佳距离 / Best distance to threshold", fontsize=9)
    ax.legend(fontsize=8)
    ax.grid(True, alpha=0.3)
    # title removed — figure name goes in paper caption below figure
    plt.tight_layout()
    save_figure(fig, "fig8_bo_convergence")
    plt.close(fig)
    logger.info("Figure 4 saved")


def fig5_re_impact():
    """Figure 5: RE penetration impact on constraints (box plots)."""
    # Use raw sweep data directly for box plots
    sweep_path = "data/processed/re_sweep/re_sweep_results.csv"
    if not Path(sweep_path).exists():
        logger.warning(f"Missing data for Figure 5: {sweep_path}")
        return

    df = pd.read_csv(sweep_path)
    df = df[df["success"] == True].copy()

    # Map RE device count to level
    from src.scenario.mode_generator import RE_LEVEL_MAP
    if "re_level" not in df.columns:
        if "n_re_devices" in df.columns:
            df["re_level"] = df["n_re_devices"].map(RE_LEVEL_MAP)
        else:
            df["re_level"] = 0

    fig, axes = plt.subplots(1, 3, figsize=(12, 4.5))
    constraints = ["f_angle", "f_freq", "f_voltage"]
    titles_cn = ["功角严重度", "频率严重度", "电压严重度"]
    titles_en = ["Angle severity", "Frequency severity", "Voltage severity"]

    levels = sorted(df["re_level"].dropna().unique())

    for idx, (col, cn, en) in enumerate(zip(constraints, titles_cn, titles_en)):
        ax = axes[idx]
        data_by_level = [df[df["re_level"] == level][col].dropna().values for level in levels]

        bp = ax.boxplot(data_by_level,
                        labels=[f"L{int(level)}" for level in levels],
                        patch_artist=True, showfliers=False)

        colors = ["#E8F5E9", "#C8E6C9", "#A5D6A7", "#81C784", "#66BB6A"]
        for i, patch in enumerate(bp["boxes"]):
            patch.set_facecolor(colors[i % len(colors)])

        ax.set_xlabel("RE渗透率等级 / RE Level")
        ax.set_ylabel("严重度 / Severity")
        ax.set_title(f"{cn}\n({en})", fontsize=8)
        ax.grid(True, axis="y", alpha=0.3)

    # title removed — figure name goes in paper caption below figure
    plt.tight_layout()
    save_figure(fig, "fig4_re_impact")
    plt.close(fig)
    logger.info("Figure 5 saved")


def fig6_aia_boundary():
    """Figure 6: AIA boundary with severity heatmap background."""
    heatmap_path = "data/processed/aia_boundaries/severity_heatmap.csv"
    proj_path = "data/processed/aia_boundaries/boundary_2d_projection.csv"
    contour_path = "data/processed/aia_boundaries/boundary_contours.json"

    if not Path(heatmap_path).exists() or not Path(proj_path).exists():
        logger.warning(f"Missing data for Figure 6")
        return

    hm_df = pd.read_csv(heatmap_path)
    proj_df = pd.read_csv(proj_path)

    fig, ax = plt.subplots(figsize=(8, 6))

    # Draw severity heatmap
    n_grid = int(np.sqrt(len(hm_df)))
    severity_grid = hm_df["predicted_severity"].values.reshape(n_grid, n_grid)
    g0 = hm_df["dim0"].values.reshape(n_grid, n_grid)
    g1 = hm_df["dim1"].values.reshape(n_grid, n_grid)

    # Custom colormap: blue (safe) → yellow (boundary) → red (unsafe)
    cmap = LinearSegmentedColormap.from_list("safety", SAFETY_CMAP_COLORS)
    # Use wider range so color gradient is visible despite narrow data range
    vmin = min(0.4, severity_grid.min() - 0.05)
    vmax = max(1.0, severity_grid.max() + 0.05)
    pcm = ax.pcolormesh(g0, g1, severity_grid, cmap=cmap, shading="auto",
                        vmin=vmin, vmax=vmax, zorder=0)
    cbar = plt.colorbar(pcm, ax=ax, label="预测严重度 / Predicted severity", shrink=0.8)

    # Draw boundary contour (threshold line)
    ax.contour(g0, g1, severity_grid, levels=[0.6], colors="black",
               linewidths=2, linestyles="-")

    # Draw AIA boundary contours
    if Path(contour_path).exists():
        with open(contour_path, encoding="utf-8") as f:
            contours = json.load(f)
        # Draw first few contours
        drawn = 0
        for key, data in contours.items():
            if drawn >= 3:
                break
            mask = np.array(data["contour_mask"]).reshape(data["n_grid"], data["n_grid"])
            # Find boundary of the contour mask
            ax.contour(g0, g1, mask.astype(float), levels=[0.5],
                       colors=["#2E7D32"], linewidths=1.5, linestyles="--")
            drawn += 1

    # Scatter data points - safe points first (larger, brighter) so they are visible
    safe = proj_df[proj_df["label"] == "safe"]
    unsafe = proj_df[proj_df["label"] == "unsafe"]
    ax.scatter(unsafe["dim0"], unsafe["dim1"], c=PALETTE["unsafe"], s=12, alpha=0.5,
               edgecolors="white", linewidths=0.3, label="不安全 / Unsafe", zorder=4)
    ax.scatter(safe["dim0"], safe["dim1"], c=PALETTE["safe"], s=25, alpha=0.85,
               edgecolors="#1B5E20", linewidths=0.6, marker="o", label="安全 / Safe", zorder=5)

    ax.set_xlabel("风电占比区域1 / wind_area1_pct", fontsize=9)
    ax.set_ylabel("风电占比区域2 / wind_area2_pct", fontsize=9)
    ax.legend(fontsize=7, loc="upper left")
    # title removed — figure name goes in paper caption below figure
    plt.tight_layout()
    save_figure(fig, "fig9_aia_boundary")
    plt.close(fig)
    logger.info("Figure 6 saved")


def fig7_transfer_limits():
    """Figure 7: Transfer limit comparison across methods."""
    path = "data/processed/transfer_limits/transfer_limits_comparison.csv"
    if not Path(path).exists():
        logger.warning(f"Missing data for Figure 7: {path}")
        return

    df = pd.read_csv(path)
    methods = ["uniform", "linear", "sigmoid", "aia"]
    method_labels = ["统一限额\nUniform", "线性聚类\nLinear", "Sigmoid聚类\nSigmoid", "AIA边界\nAIA"]
    method_colors = [PALETTE["uniform"], PALETTE["linear"], PALETTE["sigmoid"], PALETTE["aia"]]

    fig, ax = plt.subplots(figsize=(8, 5))

    x = np.arange(len(df))
    width = 0.18
    offsets = np.arange(len(methods)) - (len(methods) - 1) / 2

    for i, (method, label, color) in enumerate(zip(methods, method_labels, method_colors)):
        col = f"{method}_limit"
        if col not in df.columns:
            continue
        bars = ax.bar(x + offsets[i] * width, df[col], width,
                      label=label, color=color, alpha=0.85, edgecolor="black", linewidth=0.3)

    ax.set_xlabel("聚类编号 / Cluster ID", fontsize=9)
    ax.set_ylabel("传输容量限额 / Transfer limit (p.u.)", fontsize=9)
    ax.set_xticks(x)
    ax.set_xticklabels([f"C{c}" for c in df["cluster_id"]])
    # Auto-scale y-axis to fit all data
    ymax = max(df[[f"{m}_limit" for m in methods if f"{m}_limit" in df.columns]].max().max() * 1.15, 1.0)
    ax.set_ylim(0, ymax)
    ax.legend(fontsize=7, ncol=2, loc="upper left")
    ax.grid(True, axis="y", alpha=0.3)
    # title removed — figure name goes in paper caption below figure
    plt.tight_layout()
    save_figure(fig, "fig11_tiered_limits")
    plt.close(fig)
    logger.info("Figure 7 saved")


def fig10_closed_loop():
    """Figure 8: Closed-loop volume convergence."""
    path = "data/processed/closed_loop/closed_loop_results.csv"
    if not Path(path).exists():
        logger.warning(f"Missing data for Figure 8: {path}")
        return

    df = pd.read_csv(path)

    fig, axes = plt.subplots(1, 2, figsize=(12, 5))

    # Left panel: Normalized volume growth ratio (relative to round 1)
    ax = axes[0]
    cmap = CLUSTER_COLORS

    for i, ((fault, cluster), group) in enumerate(
        df.groupby(["fault_name", "cluster_id"])
    ):
        label = f"{fault.replace('_', ' ')} / C{cluster}"
        vols = group["volume"].values
        rounds = group["round"].values
        if vols[0] > 1e-10:
            ratio = vols / vols[0] * 100  # percentage of initial volume
        else:
            ratio = np.ones_like(vols) * 100
        ax.plot(rounds, ratio, marker="o", label=label,
                linewidth=1.5, color=cmap[i % len(cmap)], markersize=4)

    ax.set_xlabel("迭代轮次 / Iteration round", fontsize=9)
    ax.set_ylabel("相对体积 / Relative volume (% of Round 1)", fontsize=9)
    ax.legend(fontsize=6, ncol=2)
    ax.grid(True, alpha=0.3)
    ax.axhline(y=100, color="gray", linestyle="--", linewidth=0.5)
    ax.set_title("(a)", fontsize=9)

    # Right panel: Volume change percentage (bar chart)
    ax2 = axes[1]
    scenarios = []
    changes = []
    for (fault, cluster), group in df.groupby(["fault_name", "cluster_id"]):
        vols = group["volume"].values
        if len(vols) > 0 and vols[0] > 0:
            change = (vols[-1] - vols[0]) / vols[0] * 100
            scenarios.append(f"{fault[:6]}\nC{cluster}")
            changes.append(change)

    if scenarios:
        colors_bar = [PALETTE["safe"] if c >= 0 else PALETTE["unsafe"] for c in changes]
        bars = ax2.bar(range(len(scenarios)), changes, color=colors_bar,
                       alpha=0.8, edgecolor="black", linewidth=0.3)
        ax2.set_xticks(range(len(scenarios)))
        ax2.set_xticklabels(scenarios, fontsize=6)
        ax2.axhline(y=0, color="black", linewidth=0.5)
        ax2.set_ylabel("体积变化率 / Volume change (%)", fontsize=9)

    ax2.grid(True, axis="y", alpha=0.3)
    ax2.set_title("(b)", fontsize=9)

    # title removed — figure name goes in paper caption below figure
    plt.tight_layout()
    save_figure(fig, "fig10_closed_loop")
    plt.close(fig)
    logger.info("Figure 8 saved")


def fig9_parallel_coordinates():
    """图3: 8维参数平行坐标图，按聚类着色"""
    path = "data/processed/mode_analysis/mode_analysis_full.csv"
    if not Path(path).exists():
        logger.warning(f"Missing data for Figure 9: {path}")
        return

    df = pd.read_csv(path, index_col=0)

    dims = [
        ("wind_area1_pct",   "$w_1$",   "$w_1$\n风电占比A1"),
        ("wind_area2_pct",   "$w_2$",   "$w_2$\n风电占比A2"),
        ("solar_area1_pct",  "$s_1$",   "$s_1$\n光伏占比A1"),
        ("solar_area2_pct",  "$s_2$",   "$s_2$\n光伏占比A2"),
        ("load_area1",       "$l_1$",   "$l_1$\n负荷水平A1"),
        ("load_area2",       "$l_2$",   "$l_2$\n负荷水平A2"),
        ("gen_dispatch_bias", "$\\delta$", "$\\delta$\n出力偏差"),
        ("total_re_pct",     "$r$",     "$r$\n总渗透率"),
    ]

    # Normalize each dimension to [0, 1] for display
    col_names = [d[0] for d in dims]
    df_plot = df[col_names + ["cluster"]].copy()
    ranges = {}
    for col in col_names:
        vmin, vmax = df_plot[col].min(), df_plot[col].max()
        ranges[col] = (vmin, vmax)
        if vmax > vmin:
            df_plot[col + "_norm"] = (df_plot[col] - vmin) / (vmax - vmin)
        else:
            df_plot[col + "_norm"] = 0.5

    norm_cols = [c + "_norm" for c in col_names]
    clusters = sorted(df_plot["cluster"].unique())
    cmap = CLUSTER_COLORS

    fig, ax = plt.subplots(figsize=(14, 5))

    # Draw each line colored by cluster (LineCollection for efficiency)
    x_vals = np.arange(len(dims))
    for c in clusters:
        sub = df_plot[df_plot["cluster"] == c]
        color = cmap[c % len(cmap)]
        segments = []
        for _, row in sub.iterrows():
            y_vals = [row[nc] for nc in norm_cols]
            segments.append(np.column_stack([x_vals, y_vals]))
        lc = LineCollection(segments, colors=[color] * len(segments),
                            alpha=0.25, linewidths=0.8)
        ax.add_collection(lc)

    # Overlay cluster means with thicker lines
    for c in clusters:
        sub = df_plot[df_plot["cluster"] == c]
        means = [sub[nc].mean() for nc in norm_cols]
        color = cmap[c % len(cmap)]
        ax.plot(range(len(dims)), means, color=color, linewidth=2.5, marker="o",
                markersize=5, label=f"C{c} (n={len(sub)})", zorder=10)

    # Custom x-axis labels and ticks
    ax.set_xticks(range(len(dims)))
    ax.set_xticklabels([d[2] for d in dims], fontsize=7)
    ax.set_ylim(-0.05, 1.05)

    # Add secondary y-axis showing original scale for each dimension
    # Show original range at top of each axis line
    for i, (col, sym, label) in enumerate(dims):
        vmin, vmax = ranges[col]
        ax.annotate(f"[{vmin:.2f}, {vmax:.2f}]",
                    xy=(i, -0.08), fontsize=5.5, ha="center", va="top",
                    color="gray")

    ax.set_ylabel("归一化值 / Normalized value", fontsize=9)
    ax.legend(fontsize=7, loc="upper right", ncol=3, framealpha=0.9)
    ax.grid(True, axis="x", alpha=0.3, linewidth=0.5)
    # title removed — figure name goes in paper caption below figure
    plt.tight_layout()
    save_figure(fig, "fig3_parallel_coords", dpi=100)
    logger.info("Figure 9 saved")


def fig10_radar_chart():
    """图6: 多约束雷达图 — 各聚类质心的约束模式对比"""
    path = "data/processed/mode_analysis/mode_analysis_full.csv"
    if not Path(path).exists():
        logger.warning(f"Missing data for Figure 10: {path}")
        return

    df = pd.read_csv(path, index_col=0)

    constraints = ["f_angle", "f_freq", "f_voltage"]
    labels_cn = ["$f_{\\mathrm{angle}}$\n功角", "$f_{\\mathrm{freq}}$\n频率", "$f_{\\mathrm{voltage}}$\n电压"]
    N = len(constraints)

    # Compute cluster centroids
    clusters = sorted(df["cluster"].unique())
    centroids = df.groupby("cluster")[constraints].mean()

    # Close the radar loop
    angles = np.linspace(0, 2 * np.pi, N, endpoint=False).tolist()
    angles += angles[:1]

    cmap = CLUSTER_COLORS
    fig, ax = plt.subplots(figsize=(7, 6), subplot_kw=dict(polar=True))

    linestyles = ["-", "--", "-.", ":", (0, (3, 1, 1, 1)), (0, (5, 2))]
    markers = ["o", "s", "^", "D", "v", "P"]

    for idx, c in enumerate(clusters):
        values = centroids.loc[c, constraints].values.tolist()
        values += values[:1]
        color = cmap[c % len(cmap)]
        ax.plot(angles, values, color=color, linewidth=2,
                linestyle=linestyles[idx % len(linestyles)],
                marker=markers[idx % len(markers)], markersize=6,
                label=f"C{c} ($\\bar{{S}}$={centroids.loc[c, 'f_angle']:.2f})",
                zorder=5)
        ax.fill(angles, values, color=color, alpha=0.08)

    # Configure radar axes
    ax.set_xticks(angles[:-1])
    ax.set_xticklabels(labels_cn, fontsize=9)
    ax.set_ylim(0, 1.05)
    ax.set_rlabel_position(30)
    ax.set_yticks([0.2, 0.4, 0.6, 0.8, 1.0])
    ax.set_yticklabels(["0.2", "0.4", "0.6", "0.8", "1.0"], fontsize=6, color="gray")
    ax.grid(True, alpha=0.3, linestyle="--")

    # Annotate vertex values for each cluster
    for idx, c in enumerate(clusters):
        values = centroids.loc[c, constraints].values.tolist()
        for j, v in enumerate(values):
            angle_rad = angles[j]
            offset = 0.08
            ax.annotate(f"{v:.2f}",
                        xy=(angle_rad, v + offset),
                        fontsize=5.5, ha="center", va="bottom",
                        color=cmap[c % len(cmap)], fontweight="bold")

    ax.legend(fontsize=7, loc="upper right", bbox_to_anchor=(1.25, 1.1), framealpha=0.9)
    # title removed — figure name goes in paper caption below figure
    plt.tight_layout()
    save_figure(fig, "fig6_radar_chart")
    plt.close(fig)
    logger.info("Figure 10 saved")


def fig12_severity_limit_curve():
    """Figure 12: Severity-limit adaptivity curve for 4 methods.

    Shows how each method maps severity S to transfer limit P:
    - Uniform: flat line (no adaptivity)
    - Linear: straight line (linear adaptivity)
    - Sigmoid: smooth S-curve (nonlinear severity-only adaptivity)
    - AIA: actual data points above Sigmoid (geometry-enhanced adaptivity)
    """
    path = "data/processed/transfer_limits/transfer_limits_comparison.csv"
    if not Path(path).exists():
        logger.warning(f"Missing data for Figure 12: {path}")
        return

    df = pd.read_csv(path)

    # Use SimSun for Chinese, Times New Roman for English/math
    from matplotlib.font_manager import FontProperties
    cn_font = FontProperties(family="SimSun", size=9)
    cn_font_sm = FontProperties(family="SimSun", size=7)
    cn_font_title = FontProperties(family="SimSun", size=10)

    # Generate smooth curves
    s_grid = np.linspace(0.3, 1.0, 200)

    # Uniform: constant at worst-case level
    uniform_val = 0.401

    # Linear: P = max(0.4, 1.2 - 0.6 * S)
    linear_curve = np.maximum(0.4, 1.2 - 0.6 * s_grid)

    # Sigmoid: P = 0.4 + 0.8 * sigma(15*(S - 0.6))
    k, threshold = 15.0, 0.6
    sigmoid_curve = 0.4 + 0.8 / (1.0 + np.exp(k * (s_grid - threshold)))

    fig, ax = plt.subplots(figsize=(7, 5))

    # Plot smooth curves
    ax.axhline(y=uniform_val, color=PALETTE["uniform"], linewidth=2.5,
               linestyle="--", label="统一限额 Uniform", zorder=2)
    ax.plot(s_grid, linear_curve, color=PALETTE["linear"], linewidth=2.0,
            linestyle="-.", label="线性聚类 Linear", zorder=2)
    ax.plot(s_grid, sigmoid_curve, color=PALETTE["sigmoid"], linewidth=2.0,
            linestyle="-", label="Sigmoid聚类 Sigmoid", zorder=2)

    # Plot actual AIA data points with cluster labels
    aia_x = df["avg_severity"].values
    aia_y = df["aia_limit"].values
    aia_colors = ["#4CAF50" if y > 0.6 else "#81C784" for y in aia_y]
    ax.scatter(aia_x, aia_y, s=55, c=aia_colors, marker="D",
               edgecolors="black", linewidth=0.6, zorder=4,
               label="AIA边界 AIA (本文)")

    # Connect AIA points to their Sigmoid base with vertical dashed arrows
    for _, row in df.iterrows():
        s_val = row["avg_severity"]
        aia_val = row["aia_limit"]
        sig_val = row["sigmoid_limit"]
        if aia_val > sig_val + 0.02:
            ax.annotate("", xy=(s_val, aia_val - 0.01),
                        xytext=(s_val, sig_val + 0.01),
                        arrowprops=dict(arrowstyle="->", color="#66BB6A",
                                        lw=1.2, linestyle="--"))

    # Label each AIA point with cluster ID
    for _, row in df.iterrows():
        offset_y = 0.018
        offset_x = 0.006
        ax.annotate(f"C{int(row['cluster_id'])}",
                    (row["avg_severity"] + offset_x, row["aia_limit"] + offset_y),
                    fontsize=6, fontweight="bold", color="#2E7D32")

    # Add shaded regions to highlight adaptivity gaps
    ax.fill_between(s_grid, sigmoid_curve, linear_curve,
                    alpha=0.08, color=PALETTE["linear"])
    ax.fill_between(s_grid, uniform_val, sigmoid_curve,
                    where=(sigmoid_curve > uniform_val),
                    alpha=0.08, color=PALETTE["sigmoid"])

    # Key insight annotation: point to the cluster with largest geometric correction
    # Find the best AIA cluster (largest gap between aia_limit and sigmoid_limit)
    best_idx = (df["aia_limit"] - df["sigmoid_limit"]).idxmax()
    best_row = df.loc[best_idx]
    best_x, best_y = best_row["avg_severity"], best_row["aia_limit"]
    best_sig = best_row["sigmoid_limit"]
    if best_y > best_sig + 0.05:
        ax.annotate("几何修正增益",
                    xy=(best_x, best_y), xytext=(max(0.35, best_x - 0.20), min(1.10, best_y + 0.12)),
                    fontproperties=cn_font_sm, color="#2E7D32", fontweight="bold",
                    arrowprops=dict(arrowstyle="->", color="#2E7D32", lw=0.8),
                    bbox=dict(boxstyle="round,pad=0.2", fc="white", ec="#4CAF50", alpha=0.9))

    ax.set_xlabel("场景平均严重度 " + r"$\bar{S}$" + "  /  Scenario severity", fontsize=9)
    ax.set_ylabel(r"传输容量限额 $P_{78}^{\mathrm{limit}}$  /  Transfer limit (p.u.)", fontsize=9)
    ax.set_xlim(0.55, 1.05)
    ax.set_ylim(0.25, 1.20)
    ax.legend(fontsize=7, loc="upper right", framealpha=0.9, prop=cn_font_sm)
    ax.grid(True, alpha=0.3)

    # Text annotations for method characteristics (using SimSun via fontproperties)
    ax.text(0.62, 0.35, "无适应性", fontproperties=cn_font_sm,
            ha="center", color="#757575", style="italic")
    ax.text(0.85, 0.72, "线性适应性", fontproperties=cn_font_sm,
            ha="center", color=PALETTE["linear"], style="italic", rotation=-30)

    # title removed — figure name goes in paper caption below figure
    plt.tight_layout()
    save_figure(fig, "fig12_severity_limit_adaptivity")
    plt.close(fig)
    logger.info("Figure 12 saved")


def main():
    logger.info("=== Generating Paper Figures ===")

    fig3_mogp_r2()
    fig4_bo_convergence()
    fig5_re_impact()
    fig6_aia_boundary()
    fig7_transfer_limits()
    fig10_closed_loop()
    fig9_parallel_coordinates()
    fig10_radar_chart()
    fig12_severity_limit_curve()

    logger.info(f"\nAll figures saved to {OUTPUT_DIR}")
    logger.info("=== Figure Generation Complete ===")


if __name__ == "__main__":
    main()
