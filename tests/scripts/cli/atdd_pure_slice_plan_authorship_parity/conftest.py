"""pytest-bdd configuration for the slice-01 acceptance set.

ATDD-pure per-slice JIT: this AT set is authored GREEN from the moment it
first runs. Slice-01's value claim (D-2) is that `des validate-feature-delta
--require-slice-plan --format=json` is ALREADY authorship-blind by
construction -- classifying only the Slice Plan table, never the document
shape around it -- so a DISTILL-shaped fixture and a DISCUSS-shaped one with
equivalent cell content already receive the identical verdict on the current
tip. The empirical probe run before authoring this suite (three combinations,
real CLI, both fixture shapes) confirmed the claim holds; no production code
gap exists for this slice to close, so no scaffold, no `@xfail`, no RED is
authored here. The suite itself -- passing on first run -- IS the evidence
D-2 anticipated as the possible (and, empirically, actual) outcome.
"""

from __future__ import annotations
