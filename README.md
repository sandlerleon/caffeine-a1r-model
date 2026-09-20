# CaffeineMC

Single-file Monte Carlo planning model for chronic caffeine titration in mice. It accompanies the manuscript
"Can Chronic Caffeine Exposure Increase Adenosine A1 Receptor Reserve and Seizure Threshold? A Testable Hypothesis".

**This is a planning model, not evidence.** Only the pharmacokinetic parameters are anchored to a primary source
(CD-1 mouse; Kaplan et al., Br J Pharmacol 1990;100:435-440). All adaptation parameters are assumptions, and the model
assumes the mechanism it explores.

## Run
    pip install -r requirements.txt
    python CaffeineMC.py --demo        # small self-test (about 1 minute)
    python CaffeineMC.py --reproduce   # full run (about 2-3 minutes): figures, results.json, params.json
    python CaffeineMC.py --reproduce --params my_params.json   # override defaults (n and seed are fixed by the command line)

Fixed random seed: 20260919 (`--seed` to change). Power estimates are deterministic for a given input.

## Outputs (`example_output/`)
- `Fig1_concept.png`, `Fig2_exposure_adaptation.png`, `Fig3_sensitivity.png`
- `results.json` (all numbers quoted in the manuscript), `params.json` (parameters used)

## Regimens
Continuous drinking water; subcutaneous injections 3x/week at equal weekly exposure; 14-day sustained-release depot.
Washout schedules: 2-week taper or abrupt stop. Weekly EEG-style gating (step back, cap, humane-endpoint removal).

## Cite
See `CITATION.cff`. Archive with a DOI (for example via Zenodo) and cite that version.

## Extension: the design-regime analysis

`extension/design_regime.py` answers a question the base package does not:
**for which joint beliefs about the mechanism is this experiment worth running?**

The two assumptions that matter are how fast adaptation reverses after the last
dose and how much of a receptor gain reaches seizure threshold (gamma). Sweeping
both gives a region rather than the list of point scenarios in Table 3.

| | result |
|---|---|
| Adequately powered (>=0.80) over the swept plane | **13%** |
| gamma needed at the base-case decay of 7 d | **> 0.75** |
| decay needed at full transmission (gamma = 1) | **> 2.0 d** |
| power in the rat PET-like corner (decay 0.55 d, gamma = 1) | **0.40** |

There is also a caution about one-at-a-time sensitivity. About the base case the
modelled gain is exactly proportional to the assumed maximum adaptation
(elasticity +1.00) and only weakly elastic to the decay constant (+0.11) — which
would suggest decay hardly matters. It matters most, because its plausible range
is the one that crosses the power boundary: modelled gain falls from 23.7% to
6.4% as decay shortens from 21 to 0.25 days. A local sensitivity coefficient
evaluated in the flat part of that curve understates the assumption the design
actually rests on.

```bash
python extension/design_regime.py       # -> design_regime_results.json
python extension/make_regime_figure.py  # -> figure4_design_regime.png
```

Base-case reproduction was verified against the released package before the
extension was written: the depot arm returns a 13.15% modelled gain, matching
the manuscript's 13.2%, and the decay-0.5 d power of 0.37 in Table 3 matches the
0.40 obtained here at 0.55 d.

## Citation

Concept DOIs, which always resolve to the latest version:

- Code and model: [10.5281/zenodo.22860921](https://doi.org/10.5281/zenodo.22860921)
- Manuscript: [10.5281/zenodo.22860926](https://doi.org/10.5281/zenodo.22860926)
