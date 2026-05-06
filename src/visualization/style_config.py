"""Centralized CSEE journal style configuration for beyesgp figures."""

import matplotlib
import matplotlib.pyplot as plt
from pathlib import Path

# === CSEE Journal Target: Chinese serif fonts, 7-8pt text ===

CSEE_RCPARAMS = {
    # Fonts
    "font.family": "serif",
    "font.serif": ["SimSun", "Times New Roman", "DejaVu Serif"],
    "font.sans-serif": ["SimHei", "Microsoft YaHei", "DejaVu Sans"],
    "font.size": 8,
    "axes.unicode_minus": False,

    # Editable vector text
    "svg.fonttype": "none",
    "pdf.fonttype": 42,

    # Axes
    "axes.spines.right": False,
    "axes.spines.top": False,
    "axes.linewidth": 0.8,
    "axes.labelsize": 8,
    "axes.titlesize": 9,

    # Ticks
    "xtick.labelsize": 7,
    "ytick.labelsize": 7,
    "xtick.direction": "in",
    "ytick.direction": "in",

    # Legend
    "legend.frameon": False,
    "legend.fontsize": 7,

    # Figure
    "figure.dpi": 300,
    "savefig.dpi": 300,
    "savefig.bbox": "tight",
    "savefig.pad_inches": 0.05,
}

# Semantic palette (nature-skills derived, domain-adapted for power systems)
PALETTE = {
    "safe": "#0F4D92",
    "unsafe": "#B64342",
    "boundary": "#FF9800",
    "bo": "#3775BA",
    "random": "#767676",
    "lhs": "#CFCECE",
    "ga": "#9A4D8E",
    "uniform": "#CFCECE",
    "linear": "#42949E",
    "sigmoid": "#9A4D8E",
    "aia": "#0F4D92",
    "hero": "#0F4D92",
    "accent": "#FFD700",
}

# Cluster colors: coherent family (replaces tab10)
CLUSTER_COLORS = [
    "#0F4D92",  # blue_main
    "#3775BA",  # blue_secondary
    "#42949E",  # teal
    "#8BCF8B",  # green_3
    "#9A4D8E",  # violet
    "#B64342",  # red_strong
    "#FFD700",  # gold
    "#767676",  # neutral_mid
]

# Safety colormap: blue(safe) -> yellow -> red(unsafe)
SAFETY_CMAP_COLORS = ["#1565C0", "#42A5F5", "#FFF176", "#FF8A65", "#C62828"]

FIGURE_DIR = Path("paper/figures")


def apply_csee_style():
    """Apply CSEE journal style. Call once before creating any figures."""
    matplotlib.use("Agg")
    plt.rcParams.update(CSEE_RCPARAMS)


def save_figure(fig, name, formats=None, dpi=300, figure_dir=None):
    """Save figure in SVG + PDF + PNG. Closes fig to free memory."""
    if formats is None:
        formats = ["svg", "pdf", "png"]
    out_dir = Path(figure_dir) if figure_dir else FIGURE_DIR
    out_dir.mkdir(parents=True, exist_ok=True)
    base = out_dir / name
    saved = []
    for fmt in formats:
        path = base.with_suffix(f".{fmt}")
        if fmt == "png":
            fig.savefig(str(path), dpi=dpi, bbox_inches="tight")
        else:
            fig.savefig(str(path), bbox_inches="tight")
        saved.append(str(path))
    plt.close(fig)
    return saved


def add_panel_label(ax, label, x=-0.06, y=1.02, fontsize=9):
    """Place a Nature-style bold lowercase panel label near top-left."""
    ax.text(x, y, label, transform=ax.transAxes,
            fontsize=fontsize, fontweight="bold",
            ha="left", va="bottom")


def is_dark(hex_color, threshold=128):
    """Return True if hex color is dark (use white text on it)."""
    c = hex_color.lstrip("#")
    r, g, b = int(c[0:2], 16), int(c[2:4], 16), int(c[4:6], 16)
    return (0.299 * r + 0.587 * g + 0.114 * b) < threshold
