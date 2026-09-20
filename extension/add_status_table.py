# -*- coding: utf-8 -*-
"""Add the evidence-status table, the one device from the author's other
hypothesis papers still missing here.

The manuscript's Tables 1-3 give predictions, groups and sensitivity. None of
them says which links in the argument are established and which are assumed, so
a reader cannot locate the weak points without reconstructing them from the
prose. The neuroimmune and trisomy-21 manuscripts both solve this with a status
column; this does the same.

It is placed in Section 6 as Table 4, so no existing table is renumbered.

    python add_status_table.py
"""
import os

from docx import Document
from docx.shared import Pt

SRC = r"C:\Users\Leon\Downloads\Epilepsy\Epilepsia_Open_Hypothesis_Manuscript_v3.docx"

ROWS = [
 ("Adenosine acting at A\u2081R contributes to seizure termination",
  "Established", "Reviewed physiology (1,2,3)"),
 ("Acute caffeine antagonises A\u2081R and is proconvulsant at high dose",
  "Established", "Pharmacology and dose-response (4,5)"),
 ("Chronic caffeine increases A\u2081R density in mouse cortex",
  "Reported", "About 20% increase in one study (6)"),
 ("Chronic methylxanthine reduces chemoconvulsant susceptibility",
  "Reported", "Bicuculline and PTZ (7); in one case without a density change (8)"),
 ("Chronic caffeine sensitises A\u2081R-adenylate cyclase coupling",
  "Reported", "Rat cerebral cortex (10)"),
 ("A\u2082A adaptation contributes to the protective effect",
  "Reported", "Receptor-knockout evidence (9)"),
 ("A\u2081R availability returns to baseline after caffeine is cleared",
  "Contested", "Rat PET found no persistent change by about 27 h (12)"),
 ("Protection survives clearance of caffeine and active metabolites",
  "Untested", "The question this design exists to answer"),
 ("Adaptation is driven by time-averaged occupancy rather than peaks",
  "Assumed", "Premise of the simulation; the injected arm would reveal the "
             "opposite ordering"),
 ("A receptor gain is transmitted to seizure threshold (\u03b3)",
  "Assumed", "Swept from 0 to 1; \u03b3 = 0 is the falsification limit"),
 ("Adaptation magnitude and reversal rate (Rmax, decay \u03c4)",
  "Assumed", "Illustrative values; the decay constant decides feasibility "
             "(Figure 4)"),
 ("Withdrawal produces rebound hyperexcitability (Hypothesis B)",
  "Open", "Indirect rodent evidence with ethanol co-exposure (20); a safety "
          "concern, not a demonstrated effect"),
]

doc = Document(SRC)

anchor = None
for p in doc.paragraphs:
    if p.text.strip().startswith("PTZ measures acute chemoconvulsant threshold"):
        anchor = p
        break
if anchor is None:
    raise SystemExit("anchor paragraph not found")

# caption first, so it ends up above the table once both are moved
cap = doc.add_paragraph()
cap.paragraph_format.space_before = Pt(8)
cap.paragraph_format.space_after = Pt(3)
r = cap.add_run("Table 4. Status of each link in the argument. \u2018Reported\u2019 "
                "denotes a published observation not independently replicated in "
                "this context; \u2018Assumed\u2019 denotes a modelling choice, not "
                "a claim about biology.")
r.italic = True
r.font.size = Pt(9)

t = doc.add_table(rows=1, cols=3)
# this document carries no named table styles, so the grid is taken from the
# tblPr of an existing table rather than assigned by name
import copy as _copy
from docx.oxml.ns import qn as _qn
src_pr = doc.tables[0]._tbl.find(_qn("w:tblPr"))
if src_pr is not None:
    old_pr = t._tbl.find(_qn("w:tblPr"))
    if old_pr is not None:
        t._tbl.remove(old_pr)
    t._tbl.insert(0, _copy.deepcopy(src_pr))
for i, h in enumerate(["Link", "Status", "Basis"]):
    c = t.rows[0].cells[i]
    c.text = ""
    c.paragraphs[0].paragraph_format.line_spacing = 1.0
    rr = c.paragraphs[0].add_run(h)
    rr.bold = True
    rr.font.size = Pt(8.5)
for link, status, basis in ROWS:
    cells = t.add_row().cells
    for cell, txt in zip(cells, (link, status, basis)):
        cell.text = ""
        pp = cell.paragraphs[0]
        pp.paragraph_format.line_spacing = 1.0
        pp.paragraph_format.space_after = Pt(1)
        pp.add_run(txt).font.size = Pt(8)

# move caption then table to sit directly after the anchor paragraph
anchor._p.addnext(t._tbl)
anchor._p.addnext(cap._p)

doc.save(SRC)
print("Table 4 inserted with %d rows, after: %s..." % (len(ROWS), anchor.text[:52]))
print("tables now in document: %d" % len(Document(SRC).tables))
