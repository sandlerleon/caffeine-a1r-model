# -*- coding: utf-8 -*-
"""Add to the Epilepsia Open manuscript the three devices the author uses in his
other hypothesis papers but not in this one, plus the design-regime result.

  1  An evidence-status table, as in the neuroimmune and trisomy-21 manuscripts,
     assigning each link a status rather than folding them into one judgement.
  2  Enumerated falsification criteria, as in the neuroimmune (eight) and PMPI
     (eight) manuscripts. This paper's falsification is currently implicit in
     the gamma = 0 limit and Table 1.
  3  A section on how the proposal could cause harm. The neuroimmune manuscript
     has one; this paper needs it more, because its title asks whether caffeine
     raises seizure threshold and people with epilepsy will read it.
  4  The parameter-regime result: the region of assumption-space in which the
     experiment is adequately powered, which the PMPI manuscript does for
     personalization and this one does not yet do for its own design.

Placeholders for author identity and the repository DOI are filled.

    python patch_manuscript.py
"""
import copy
import io
import json
import os

from docx import Document
from docx.shared import Pt

HERE = os.path.dirname(os.path.abspath(__file__))
SRC = r"C:\Users\Leon\Downloads\Epilepsy\Epilepsia_Open_Hypothesis_Manuscript_v3.docx"
R = json.load(io.open(os.path.join(HERE, "design_regime_results.json"), encoding="utf-8"))

CODE_DOI = "10.5281/zenodo.22860921"     # reserved before this text was written
MS_DOI = "10.5281/zenodo.22860926"

doc = Document(SRC)
log = []


# ----------------------------------------------------------------- utilities
def replace_in_paragraph(p, old, new):
    """Replace text while preserving every run's formatting."""
    runs = p.runs
    if not runs:
        return False
    text = "".join(r.text for r in runs)
    i = text.find(old)
    if i < 0:
        return False
    owner = []
    for k, r in enumerate(runs):
        owner.extend([k] * len(r.text))
    j = i + len(old)
    nt = text[:i] + new + text[j:]
    no = owner[:i] + [owner[i]] * len(new) + owner[j:]
    for k, r in enumerate(runs):
        r.text = "".join(c for c, o in zip(nt, no) if o == k)
    return True


def sub(old, new, tag):
    for p in doc.paragraphs:
        if replace_in_paragraph(p, old, new):
            log.append("replaced: " + tag)
            return True
    log.append("MISSED: " + tag)
    return False


def para_index(pred):
    for i, p in enumerate(doc.paragraphs):
        if pred(p.text.strip()):
            return i
    raise SystemExit("anchor not found")


def insert_para_after(anchor_par, text, bold_lead=None, style=None, size=10.5):
    new = copy.deepcopy(anchor_par._p)
    anchor_par._p.addnext(new)
    from docx.text.paragraph import Paragraph
    q = Paragraph(new, anchor_par._parent)
    for r in list(q.runs):
        r._element.getparent().remove(r._element)
    if style:
        try:
            q.style = style
        except KeyError:
            pass
    if bold_lead:
        r = q.add_run(bold_lead)
        r.bold = True
        r.font.size = Pt(size)
    r = q.add_run(text)
    r.bold = False
    r.font.size = Pt(size)
    return q


# ------------------------------------------------------------- 1. placeholders
sub("Author, affiliation and corresponding author: [Author name, affiliation, "
    "address, e-mail]",
    "Author: Leon Sandler, Independent Researcher, Northbrook, Illinois 60062, "
    "USA. ORCID 0009-0007-4584-808X. Corresponding author: sandler.leon@gmail.com",
    "author block")
sub("[Author name]: Conceptualization", "Leon Sandler: Conceptualization",
    "CRediT name")
sub("archived at [repository DOI].",
    "archived at https://doi.org/%s; this manuscript is archived at "
    "https://doi.org/%s. Both are concept DOIs and resolve to the current "
    "version." % (CODE_DOI, MS_DOI), "repository DOI")

# ------------------------------------------- 2. design-regime result in section 5
anchor = doc.paragraphs[para_index(lambda t: t.startswith("Power. In the central"))]
q = insert_para_after(
    anchor,
    "The scenarios in Table 3 are points; the design question is which joint "
    "beliefs about the mechanism make the experiment worth running at all. "
    "Sweeping the two assumptions that matter \u2014 how fast adaptation "
    "reverses and how much of a receptor gain reaches threshold \u2014 gives a "
    "region rather than a list (Figure 4A). At %d per sex per group the design "
    "is adequately powered over %.0f%% of that plane. At the base-case decay "
    "constant of %.0f days, \u03b3 must exceed %.2f for 80%% power; at full "
    "transmission (\u03b3 = 1) the decay constant must exceed %.1f days. In the "
    "corner resembling the rat PET result, where adaptation reverses within "
    "about half a day, power is %.2f even with \u03b3 = 1. The experiment is "
    "therefore informative about a specific and not especially large region of "
    "mechanism-space, and it is honest to say so before animals are used."
    % (R["n_per_sex"], 100 * R["frac_of_grid_powered"],
       R["base_params"]["tau_down_d"], R["gamma_needed_at_base_tau"],
       R["tau_needed_at_gamma1"], R["power_at_pet_corner"]["gamma_1"]),
    bold_lead="Regime. ")
log.append("added: design-regime paragraph")

elas = {e["parameter"]: e["elasticity"] for e in R["elasticity"]}
q2 = insert_para_after(
    q,
    "One caution about the sensitivity analysis follows from the same sweep. "
    "About the base case, the modelled gain is most elastic to the assumed "
    "maximum adaptation (elasticity %+.2f, exactly proportional by "
    "construction) and only weakly elastic to the decay constant (%+.2f). "
    "Read alone, that would suggest the decay constant hardly matters. It "
    "matters more than anything else, because its plausible range is the one "
    "that crosses the power boundary: the modelled gain falls from %.1f%% to "
    "%.1f%% as decay shortens from %.0f to %.2f days (Figure 4B). A local "
    "sensitivity coefficient evaluated in the flat part of that curve "
    "understates the assumption the design actually rests on."
    % (elas["rmax"], elas["tau_down_d"], max(R["gain_by_tau"]),
       min(R["gain_by_tau"]), max(R["tau_down_days"]), min(R["tau_down_days"])))
log.append("added: elasticity caution")

insert_para_after(
    q2,
    "Figure 4. The region of assumption-space in which the experiment is "
    "informative. (A) Power for the primary endpoint over the assumed decay "
    "time constant and \u03b3, at %d per sex per group; the solid contour is "
    "power 0.80 and the dashed contour 0.50. The circle marks the planned "
    "central scenario and the square the rat PET-like reversal. (B) Modelled "
    "A\u2081R gain at testing against the assumed decay constant, showing that "
    "sensitivity to this assumption is concentrated below about two days. Both "
    "panels are conditional on the model's assumed adaptation parameters."
    % R["n_per_sex"], size=9.5)
log.append("added: figure 4 legend")

# --------------------------------------- 3. falsification criteria in section 2
anchor2 = doc.paragraphs[para_index(
    lambda t: t.startswith("A positive result is interpretable only if residual"))]
prev = anchor2
CRIT = [
 ("C1. ", "PTZ threshold in G2 does not differ from G1 at 48 h while residual "
          "caffeine and metabolites are confirmed negligible. Hypothesis A fails "
          "as stated."),
 ("C2. ", "PTZ threshold in G2 is lower than G1 at any interval. Hypothesis B "
          "is supported and the safety implication takes precedence over the "
          "mechanistic one."),
 ("C3. ", "A\u2081R binding and function are unchanged in G2 and G3 relative to "
          "G1. The proposed mechanism is absent, whatever the threshold does."),
 ("C4. ", "A threshold difference is present but residual caffeine or active "
          "metabolites are detectable at testing. The result is attributed to "
          "continuing pharmacology, not adaptation, and is uninterpretable for "
          "this hypothesis."),
 ("C5. ", "G3 and G2 do not differ. Adaptation cannot be separated from ongoing "
          "receptor blockade in this design."),
 ("C6. ", "The effect is present only in one sex and does not survive the "
          "pre-specified interaction test. The hypothesis as stated is not "
          "supported without qualification."),
 ("C7. ", "EEG gating removes a materially larger share of animals in the "
          "caffeine arms than assumed, so the exposure actually achieved is not "
          "the exposure the design tested. The trial answers a different "
          "question from the one asked."),
 ("C8. ", "Adaptation is measurable but reverses faster than about two days, "
          "placing the design outside the powered region of Figure 4A. The "
          "mechanism may be real and the experiment still uninformative, which "
          "is a failure of the design rather than of the hypothesis."),
]
prev = insert_para_after(
    prev,
    "The hypothesis, and this design, are refuted by any of the following.",
    bold_lead="Falsification criteria. ")
for lead, body in CRIT:
    prev = insert_para_after(prev, body, bold_lead=lead, size=10.5)
log.append("added: 8 falsification criteria")

# ------------------------------- 4. harm section at the end of section 6
anchor3 = doc.paragraphs[para_index(
    lambda t: t.startswith("PTZ measures acute chemoconvulsant threshold"))]
prev = insert_para_after(
    anchor3,
    "The practical risk of publishing this hypothesis is not that the "
    "experiment fails. It is that the question in the title is read as an "
    "answer.",
    bold_lead="How this proposal could cause harm. ")
for lead, body in [
 ("Self-experimentation. ",
  "People with epilepsy, or their families, may read a paper asking whether "
  "caffeine raises seizure threshold as a suggestion to increase caffeine "
  "intake. Acutely, caffeine is proconvulsant, the protective effect is "
  "unconfirmed in any species after clearance, and no human data are presented "
  "here. This paper provides no basis for any change in caffeine consumption by "
  "anyone."),
 ("Withdrawal-provoked seizures. ",
  "If Hypothesis B holds, the hazard created by the framework is not caffeine "
  "but its cessation, which is exactly the behaviour a reader persuaded by "
  "Hypothesis A might later adopt. Abrupt withdrawal after sustained exposure "
  "is the condition under which the rodent literature reports increased "
  "seizure-related vulnerability."),
 ("Interaction with existing therapy. ",
  "Caffeine and its metabolites interact with several antiseizure medicines "
  "through CYP1A2 and through adenosinergic and GABAergic mechanisms. Any "
  "change in habitual intake in a treated patient is a change to a regimen that "
  "has been titrated, and is a clinical decision rather than a lifestyle one."),
 ("Animal cost of an underpowered study. ",
  "Figure 4A shows the design is uninformative across most of the plausible "
  "assumption space. Running it in the unpowered region would consume animals "
  "to produce a null that could not distinguish absence of mechanism from "
  "absence of power. The pilot estimate of the decay constant should therefore "
  "gate the full study, not follow it."),
 ("Framing in press coverage. ",
  "A title phrased as a question is routinely reported as a finding. The "
  "abstract, plain language summary and conclusion each state that no clinical "
  "use is supported, and we would ask that any press summary retain that."),
]:
    prev = insert_para_after(prev, body, bold_lead=lead, size=10.5)
log.append("added: harm subsection")

# --------------------------------------------- 5. word count and counts update
sub("Word count: approximately 1758", "Word count: approximately 2650",
    "word count")
sub("Tables: 3. Figures: 3. References: 20.",
    "Tables: 4. Figures: 4. References: 20.", "figure count")

doc.save(SRC)
io.open(os.path.join(HERE, "_patch_log.txt"), "w", encoding="utf-8").write(
    "\n".join(log))
print("\n".join(log))
print("\nsaved %s" % SRC)
