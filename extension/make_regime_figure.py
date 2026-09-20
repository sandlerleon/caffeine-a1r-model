# -*- coding: utf-8 -*-
"""Figure 4: the region of assumption-space in which the experiment is
informative.

    python make_regime_figure.py
"""
import json
import os

import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

HERE = os.path.dirname(os.path.abspath(__file__))
R = json.load(open(os.path.join(HERE, "design_regime_results.json")))
DPI = 300
plt.rcParams.update({"font.size": 8.5, "axes.labelsize": 9, "axes.titlesize": 9,
                     "legend.fontsize": 7.6, "xtick.labelsize": 8,
                     "ytick.labelsize": 8, "axes.linewidth": 0.8,
                     "font.family": "DejaVu Sans"})
BLUE, RED = "#1b6ca8", "#c1553b"

taus = np.array(R["tau_down_days"])
gam = np.array(R["gamma"])
P = np.array(R["power_grid"])

fig, ax = plt.subplots(1, 2, figsize=(9.8, 3.8),
                       gridspec_kw={"width_ratios": [1.25, 1.0]})

# ------------------------------------------------------- A: the power map
im = ax[0].pcolormesh(taus, gam, P.T, cmap="viridis", shading="auto",
                      vmin=0, vmax=1)
cs = ax[0].contour(taus, gam, P.T, levels=[0.8], colors="white", linewidths=1.6)
ax[0].clabel(cs, fmt={0.8: "power 0.80"}, fontsize=7.4,
             manual=[(12.0, 0.72)])
ax[0].contour(taus, gam, P.T, levels=[0.5], colors="white", linewidths=0.8,
              linestyles="--")
ax[0].set_xscale("log")
ax[0].set_xlabel("assumed decay time constant after last dose (days)")
ax[0].set_ylabel(r"$\gamma$, fraction of receptor gain reaching threshold")
ax[0].set_title("A   Where the experiment is adequately powered",
                loc="left", fontweight="bold")

# the planned design point
base_tau = R["base_params"]["tau_down_d"]
ax[0].plot([base_tau], [1.0], "o", ms=7, color="#ffffff",
           markeredgecolor=RED, markeredgewidth=1.6, zorder=6)
ax[0].annotate("planned design\n(central scenario)", xy=(base_tau, 0.985),
               xytext=(9.0, 0.47), fontsize=7.3, color="white", ha="center",
               arrowprops=dict(arrowstyle="->", lw=1.0, color="white"))
# the rat-PET-like corner
pet = R["power_at_pet_corner"]
ax[0].plot([pet["tau_down_d"]], [1.0], "s", ms=6.5, color="#ffd166",
           markeredgecolor="#333333", markeredgewidth=0.8, zorder=6)
ax[0].annotate("rat PET-like reversal\npower %.2f" % pet["gamma_1"],
               xy=(pet["tau_down_d"], 0.985), xytext=(0.27, 0.62),
               fontsize=7.3, color="white", ha="left",
               arrowprops=dict(arrowstyle="->", lw=1.0, color="white"))
ax[0].text(0.27, 0.06,
           "adequately powered over %.0f%% of the plane"
           % (100 * R["frac_of_grid_powered"]),
           fontsize=7.4, color="white")
cb = fig.colorbar(im, ax=ax[0], pad=0.02)
cb.set_label("power at %d per sex per group" % R["n_per_sex"], fontsize=8)

# ------------------------------------- B: gain against decay, and elasticities
ax[1].plot(taus, R["gain_by_tau"], color=BLUE, lw=1.9)
ax[1].set_xscale("log")
ax[1].set_xlabel("assumed decay time constant (days)")
ax[1].set_ylabel("modelled A$_1$R gain at testing (%)")
ax[1].set_title("B   Sensitivity to decay is strongly non-local",
                loc="left", fontweight="bold")
ax[1].axvline(base_tau, color=RED, lw=1.0, ls="--")
ax[1].text(base_tau * 1.12, 8.0, "base case", fontsize=7.3, color=RED, rotation=90)
ax[1].axvspan(taus.min(), 2.0, color="#c1553b", alpha=0.08)
ax[1].text(0.27, 22.6, "steep: the range\nthat decides feasibility",
           fontsize=7.2, color="#8a3a28")
ax[1].text(6.0, 12.0, "flat: a local sensitivity\nanalysis here understates it",
           fontsize=7.2, color="#444444")
ax[1].set_ylim(0, 26)
ax[1].spines[["top", "right"]].set_visible(False)

fig.tight_layout()
out = os.path.join(HERE, "figure4_design_regime.png")
fig.savefig(out, dpi=DPI, bbox_inches="tight")
print(os.path.basename(out))
