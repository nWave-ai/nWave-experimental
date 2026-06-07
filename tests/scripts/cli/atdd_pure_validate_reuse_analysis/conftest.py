"""pytest-bdd configuration for the F-DESIGN-REUSE-FIRST-GATE slice-01 set.

ATDD-pure author-ahead lifecycle: DISTILL authored this AT set ahead of its
slice's implementation. Per the carpaccio per-slice parking convention only
slice-01 (the walking skeleton) lives in the collected ``tests/`` tree;
slices 02-03 are parked under
``docs/feature/fix-design-reuse-first-gate/distill/pending-slices/`` and the
DELIVER loop moves each back when its slice is delivered.

Slice-01 has now been delivered: the production
``validate_feature_delta.py --require-reuse-analysis`` extension exists, the
``@xfail`` tags have been removed from the ``.feature`` file, and the
``pytest_bdd_apply_tag`` xfail translation hook has been retired. The
scenarios run live against the implemented pure core.
"""

from __future__ import annotations
