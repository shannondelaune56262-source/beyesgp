"""Severity heatmap for 2D parameter space."""

from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import seaborn as sns


def plot_severity_heatmap(
    grid_X: np.ndarray,
    grid_y: np.ndarray,
    dim_names: list[str],
    bo_points: np.ndarray | None = None,
    output_path: str | Path = "data/figures/severity_heatmap.pdf",
    figsize: tuple = (6, 5),
):
    """Plot 2D severity heatmap with optional BO sampling trajectory.

    Args:
        grid_X: Grid points, shape (n, 2).
        grid_y: Severity values, shape (n,).
        dim_names: Names for the two dimensions.
        bo_points: BO sampling points to overlay, shape (n_bo, 2).
        output_path: Save path.
    """
    x0_unique = np.sort(np.unique(grid_X[:, 0]))
    x1_unique = np.sort(np.unique(grid_X[:, 1]))

    Z = np.full((len(x1_unique), len(x0_unique)), np.nan)
    for i, (x0, x1) in enumerate(grid_X):
        i0 = np.argmin(np.abs(x0_unique - x0))
        i1 = np.argmin(np.abs(x1_unique - x1))
        Z[i1, i0] = grid_y[i]

    fig, ax = plt.subplots(figsize=figsize)
    im = ax.imshow(
        Z, origin="lower", aspect="auto",
        extent=[x0_unique[0], x0_unique[-1], x1_unique[0], x1_unique[-1]],
        cmap="YlOrRd",
    )
    plt.colorbar(im, ax=ax, label="Severity Score")

    if bo_points is not None and len(bo_points) > 0:
        ax.scatter(
            bo_points[:, 0], bo_points[:, 1],
            c="blue", s=15, alpha=0.7, edgecolors="white", linewidths=0.5,
            label="BO samples",
        )
        # Number the points
        for i, (x, y) in enumerate(bo_points):
            if i < 20:  # Only number first 20 to avoid clutter
                ax.annotate(str(i + 1), (x, y), fontsize=6, color="blue")
        ax.legend(loc="upper right", fontsize=8)

    ax.set_xlabel(dim_names[0])
    ax.set_ylabel(dim_names[1])
    ax.set_title("Severity Landscape with BO Sampling Trajectory")

    fig.tight_layout()
    fig.savefig(output_path, dpi=300, bbox_inches="tight")
    plt.close(fig)
