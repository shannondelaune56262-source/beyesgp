"""Generate fig4: entropy weight variation across RE penetration levels."""
import sys
import io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

import matplotlib
import matplotlib.pyplot as plt
import numpy as np

from src.visualization.style_config import apply_csee_style, save_figure

apply_csee_style()

levels = np.array([0, 1, 2, 3, 4])
labels = ['Level 0\n(0%)', 'Level 1\n(15%)', 'Level 2\n(30%)', 'Level 3\n(45%)', 'Level 4\n(60%)']

# Data from Section 3.2.3 description
omega_a = np.array([0.62, 0.55, 0.42, 0.38, 0.35])
omega_f = np.array([0.08, 0.12, 0.30, 0.33, 0.35])
omega_v = np.array([0.30, 0.33, 0.28, 0.29, 0.30])

fig, ax = plt.subplots(figsize=(8, 5))

ax.plot(levels, omega_a, 'ko-', linewidth=2, markersize=8, label=r'$\omega_a$（功角）')
ax.plot(levels, omega_f, 'k^--', linewidth=2, markersize=8, label=r'$\omega_f$（频率）')
ax.plot(levels, omega_v, 'ks:', linewidth=2, markersize=8, label=r'$\omega_v$（电压）')

ax.set_xticks(levels)
ax.set_xticklabels(labels, fontsize=11)
ax.set_ylabel('权重系数', fontsize=13)
ax.set_xlabel('新能源渗透率等级', fontsize=13)
ax.set_ylim(0, 0.75)
ax.set_xlim(-0.2, 4.2)

ax.legend(fontsize=12, loc='center right')
ax.grid(True, linestyle='--', alpha=0.3)

# Annotate transition regions
ax.axvspan(-0.2, 1.2, alpha=0.06, color='blue', label='_nolegend_')
ax.axvspan(1.8, 2.2, alpha=0.06, color='green', label='_nolegend_')
ax.axvspan(2.8, 4.2, alpha=0.06, color='red', label='_nolegend_')

ax.annotate('功角单一主导', xy=(0.5, 0.68), fontsize=10, ha='center', color='blue')
ax.annotate('双约束\n过渡', xy=(2.0, 0.68), fontsize=9, ha='center', color='green')
ax.annotate('多约束耦合', xy=(3.5, 0.68), fontsize=10, ha='center', color='red')

fig.tight_layout()
save_figure(fig, "fig4_entropy_weights")
print("fig4 saved successfully")
