"""Comprehensive IEEE 39-bus analysis: statistics, limits, figures, and tables.

Works with checkpoint data (partial sweep) to produce:
  - Severity statistics per distribution mode and RE penetration level
  - Transfer limit comparison (uniform vs flexible per-cluster)
  - All figures (fig16-fig20) and tables (tab9-tab10)
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
from sklearn.cluster import KMeans
from sklearn.preprocessing import StandardScaler
from scipy import stats

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8")
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

rcParams['font.family'] = 'serif'
rcParams['font.size'] = 10
rcParams['axes.linewidth'] = 0.8
rcParams['figure.dpi'] = 300


def load_data():
    """Load sweep results (checkpoint or final)."""
    data_dir = Path("data/processed/ieee39_re_sweep")
    final = data_dir / "ieee39_re_sweep_results.csv"
    checkpoint = data_dir / "ieee39_re_sweep_checkpoint.csv"
    if final.exists():
        df = pd.read_csv(final)
        print(f"Loaded final results: {len(df)} rows")
    elif checkpoint.exists():
        df = pd.read_csv(checkpoint)
        print(f"Loaded checkpoint: {len(df)} rows (sweep still running)")
    else:
        raise FileNotFoundError("No sweep data found")
    return df


def compute_statistics(df):
    """Compute summary statistics for tab9."""
    stats_rows = []
    for pen in sorted(df["re_penetration"].unique()):
        sub = df[df["re_penetration"] == pen]
        n_total = len(sub)
        n_success = sub["success"].sum()
        n_stable = sub["stable"].sum()
        ok = sub[sub["success"]]

        row = {
            "re_penetration": f"{pen:.0%}",
            "n_total": n_total,
            "n_success": int(n_success),
            "success_rate": f"{n_success/n_total*100:.1f}%" if n_total > 0 else "N/A",
            "n_stable": int(n_stable),
            "stable_rate": f"{n_stable/n_success*100:.1f}%" if n_success > 0 else "N/A",
            "severity_mean": f"{ok['severity'].mean():.3f}" if len(ok) > 0 else "N/A",
            "severity_std": f"{ok['severity'].std():.3f}" if len(ok) > 0 else "N/A",
            "f_angle_mean": f"{ok['f_angle'].mean():.3f}" if len(ok) > 0 else "N/A",
            "f_freq_mean": f"{ok['f_freq'].mean():.3f}" if len(ok) > 0 else "N/A",
            "f_voltage_mean": f"{ok['f_voltage'].mean():.3f}" if len(ok) > 0 else "N/A",
            "max_angle_mean": f"{ok['max_angle_deg'].mean():.1f}" if len(ok) > 0 else "N/A",
            "V_min_mean": f"{ok['V_min'].mean():.4f}" if len(ok) > 0 else "N/A",
            "initial_flow_mean": f"{ok['initial_flow_MW'].mean():.1f}" if len(ok) > 0 else "N/A",
            "max_flow_mean": f"{ok['max_flow_MW'].mean():.1f}" if len(ok) > 0 else "N/A",
        }
        stats_rows.append(row)

    return pd.DataFrame(stats_rows)


def compute_transfer_limits(df):
    """Compute uniform vs per-cluster transfer limits."""
    ok = df[df["success"] == True].copy()
    ok["distribution_mode"] = ok["re_west_fraction"].apply(classify_distribution)

    # Use initial_flow_MW as the pre-fault interface transfer level
    flow_col = "initial_flow_MW"

    # Filter stable cases only
    stable = ok[ok["stable"] == True].copy()
    print(f"\nTransfer limit computation: {len(stable)} stable cases out of {len(ok)} successful")

    if len(stable) < 10:
        print("WARNING: Too few stable cases for reliable limit calculation")
        return None

    # Uniform limit: 10th percentile of pre-fault flow among stable cases
    uniform_limit = np.percentile(stable[flow_col], 10)
    print(f"Uniform limit (10th pct): {uniform_limit:.1f} MW")

    # Per-distribution-mode flexible limits
    results = []
    for mode in ["west_concentrated", "balanced", "east_concentrated"]:
        sub = stable[stable["distribution_mode"] == mode]
        if len(sub) < 3:
            print(f"  {mode}: only {len(sub)} stable cases, skipping")
            continue
        mode_limit = np.percentile(sub[flow_col], 10)
        improvement = (mode_limit - uniform_limit) / abs(uniform_limit) * 100

        results.append({
            "distribution_mode": mode,
            "n_stable": len(sub),
            "avg_re_west_frac": f"{sub['re_west_fraction'].mean():.3f}",
            "avg_re_penetration": f"{sub['re_penetration'].mean():.3f}",
            "avg_initial_flow_MW": f"{sub[flow_col].mean():.1f}",
            "uniform_limit_MW": f"{uniform_limit:.1f}",
            "flexible_limit_MW": f"{mode_limit:.1f}",
            "improvement_pct": f"{improvement:+.1f}",
        })
        print(f"  {mode}: limit={mode_limit:.1f} MW (uniform={uniform_limit:.1f}), "
              f"improvement={improvement:+.1f}%")

    if not results:
        return None

    comp_df = pd.DataFrame(results)

    # KMeans clustering for more detailed analysis
    cluster_features = ["re_west_fraction", "re_penetration", "load_level_west", "load_level_east"]
    valid = stable.dropna(subset=cluster_features)
    if len(valid) >= 10:
        X = valid[cluster_features].values
        scaler = StandardScaler()
        X_scaled = scaler.fit_transform(X)
        n_clusters = min(3, len(valid) // 5)
        kmeans = KMeans(n_clusters=n_clusters, random_state=42, n_init=10)
        valid["cluster_id"] = kmeans.fit_predict(X_scaled)

        print(f"\nKMeans clustering (k={n_clusters}):")
        for c in range(n_clusters):
            cl = valid[valid["cluster_id"] == c]
            cl_limit = np.percentile(cl[flow_col], 10) if len(cl) >= 3 else uniform_limit
            print(f"  Cluster {c}: n={len(cl)}, avg_west_frac={cl['re_west_fraction'].mean():.3f}, "
                  f"limit={cl_limit:.1f} MW")

    return comp_df


def classify_distribution(f):
    if f >= 0.7:
        return "west_concentrated"
    elif f <= 0.3:
        return "east_concentrated"
    else:
        return "balanced"


def plot_severity_boxplot(df, output_path):
    """Fig16: Severity breakdown by RE penetration and distribution mode."""
    ok = df[df["success"] == True].copy()
    ok["distribution_mode"] = ok["re_west_fraction"].apply(classify_distribution)

    fig, axes = plt.subplots(1, 3, figsize=(14, 5))

    # Panel (a): Overall severity by RE penetration
    pen_levels = sorted(ok["re_penetration"].unique())
    data_sev = [ok[ok["re_penetration"] == p]["severity"].values for p in pen_levels]
    bp1 = axes[0].boxplot(data_sev, labels=[f"{p:.0%}" for p in pen_levels],
                           patch_artist=True, widths=0.5)
    colors_pen = plt.cm.Blues(np.linspace(0.3, 0.8, len(pen_levels)))
    for patch, color in zip(bp1['boxes'], colors_pen):
        patch.set_facecolor(color)
    axes[0].set_xlabel("RE Penetration Level")
    axes[0].set_ylabel("Severity Index $f$")
    axes[0].set_title("(a) Severity vs RE Penetration")
    axes[0].grid(True, alpha=0.3, axis='y')

    # Panel (b): f_angle, f_freq, f_voltage breakdown by RE penetration
    components = ["f_angle", "f_freq", "f_voltage"]
    comp_colors = ["#e74c3c", "#3498db", "#2ecc71"]
    x_pos = np.arange(len(pen_levels))
    width = 0.25
    for i, (comp, color) in enumerate(zip(components, comp_colors)):
        means = [ok[ok["re_penetration"] == p][comp].mean() for p in pen_levels]
        stds = [ok[ok["re_penetration"] == p][comp].std() for p in pen_levels]
        axes[1].bar(x_pos + i * width, means, width, yerr=stds,
                    label=comp.replace("f_", "$f_{\\rm ") + "}$" if comp != "f_angle" else "$f_\\delta$",
                    color=color, alpha=0.8, capsize=3)
    axes[1].set_xlabel("RE Penetration Level")
    axes[1].set_ylabel("Component Severity")
    axes[1].set_title("(b) Severity Components")
    axes[1].set_xticks(x_pos + width)
    axes[1].set_xticklabels([f"{p:.0%}" for p in pen_levels])
    axes[1].legend(fontsize=8)
    axes[1].grid(True, alpha=0.3, axis='y')

    # Panel (c): Severity by distribution mode (for all RE levels combined)
    modes = ["west_concentrated", "balanced", "east_concentrated"]
    mode_labels = ["WEST\nConcentrated", "Balanced", "EAST\nConcentrated"]
    mode_colors = ["#e74c3c", "#f39c12", "#3498db"]
    data_mode = [ok[ok["distribution_mode"] == m]["severity"].values for m in modes]
    bp3 = axes[2].boxplot(data_mode, labels=mode_labels, patch_artist=True, widths=0.5)
    for patch, color in zip(bp3['boxes'], mode_colors):
        patch.set_facecolor(color)
    axes[2].set_xlabel("RE Distribution Mode")
    axes[2].set_ylabel("Severity Index $f$")
    axes[2].set_title("(c) Severity vs Distribution Mode")
    axes[2].grid(True, alpha=0.3, axis='y')

    plt.tight_layout()
    plt.savefig(output_path, bbox_inches='tight', dpi=300)
    plt.close()
    print(f"Saved: {output_path}")


def plot_transfer_limits(limits_df, df, output_path):
    """Fig17: Transfer limit comparison (uniform vs flexible)."""
    if limits_df is None or len(limits_df) == 0:
        print("No limit data to plot")
        return

    fig, axes = plt.subplots(1, 2, figsize=(12, 5))

    # Panel (a): Bar chart comparing limits
    modes = limits_df["distribution_mode"].values
    uniform_vals = limits_df["uniform_limit_MW"].astype(float).values
    flexible_vals = limits_df["flexible_limit_MW"].astype(float).values

    x = np.arange(len(modes))
    width = 0.35
    bars1 = axes[0].bar(x - width/2, uniform_vals, width, label='Uniform Limit',
                         color='#95a5a6', edgecolor='black', linewidth=0.5)
    bars2 = axes[0].bar(x + width/2, flexible_vals, width, label='Flexible Limit',
                         color='#2ecc71', edgecolor='black', linewidth=0.5)
    axes[0].set_xlabel("Distribution Mode")
    axes[0].set_ylabel("Transfer Limit (MW)")
    axes[0].set_title("(a) Transfer Limit Comparison")
    axes[0].set_xticks(x)
    mode_labels = [m.replace("_", "\n") for m in modes]
    axes[0].set_xticklabels(mode_labels, fontsize=8)
    axes[0].legend()
    axes[0].grid(True, alpha=0.3, axis='y')

    # Add improvement annotations
    for i, (u, f) in enumerate(zip(uniform_vals, flexible_vals)):
        if u != 0:
            pct = (f - u) / abs(u) * 100
            axes[0].annotate(f"{pct:+.1f}%", xy=(i + width/2, f),
                           xytext=(0, 5), textcoords='offset points',
                           ha='center', fontsize=8, fontweight='bold')

    # Panel (b): Scatter plot of initial_flow vs severity, colored by mode
    ok = df[df["success"] == True].copy()
    ok["distribution_mode"] = ok["re_west_fraction"].apply(classify_distribution)
    mode_colors_map = {"west_concentrated": "#e74c3c", "balanced": "#f39c12",
                       "east_concentrated": "#3498db"}
    for mode, color in mode_colors_map.items():
        sub = ok[ok["distribution_mode"] == mode]
        axes[1].scatter(sub["initial_flow_MW"], sub["severity"],
                       c=color, label=mode, alpha=0.5, s=20, edgecolors='none')

    # Mark stable/unstable boundary
    axes[1].axhline(y=0.5, color='gray', linestyle='--', alpha=0.5, label='Stability boundary')
    axes[1].set_xlabel("Initial Interface Flow (MW)")
    axes[1].set_ylabel("Severity Index $f$")
    axes[1].set_title("(b) Flow vs Severity by Distribution Mode")
    axes[1].legend(fontsize=7)
    axes[1].grid(True, alpha=0.3)

    plt.tight_layout()
    plt.savefig(output_path, bbox_inches='tight', dpi=300)
    plt.close()
    print(f"Saved: {output_path}")


def statistical_tests(df):
    """Run statistical tests for significance of distribution effects."""
    ok = df[df["success"] == True].copy()
    ok["distribution_mode"] = ok["re_west_fraction"].apply(classify_distribution)

    results = {}

    # ANOVA test: severity across distribution modes
    groups = [ok[ok["distribution_mode"] == m]["severity"].values
              for m in ["west_concentrated", "balanced", "east_concentrated"]]
    groups = [g for g in groups if len(g) >= 3]
    if len(groups) >= 2:
        f_stat, p_value = stats.f_oneway(*groups)
        results["severity_anova_p"] = p_value
        print(f"Severity ANOVA: F={f_stat:.3f}, p={p_value:.4e}")

    # T-test: WEST vs EAST concentrated
    west = ok[ok["distribution_mode"] == "west_concentrated"]["severity"].values
    east = ok[ok["distribution_mode"] == "east_concentrated"]["severity"].values
    if len(west) >= 3 and len(east) >= 3:
        t_stat, p_value = stats.ttest_ind(west, east)
        results["severity_west_vs_east_p"] = p_value
        print(f"Severity WEST vs EAST t-test: t={t_stat:.3f}, p={p_value:.4e}")

    # Flow difference between distribution modes
    for metric in ["initial_flow_MW", "max_flow_MW"]:
        groups_flow = [ok[ok["distribution_mode"] == m][metric].dropna().values
                       for m in ["west_concentrated", "balanced", "east_concentrated"]]
        groups_flow = [g for g in groups_flow if len(g) >= 3]
        if len(groups_flow) >= 2:
            f_stat, p_val = stats.f_oneway(*groups_flow)
            results[f"{metric}_anova_p"] = p_val
            print(f"{metric} ANOVA: F={f_stat:.3f}, p={p_val:.4e}")

    return results


def write_tab9(stats_df, output_path):
    """Write tab9: IEEE 39 simulation statistics table."""
    lines = ["| 指标 | " + " | ".join(stats_df["re_penetration"].values) + " |",
             "|------|" + "|".join(["------"] * len(stats_df)) + "|"]
    for col in stats_df.columns[1:]:
        label_map = {
            "n_total": "仿真总数",
            "n_success": "成功数",
            "success_rate": "成功率",
            "n_stable": "稳定数",
            "stable_rate": "稳定率",
            "severity_mean": "严重度均值",
            "severity_std": "严重度标准差",
            "f_angle_mean": "$f_\\delta$均值",
            "f_freq_mean": "$f_f$均值",
            "f_voltage_mean": "$f_V$均值",
            "max_angle_mean": "最大功角差(°)",
            "V_min_mean": "最低电压(p.u.)",
            "initial_flow_mean": "初始断面潮流(MW)",
            "max_flow_mean": "最大断面潮流(MW)",
        }
        label = label_map.get(col, col)
        vals = [str(v) for v in stats_df[col].values]
        lines.append(f"| {label} | " + " | ".join(vals) + " |")

    with open(output_path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))
    print(f"Saved: {output_path}")


def write_tab10(limits_df, output_path):
    """Write tab10: Transfer limit comparison table."""
    if limits_df is None:
        return
    lines = [
        "| 分布模式 | 稳定样本数 | 平均$\\alpha_W$ | 平均RE渗透率 | "
        "断面潮流均值(MW) | 统一限额(MW) | 灵活限额(MW) | 提升(%) |",
        "|----------|-----------|---------------|-------------|------------------|-------------|-------------|---------|",
    ]
    for _, row in limits_df.iterrows():
        lines.append(
            f"| {row['distribution_mode']} | {row['n_stable']} | "
            f"{row['avg_re_west_frac']} | {row['avg_re_penetration']} | "
            f"{row['avg_initial_flow_MW']} | {row['uniform_limit_MW']} | "
            f"{row['flexible_limit_MW']} | {row['improvement_pct']} |"
        )

    with open(output_path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))
    print(f"Saved: {output_path}")


def main():
    output_fig_dir = Path("paper/figures")
    output_tab_dir = Path("paper/tables")
    output_data_dir = Path("data/processed/ieee39_transfer_limits")
    for d in [output_fig_dir, output_tab_dir, output_data_dir]:
        d.mkdir(parents=True, exist_ok=True)

    # Load data
    df = load_data()
    print(f"\n{'='*60}")
    print(f"Data overview: {len(df)} simulations")
    print(f"  RE levels: {sorted(df['re_penetration'].unique())}")
    print(f"  Modes: {df['mode_idx'].nunique()}")
    print(f"  Faults: {df['fault_name'].nunique()}")
    print(f"  Success: {df['success'].mean()*100:.1f}%")
    print(f"  Stable: {df['stable'].mean()*100:.1f}%")
    print(f"{'='*60}")

    # 1. Compute statistics (tab9)
    print("\n--- Computing Statistics (Tab 9) ---")
    stats_df = compute_statistics(df)
    write_tab9(stats_df, output_tab_dir / "tab9_ieee39_results.md")

    # 2. Statistical tests
    print("\n--- Statistical Tests ---")
    stat_results = statistical_tests(df)

    # 3. Transfer limits (tab10)
    print("\n--- Transfer Limits (Tab 10) ---")
    limits_df = compute_transfer_limits(df)
    write_tab10(limits_df, output_data_dir / "ieee39_limits_comparison.csv")
    write_tab10(limits_df, output_tab_dir / "tab10_ieee39_limits.md")

    # 4. Figures
    print("\n--- Generating Figures ---")
    plot_severity_boxplot(df, output_fig_dir / "fig16_ieee39_severity_boxplot.pdf")
    plot_transfer_limits(limits_df, df, output_fig_dir / "fig17_ieee39_transfer_limits.pdf")

    print("\n=== Analysis Complete ===")


if __name__ == "__main__":
    main()
