# -*- coding: utf-8 -*-
"""The parameter regime in which the proposed experiment is worth running.

The manuscript already reports one-at-a-time sensitivity (its Table 3) and two
one-dimensional sweeps (its Figure 3). What neither shows is the joint region of
assumption-space in which the experiment is adequately powered -- and since the
two assumptions that matter are how fast adaptation reverses (tau_down) and how
much of a receptor gain reaches seizure threshold (gamma), that region is two
dimensional and can be drawn.

This is the same device used in the author's PMPI manuscript, which identifies
the parameter regime in which personalization could outperform a generic
vaccine. Here it answers a sharper question: before any animal is used, for
which beliefs about the mechanism is this experiment informative, and for which
is it futile?

Two outputs:

  1  A power map over (tau_down, gamma) at the planned sample size, with the
     0.8 contour and the rat-PET-like corner marked.
  2  An elasticity ranking: the proportional change in modelled gain per
     proportional change in each assumed parameter, so the assumptions can be
     ordered by how much they matter.

    python design_regime.py
"""
import importlib.util
import json
import os

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
CODE = os.path.join(HERE, "CaffeineMC", "CaffeineMC.py")
spec = importlib.util.spec_from_file_location("cmc", CODE)
M = importlib.util.module_from_spec(spec)
spec.loader.exec_module(M)

N = 2000          # matches the manuscript's headline runs
NSIM = 4000
N_PER_SEX = 12    # the planned design
SEED = 20260919
BASE = dict(M.P0, n=N, seed=SEED, washout="abrupt")

res = {"n": N, "nsim": NSIM, "n_per_sex": N_PER_SEX, "seed": SEED,
       "base_params": {k: BASE[k] for k in
                       ("ki_uM", "rmax", "tau_up_d", "tau_down_d", "hill",
                        "tau_theta_h", "seiz_uM")}}

# ================================================= 1. power over (tau_down, gamma)
taus = np.round(np.geomspace(0.25, 21.0, 18), 3)
gammas = np.round(np.linspace(0.0, 1.0, 21), 3)
print("simulating %d washout scenarios..." % len(taus))
pools = {}
gains = []
for td in taus:
    o = M.simulate("water", dict(BASE, tau_down_d=float(td)))
    pools[float(td)] = o["R_test"][~o["removed"]]
    gains.append(M.gain_of(o))
    print("   tau_down %6.2f d -> modelled gain %5.2f%%" % (td, gains[-1]))

grid = np.zeros((len(taus), len(gammas)))
for i, td in enumerate(taus):
    for j, g in enumerate(gammas):
        grid[i, j] = M.power(pools[float(td)], float(g), N_PER_SEX, NSIM)

res["tau_down_days"] = taus.tolist()
res["gamma"] = gammas.tolist()
res["gain_by_tau"] = [round(x, 3) for x in gains]
res["power_grid"] = np.round(grid, 4).tolist()

# where is the experiment adequately powered?
ok = grid >= 0.80
res["frac_of_grid_powered"] = round(float(ok.mean()), 4)
# minimum gamma reaching 0.8 at the base-case tau_down
i_base = int(np.argmin(np.abs(taus - BASE["tau_down_d"])))
j = np.where(grid[i_base, :] >= 0.80)[0]
res["gamma_needed_at_base_tau"] = float(gammas[j[0]]) if j.size else None
# minimum tau_down reaching 0.8 at full transmission
j_full = int(np.argmin(np.abs(gammas - 1.0)))
i = np.where(grid[:, j_full] >= 0.80)[0]
res["tau_needed_at_gamma1"] = float(taus[i[0]]) if i.size else None
# the rat-PET-like corner: adaptation reverses within about a day
i_pet = int(np.argmin(np.abs(taus - 0.5)))
res["power_at_pet_corner"] = {"tau_down_d": float(taus[i_pet]),
                              "gamma_1": round(float(grid[i_pet, j_full]), 4)}

print("\npowered over %.0f%% of the swept (tau_down, gamma) plane"
      % (100 * res["frac_of_grid_powered"]))
print("at the base-case decay (%.0f d), gamma must exceed %s for 80%% power"
      % (BASE["tau_down_d"], res["gamma_needed_at_base_tau"]))
print("at full transmission (gamma = 1), decay must exceed %s d"
      % res["tau_needed_at_gamma1"])
print("in the rat-PET-like corner (decay %.2f d, gamma = 1) power is %.3f"
      % (res["power_at_pet_corner"]["tau_down_d"],
         res["power_at_pet_corner"]["gamma_1"]))

# ============================================== 2. elasticity of the modelled gain
# proportional change in gain per proportional change in each assumption, taken
# symmetrically about the base case
PERTURB = {"ki_uM": 0.25, "rmax": 0.25, "tau_up_d": 0.25, "tau_down_d": 0.25,
           "hill": 0.25, "tau_theta_h": 0.25, "seiz_uM": 0.25}
base_gain = M.gain_of(M.simulate("water", BASE))
res["base_gain"] = round(base_gain, 3)
elas = []
print("\ncomputing elasticities about the base case (gain %.2f%%)..." % base_gain)
for k, frac in PERTURB.items():
    lo = M.gain_of(M.simulate("water", dict(BASE, **{k: BASE[k] * (1 - frac)})))
    hi = M.gain_of(M.simulate("water", dict(BASE, **{k: BASE[k] * (1 + frac)})))
    e = ((hi - lo) / base_gain) / (2 * frac)
    elas.append({"parameter": k, "low": round(lo, 3), "high": round(hi, 3),
                 "elasticity": round(float(e), 3)})
    print("   %-14s %6.2f -> %6.2f   elasticity %+.3f" % (k, lo, hi, e))
elas.sort(key=lambda r: -abs(r["elasticity"]))
res["elasticity"] = elas
res["dominant_assumption"] = elas[0]["parameter"]

json.dump(res, open(os.path.join(HERE, "design_regime_results.json"), "w"), indent=1)
print("\ndominant assumption: %s" % res["dominant_assumption"])
print("wrote design_regime_results.json")
