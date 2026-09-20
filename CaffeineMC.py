#!/usr/bin/env python3
"""
CaffeineMC -- single-file Monte Carlo framework for chronic caffeine titration in mice.

Question: IF chronic sub-convulsive caffeine exposure induces a slowly developing, reversible
increase in A1 adenosine receptor (A1R) availability, which delivery mode (continuous drinking
water, intermittent SC "shots", or a sustained-release depot) and which washout schedule best
reveals it, at what safety cost, and with how many animals?

Layers
  1. Per-animal stochastic PK -> receptor occupancy -> slow A1R adaptation model with EEG-style
     weekly gating (step back / cap / humane-endpoint removal). Common random numbers across
     regimens: virtual animal j has the same physiology under every regimen.
  2. Trial-level Monte Carlo: resamples virtual animals into experiments and estimates power
     and type I error for the PTZ-threshold and A1R-binding endpoints.
  3. Sensitivity suite: occupancy constant (Ki), maximum adaptation, up/down time constants,
     Hill steepness, convulsive threshold, and transmission of receptor change to seizure threshold.

IMPORTANT: this is a planning model, not evidence. Adaptation parameters are ASSUMPTIONS; the
model assumes the mechanism it explores. Only the pharmacokinetic parameters are anchored to a
primary source (CD-1 mouse: t1/2 1.25-1.62 h, Vd 0.88-1.16 L/kg; Kaplan et al., Br J Pharmacol
1990;100:435-440). The closest in-vivo test of persistence (rat PET, 30 mg/kg/day for 12 weeks;
Nabbi-Schroeter et al., Mol Imaging Biol 2018;20:284-291) found A1R availability back at baseline
about 27 h after withdrawal, i.e. it favours the fast-reversal scenarios in the sensitivity suite.

Quick start
  pip install numpy scipy matplotlib
  python CaffeineMC.py --demo         # ~1 min self-test with small N
  python CaffeineMC.py --reproduce    # full run: figures + results.json (fixed seed 20260919)
"""
import argparse, json, os, time
import numpy as np
from scipy import stats
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

MW = 194.19                       # g/mol; mg/L -> uM: x / 0.19419
LEVELS = np.array([5.0, 10.0, 15.0, 22.5, 30.0])   # target mg/kg/day (Table 2 of manuscript)

P0 = dict(
    n=2000, seed=20260919,
    t_half_h=1.4, cv_thalf=0.25,           # elimination half-life (h); CD-1 mouse 1.25-1.62 (Kaplan 1990)
    vd=1.00, cv_vd=0.15,                   # L/kg; CD-1 mouse 0.88-1.16 (Kaplan 1990)
    ka_gut=3.0, ka_sc=1.5,                 # 1/h absorption (water / SC solution)
    ka_burst=1.0, burst_frac=0.10, depot_t_half_d=3.0,   # depot: burst + slow release
    dark_frac=0.85, cv_intake=0.15, cv_daily=0.20,       # drinking pattern
    ki_uM=25.0, tau_theta_h=24.0, theta50=0.15, hill=2.0,  # apparent Ki, occupancy filter, Hill drive
    rmax=0.30, cv_rmax=0.30,               # max fractional A1R up-regulation (median, CV)
    tau_up_d=14.0, tau_down_d=7.0, cv_tau=0.25,
    seiz_uM=400.0, cv_seiz=0.30, flag_frac=0.5,   # ASSUMED convulsive plasma threshold (uM); EEG flag at 50 %
    treat_weeks=12, horizon_d=112, test_day=86, dt=0.1,
    washout="taper",                         # 'taper' (15 -> 5 -> 0 in weeks 11-12) or 'abrupt' (full dose to day 84, then stop)
)

def lognorm(rng, n, median, cv):
    s = np.sqrt(np.log(1 + cv**2))
    return median * np.exp(rng.normal(0, s, n))

def dose_of_week(L, w, abrupt=False):
    base = LEVELS[L]
    if abrupt: return base if w < 12 else np.zeros_like(base)
    if w < 10:  return base
    if w == 10: return np.minimum(15.0, base)
    if w == 11: return np.minimum(5.0, base)
    return np.zeros_like(base)

def simulate(regimen, p, rmax=None, seiz_scale=1.0):
    """regimen in {'vehicle','water','shots','depot'}. Returns dict of per-animal outputs."""
    p = dict(p); rmax = p["rmax"] if rmax is None else rmax
    n, dt = p["n"], p["dt"]
    rng = np.random.default_rng(p["seed"])            # identical draws for every regimen
    ke = np.log(2) / lognorm(rng, n, p["t_half_h"], p["cv_thalf"])
    vd = lognorm(rng, n, p["vd"], p["cv_vd"])
    intake = lognorm(rng, n, 1.0, p["cv_intake"])
    seiz = lognorm(rng, n, p["seiz_uM"] * seiz_scale, p["cv_seiz"])
    rmx = lognorm(rng, n, rmax, p["cv_rmax"]) if rmax > 0 else np.zeros(n)
    tau_up = lognorm(rng, n, p["tau_up_d"] * 24, p["cv_tau"])
    tau_dn = lognorm(rng, n, p["tau_down_d"] * 24, p["cv_tau"])
    for a in (ke, vd, intake, seiz, rmx, tau_up, tau_dn):   # animal 0 = "typical" animal
        a[0] = np.median(a) if a is not ke else np.log(2) / p["t_half_h"]
    flag = p["flag_frac"] * seiz
    rng2 = np.random.default_rng(p["seed"] + 1)       # stochastic intake noise (per regimen-independent stream)

    T = int(p["horizon_d"] * 24 / dt); wk_steps = int(168 / dt)
    G = np.zeros(n); S = np.zeros(n); C = np.zeros(n)
    thb = np.zeros(n); R = np.ones(n)
    L = np.zeros(n, int); consec = np.zeros(n, int)
    capped = np.zeros(n, bool); removed = np.zeros(n, bool)
    wkmax = np.zeros(n); wkmax_hist = np.zeros((n, p["treat_weeks"])); L_hist = np.zeros((n, p["treat_weeks"]), int)
    ab_ = p["washout"] == "abrupt"
    level = np.zeros(n) if regimen == "vehicle" else dose_of_week(L, 0, ab_)
    noise = lognorm(rng2, n, 1.0, p["cv_daily"])
    ka_gut, ka_sc, kb = p["ka_gut"], p["ka_sc"], p["ka_burst"]
    kr = np.log(2) / (p["depot_t_half_d"] * 24)
    ex = lambda k: np.exp(-k * dt)
    eke = np.exp(-ke * dt)
    shot_steps = {}; depot_steps = {}
    for d in range(p["treat_weeks"] * 7):
        if d % 7 in (0, 2, 4): shot_steps[int((d * 24 + 9) / dt)] = d // 7
    for j in range(6): depot_steps[int(j * 336 / dt)] = j * 2
    Rhist, trace = [], []
    test_step = int(p["test_day"] * 24 / dt)
    R_test = C_test = None
    rec = int(12 / dt)
    for s in range(T):
        t = s * dt; w = int(t // 168)
        if s % int(24 / dt) == 0 and s > 0: noise = lognorm(rng2, n, 1.0, p["cv_daily"])
        active = (~removed)
        if regimen == "water" and w < p["treat_weeks"]:
            h = t % 24
            rate = level * intake * noise * ((p["dark_frac"] / 12) if h >= 12 else ((1 - p["dark_frac"]) / 12)) / 1.0
            G += rate * dt * active
        elif regimen == "shots" and s in shot_steps and w < p["treat_weeks"]:
            G += level * 7 / 3 * active     # SC solution bolus, absorbed with ka_sc
        elif regimen == "depot" and s in depot_steps:
            dose = 14 * dose_of_week(L, w, ab_) * active
            G += p["burst_frac"] * dose; S += (1 - p["burst_frac"]) * dose
        if regimen == "shots":
            ab = G * (1 - ex(ka_sc)); G -= ab
        elif regimen == "depot":
            ab = G * (1 - ex(kb)); G -= ab
            rel = S * (1 - ex(kr)); S -= rel; ab = ab + rel
        else:
            ab = G * (1 - ex(ka_gut)); G -= ab
        C = C * eke + ab / vd
        mu = C / 0.19419
        ev = (mu > seiz) & active
        if ev.any(): removed |= ev; level = np.where(ev, 0.0, level); G[ev] = 0; S[ev] = 0
        wkmax = np.maximum(wkmax, np.where(active, mu, 0))
        occ = mu / (mu + p["ki_uM"]); thb += (occ - thb) * dt / p["tau_theta_h"]
        Rt = 1 + rmx * thb**p["hill"] / (thb**p["hill"] + p["theta50"]**p["hill"])
        R += (Rt - R) * dt / np.where(Rt > R, tau_up, tau_dn)
        if s % rec == 0: Rhist.append(R.copy())
        if s % 5 == 0: trace.append(mu[0])
        if s == test_step: R_test = R.copy(); C_test = mu.copy()
        if (s + 1) % wk_steps == 0:
            wi = (s + 1) // wk_steps - 1
            if wi < p["treat_weeks"]:
                wkmax_hist[:, wi] = wkmax; L_hist[:, wi] = L
                if regimen != "vehicle":
                    breach = (wkmax > flag) & active
                    consec = np.where(breach, consec + 1, 0); capped |= consec >= 2
                    Ln = np.where(breach, np.maximum(L - 1, 0), L)
                    stepb = ((wi + 1) % 2 == 0) and (wi + 1) < 10
                    if stepb: Ln = np.where(~breach & ~capped, np.minimum(L + 1, 4), Ln)
                    L = Ln; level = dose_of_week(L, wi + 1, ab_) * active
            wkmax = np.zeros(n)
    Rhist = np.array(Rhist).T        # (n, steps/12h)
    return dict(regimen=regimen, R_test=R_test, C_test=C_test, removed=removed, capped=capped,
                flagged=(wkmax_hist > flag[:, None]).any(1), wkmax_hist=wkmax_hist, L_hist=L_hist,
                Rhist=Rhist, trace=np.array(trace), seiz=seiz, flag=flag, params=p)

def summarize(o):
    p = o["params"]; keep = ~o["removed"]; wk = o["wkmax_hist"]
    R = o["R_test"][keep]; Rh = o["Rhist"][keep]
    d_end = int(84 * 2)                       # index at 12 h resolution
    excess = Rh[:, d_end] - 1 if Rh.shape[1] > d_end else np.zeros(keep.sum())
    tail = Rh[:, d_end:] - 1
    with np.errstate(divide="ignore", invalid="ignore"):
        half = np.array([(np.argmax(tr <= 0.5 * e) / 2.0 if e > 1e-3 and (tr <= 0.5 * e).any() else np.nan) for tr, e in zip(tail, excess)])
    pk = wk[:, 8:10].max(1)[keep]                     # highest weekly peak, maintenance weeks 9-10
    return dict(regimen=o["regimen"], n=int(len(o["removed"])),
        R_test_mean=float(np.mean(R)), R_test_p5=float(np.percentile(R, 5)), R_test_p95=float(np.percentile(R, 95)),
        pct_R_gain_mean=float(100 * (np.mean(R) - 1)),
        pct_flag=float(100 * o["flagged"].mean()), pct_removed=float(100 * o["removed"].mean()),
        pct_capped=float(100 * o["capped"].mean()),
        pct_reach_top=float(100 * (o["L_hist"][:, 9][keep] == 4).mean()),
        peak_maint_uM_median=float(np.median(pk)), peak_maint_uM_p95=float(np.percentile(pk, 95)),
        residual_uM_test_median=float(np.median(o["C_test"][keep])),
        halflife_excess_days_median=float(np.nanmedian(half)))

# ---------------- trial-level Monte Carlo ----------------
def power(Rpool, gamma, n_per_sex, nsim, rng=None, endpoint="ptz", sd_ptz=0.18, sd_a1r=0.12, sex_eff=0.10, seed=20260919):
    """Monte Carlo power (or type I error at gamma=0). Deterministic: the noise stream is re-seeded on every call,
    so identical inputs always give identical output and every table/figure quotes the same number."""
    rng = np.random.default_rng(seed + (0 if endpoint == "ptz" else 1))
    n = n_per_sex
    sex = np.tile(np.r_[np.zeros(n), np.ones(n)], 2); grp = np.r_[np.zeros(2 * n), np.ones(2 * n)]
    X = np.c_[np.ones(4 * n), grp, sex]; XtXi = np.linalg.inv(X.T @ X); H = XtXi @ X.T
    Rg = np.ones((2 * n, nsim)); Rc = rng.choice(Rpool, size=(2 * n, nsim), replace=True)
    Rall = np.vstack([Rg, Rc])
    if endpoint == "ptz":
        y = np.log(1 + gamma * (Rall - 1)) + np.log(1 - sex_eff * sex)[:, None] + rng.normal(0, sd_ptz, Rall.shape)
    else:
        y = np.log(Rall) + rng.normal(0, sd_a1r, Rall.shape)
    beta = H @ y; res = y - X @ beta; df = 4 * n - 3
    se = np.sqrt((res**2).sum(0) / df * XtXi[1, 1]); tt = beta[1] / se
    pv = 2 * stats.t.sf(np.abs(tt), df)
    return float((pv < 0.05).mean())

# ---------------- figures ----------------
COL = dict(water="#0072B2", shots="#D55E00", depot="#009E73", vehicle="#666666")
LAB = dict(water="Continuous (drinking water)", shots="SC shots 3x/week", depot="Depot every 14 d")

def _style():
    plt.rcParams.update({"font.size": 9, "axes.spines.top": False, "axes.spines.right": False, "font.family": "DejaVu Sans"})

def fig_concept(out):
    """Figure 1: conceptual framework (no simulation)."""
    from matplotlib.patches import FancyBboxPatch, FancyArrowPatch
    _style(); fig, ax = plt.subplots(figsize=(9.2, 5.4)); ax.set_xlim(0, 100); ax.set_ylim(0, 58); ax.axis("off")
    def box(x, y, w, h, t, fc, fs=8, bold=False):
        ax.add_patch(FancyBboxPatch((x, y), w, h, boxstyle="round,pad=0.3,rounding_size=1.2", fc=fc, ec="#444", lw=0.8))
        ax.text(x + w / 2, y + h / 2, t, ha="center", va="center", fontsize=fs, fontweight="bold" if bold else "normal")
    def arr(x1, y1, x2, y2): ax.add_patch(FancyArrowPatch((x1, y1), (x2, y2), arrowstyle="-|>", mutation_scale=10, lw=1, color="#333"))
    box(24, 51, 52, 6, "Chronic escalating sub-convulsive caffeine (EEG-gated)", "#DCE9F5", 8.5, True)
    arr(50, 51, 50, 47.5)
    box(30, 42, 40, 5, "Homeostatic adaptation", "#DCE9F5", 8.5, True)
    for x, t in ((6, "A₁R density"), (38, "A₁R coupling"), (70, "Adenosine tone")):
        box(x, 31, 24, 6, t, "#EAF2FA"); arr(50, 42, x + 12, 37.6)
    arr(50, 31, 50, 27.5)
    box(30, 22, 40, 5, "Caffeine withdrawal", "#F5E6C8", 8.5, True)
    for x, t, fc in ((6, "A: threshold ↑\n(adenosinergic reserve)", "#D5EDD8"), (38, "B: threshold ↓\n(rebound excitability)", "#F6D5D5"), (70, "C: threshold unchanged\n(reversible / no effect)", "#E6E6E6")):
        box(x, 10.5, 24, 6.5, t, fc); arr(50, 22, x + 12, 17.4)
    ax.text(50, 6.2, "Measured by: PTZ threshold · A₁R PET / binding · synaptic function · LC-MS/MS (caffeine + metabolites) · G3 (caffeine continued)", ha="center", fontsize=7.5)
    ax.plot([6, 94], [3.6, 3.6], color="#888", lw=0.8)
    for x, t in ((10, "4-6 h: residual drug"), (33, "24 h: transition"), (57, "48 h: primary test"), (81, "96 h: persistence / reversal")):
        ax.text(x, 1.3, t, fontsize=7.5, ha="left", color="#333")
    fig.tight_layout(); fig.savefig(os.path.join(out, "Fig1_concept.png"), dpi=300); plt.close(fig)

def fig_exposure_adaptation(runs, out):
    _style()
    fig, ax = plt.subplots(1, 2, figsize=(9.2, 3.6))
    for k in ("water", "shots", "depot"):
        tr = runs[k]["trace"]; x = np.arange(len(tr)) * 5 * runs[k]["params"]["dt"] / 24
        m = (x >= 63) & (x <= 68.9); ax[0].plot(x[m], tr[m], color=COL[k], lw=1.1, label=LAB[k])
    fl = np.median(runs["shots"]["flag"]); ax[0].axhline(fl, color="k", ls="--", lw=.8); ax[0].text(63.05, fl * 1.08, "median EEG-flag level (assumed)", fontsize=7)
    ax[0].set_yscale("log"); ax[0].set_ylim(0.5, 900); ax[0].set_xlabel("Day of study"); ax[0].set_ylabel("Modelled plasma caffeine (µM)")
    ax[0].set_title("Typical virtual mouse, maintenance weeks 9-10", fontsize=9, loc="left"); ax[0].legend(frameon=False, fontsize=7, loc="lower left")
    for k in ("water", "shots", "depot"):
        keep = ~runs[k]["removed"]; Rh = runs[k]["Rhist"][keep]; x = np.arange(Rh.shape[1]) / 2
        ax[1].plot(x, Rh.mean(0), color=COL[k], lw=1.6, label=LAB[k])
        ax[1].fill_between(x, np.percentile(Rh, 5, 0), np.percentile(Rh, 95, 0), color=COL[k], alpha=.12, lw=0)
    ka = runs["water_abrupt"]; Rh = ka["Rhist"][~ka["removed"]]; x = np.arange(Rh.shape[1]) / 2
    ax[1].plot(x, Rh.mean(0), color=COL["water"], lw=1.4, ls="--", label="Continuous, abrupt stop")
    ax[1].axhline(1, color=COL["vehicle"], lw=1, ls=":"); ax[1].axvline(86, color="k", lw=.7)
    ax[1].set_xlabel("Day of study"); ax[1].set_ylabel("Modelled A₁R density (vehicle = 1)"); ax[1].legend(frameon=False, fontsize=7, loc="upper left")
    ax[1].set_title("Modelled adaptation (assumed parameters)", fontsize=9, loc="left")
    for a_, l in zip(ax, "AB"): a_.text(-0.12, 1.08, l, transform=a_.transAxes, fontweight="bold", fontsize=11)
    fig.tight_layout(); fig.savefig(os.path.join(out, "Fig2_exposure_adaptation.png"), dpi=300); plt.close(fig)

def fig_sensitivity(suite, out):
    _style(); fig, ax = plt.subplots(1, 2, figsize=(9.2, 3.6))
    td = suite["tau_down_days"]
    for k, c, ls, lab in (("water_abrupt", COL["water"], "-", "Continuous, abrupt stop"), ("water_taper", COL["water"], "--", "Continuous, 2-week taper"), ("shots_abrupt", COL["shots"], "-", "SC shots, abrupt stop")):
        ax[0].plot(td, suite["tau_down_gain"][k], color=c, ls=ls, marker="o", ms=3.5, lw=1.5, label=lab)
    ax[0].set_xscale("log"); ax[0].set_xticks(td); ax[0].set_xticklabels([str(t) for t in td]); ax[0].axvline(1, color="#888", lw=.7, ls=":")
    ax[0].set_xlabel("Assumed receptor decay time constant after last dose (days)"); ax[0].set_ylabel("Modelled A₁R gain at day 86 (%)")
    ax[0].set_title("Persistence assumption dominates", fontsize=9, loc="left"); ax[0].legend(frameon=False, fontsize=7)
    g = suite["gamma"]
    for rm, c in ((0.1, "#CC79A7"), (0.3, "#0072B2"), (0.5, "#009E73")):
        ax[1].plot(g, suite["power_gamma"][str(rm)], color=c, marker="o", ms=3.5, lw=1.5, label=f"Rmax {rm}")
    ax[1].axhline(.8, color="k", lw=.7, ls=":"); ax[1].axhline(.05, color="k", lw=.7, ls=":")
    ax[1].set_xlabel("γ: fraction of receptor gain transmitted to PTZ threshold"); ax[1].set_ylabel("Power, 12 per sex per group")
    ax[1].set_ylim(0, 1.02); ax[1].set_title("γ = 0 gives the type I error", fontsize=9, loc="left"); ax[1].legend(frameon=False, fontsize=7, loc="upper left")
    for a_, l in zip(ax, "AB"): a_.text(-0.12, 1.08, l, transform=a_.transAxes, fontweight="bold", fontsize=11)
    fig.tight_layout(); fig.savefig(os.path.join(out, "Fig3_sensitivity.png"), dpi=300); plt.close(fig)

# ---------------- sensitivity suite ----------------
def gain_of(o): return float(100 * (np.mean(o["R_test"][~o["removed"]]) - 1))

def sensitivity_suite(p, nsim):
    """Same n, seed and nsim as the headline runs, so the base-case row reproduces the headline numbers exactly."""
    pa = dict(p, washout="abrupt"); pt = dict(p, washout="taper"); rng = None
    rows = []
    def scen(label, **kw):
        q = {k: v for k, v in kw.items() if k in P0}; rm = kw.get("rmax")
        w = simulate("water", dict(pa, **q)); sh = simulate("shots", dict(pa, **q)); dp = simulate("depot", dict(pa, **q))
        pool = w["R_test"][~w["removed"]]
        rows.append(dict(label=label, water=gain_of(w), shots=gain_of(sh), depot=gain_of(dp), water_taper=gain_of(simulate("water", dict(pt, **q))),
                         ptz_g1=power(pool, 1.0, 12, nsim, rng), ptz_g05=power(pool, 0.5, 12, nsim, rng), a1r=power(pool, 1.0, 10, nsim, rng, "a1r"),
                         flag_shots=float(100 * sh["flagged"].mean())))
    scen("Base case")
    for ki in (10.0, 50.0): scen(f"Ki = {ki:g} µM", ki_uM=ki)
    for rm in (0.1, 0.2, 0.5): scen(f"Rmax = {rm}", rmax=rm)
    for tu in (7.0, 28.0): scen(f"Up-regulation tau = {tu:g} d", tau_up_d=tu)
    for td in (0.5, 1.0, 3.0, 14.0): scen(f"Decay tau = {td:g} d", tau_down_d=td)
    for h in (1.0, 4.0): scen(f"Hill n = {h:g}", hill=h)
    scen("Fast reversal (6-h occupancy window, decay 0.5 d)", tau_theta_h=6.0, tau_down_d=0.5)   # closest to rat PET: baseline by ~27 h
    # curves for the figure
    tds = [0.5, 1.0, 3.0, 7.0, 14.0]; tg = {"water_abrupt": [], "water_taper": [], "shots_abrupt": []}
    for td in tds:
        tg["water_abrupt"].append(gain_of(simulate("water", dict(pa, tau_down_d=td))))
        tg["water_taper"].append(gain_of(simulate("water", dict(pt, tau_down_d=td))))
        tg["shots_abrupt"].append(gain_of(simulate("shots", dict(pa, tau_down_d=td))))
    gam = [0.0, 0.25, 0.5, 1.0]; pg = {}
    for rm in (0.1, 0.3, 0.5):
        pool = simulate("water", dict(pa, rmax=rm))["R_test"]; pg[str(rm)] = [power(pool, g, 12, nsim, rng) for g in gam]
    return dict(rows=rows, tau_down_days=tds, tau_down_gain=tg, gamma=gam, power_gamma=pg)

def run_all(out="mc_out", n=2000, nsim=4000, seed=20260919, overrides=None):
    os.makedirs(out, exist_ok=True); t0 = time.time()
    p = dict(P0, n=n, seed=seed, **(overrides or {})); pa = dict(p, washout="abrupt")
    json.dump(p, open(os.path.join(out, "params.json"), "w"), indent=1)
    runs = {k: simulate(k, p) for k in ("water", "shots", "depot")}
    runs["water_abrupt"] = simulate("water", pa)
    summ = {k: summarize(runs[k]) for k in runs}
    for k in ("shots", "depot"): summ[k + "_abrupt"] = summarize(simulate(k, pa))
    sens = {}                                   # safety vs the (assumed) convulsive threshold
    for sc in (0.5, 1.0, 2.0):
        for k in ("water", "shots", "depot"):
            o = runs[k] if sc == 1.0 else simulate(k, p, seiz_scale=sc)
            sens[f"{k}|{sc}"] = dict(pct_flag=float(100 * o["flagged"].mean()), pct_removed=float(100 * o["removed"].mean()), R_gain=gain_of(o))
    rng = np.random.default_rng(seed + 7)
    pools = {}
    for mode in ("taper", "abrupt"):
        pools[(mode, 0.0)] = np.ones(10)
        for rm in (0.1, 0.3, 0.5):
            o = (runs["water"] if mode == "taper" else runs["water_abrupt"]) if rm == 0.3 else simulate("water", dict(p, washout=mode), rmax=rm)
            pools[(mode, rm)] = o["R_test"][~o["removed"]]
    grid = {}
    for (mode, rm), pool in pools.items():
        for g in (0.5, 1.0):
            grid[f"{mode}|Rmax={rm}|gamma={g}"] = dict(ptz=power(pool, g, 12, nsim, rng, "ptz"), a1r=power(pool, g, 10, nsim, rng, "a1r"), R_mean=float(pool.mean()))
    ns = list(range(4, 41, 3)); curve = {}
    for lab, mode, rm, g in (("Rmax 0.3, γ = 1.0", "abrupt", .3, 1.0), ("Rmax 0.3, γ = 1.0 (taper)", "taper", .3, 1.0), ("Rmax 0.5, γ = 1.0", "abrupt", .5, 1.0)):
        curve[lab] = [power(pools[(mode, rm)], g, k, nsim, rng, "ptz") for k in ns]
    need = {lab: next((k for k, v in zip(ns, vs) if v >= .8), None) for lab, vs in curve.items()}
    pw = dict(grid=grid, curve_n=ns, curve=curve, n_for_80=need)
    suite = sensitivity_suite(p, nsim)
    fig_concept(out); fig_exposure_adaptation(runs, out); fig_sensitivity(suite, out)
    res = dict(summary=summ, sensitivity=sens, suite=suite, power=pw, params=p, runtime_s=round(time.time() - t0, 1))
    json.dump(res, open(os.path.join(out, "results.json"), "w"), indent=1, default=float)
    return res

if __name__ == "__main__":
    ap = argparse.ArgumentParser(); ap.add_argument("--demo", action="store_true"); ap.add_argument("--reproduce", action="store_true")
    ap.add_argument("--out", default="mc_out"); ap.add_argument("--params", help="JSON file overriding default parameters (see params.json written to the output folder)"); ap.add_argument("--seed", type=int, default=20260919)
    a = ap.parse_args()
    ov = json.load(open(a.params)) if a.params else None
    ov = {k: v for k, v in (ov or {}).items() if k not in ("n", "seed")}
    r = run_all(a.out, n=300 if a.demo else 2000, nsim=500 if a.demo else 4000, seed=a.seed, overrides=ov)
    print(json.dumps(r["summary"], indent=1)); print("runtime (s):", r["runtime_s"])
