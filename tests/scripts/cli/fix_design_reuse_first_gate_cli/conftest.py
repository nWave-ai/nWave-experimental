"""pytest-bdd configuration for the F-DESIGN-REUSE-FIRST-GATE-CLI slice-01 set.

ATDD-pure author-ahead lifecycle: DISTILL authored this AT set ahead of its
slice's implementation. Per the carpaccio per-slice parking convention only
slice-01 (the walking skeleton) lives in the collected ``tests/`` tree;
slice-02 will be parked under
``docs/feature/fix-design-reuse-first-gate-cli/distill/pending-slices/`` and the
DELIVER loop moves each back when its slice is delivered.

The driving-port CLI (``scripts/cli/check_reuse_first_design.py``) does NOT
exist on master -- the AT set drives its creation. The crafter authors it
as a RED scaffold (``__SCAFFOLD__ = True``; ``main`` raises ``AssertionError``)
in A_GREEN_ATS so scenarios fail with semantic ``AssertionError``
(MISSING_FUNCTIONALITY RED) rather than a collection error
(``ImportError``/``ModuleNotFoundError``) (Mandate 7).

No xfail rewrite hook: under atdd_pure each slice's scenarios go GREEN when
its slice lands. The carpaccio DELIVER spine unskips per slice; on master the
slice-01 set is RED-for-the-right-reason, which is the intended pre-DELIVER
state per ADR-025.
"""

from __future__ import annotations
