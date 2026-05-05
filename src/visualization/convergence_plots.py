"""Convergence curve plots for method comparison."""

from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import seaborn as sns


def plot_convergence_curves(
    results_by_method: dict[str, list[np.ndarray]],
    output_path: str | Path,
    title: str = "Convergence Comparison",
    figsize: tuple = (7, 4.5),
):
    """Plot convergence curves with mean ± std shading.

    Args:
        results_by_method: {method_name: [convergence_array_per_seed, ...]}
        output_path: Save path for the figure.
    """
    sns.set_style("whitegrid")
    fig, ax = plt.subplots(figsize=figsize)

    for method, curves in results_by_method.items():
        curves = np.array(curves)  # (n_seeds, n_evals)
        mean = np.mean(curves, axis=0)
        std = np.std(curves, axis=0)
        x = np.arange(1, len(mean) + 1)

        ax.plot(x, mean, label=method.upper(), linewidth=1.5)
        ax.fill_between(x, mean - std, mean + std, alpha=0.2)

    ax.set_xlabel("Number of Evaluations")
    ax.set_ylabel("Best Severity Found")
    ax.set_title(title)
    ax.legend(loc="lower right")
    ax.set_xlim(left=1)

    fig.tight_layout()
    fig.savefig(output_path, dpi=300, bbox_inches="tight")
    plt.close(fig)
