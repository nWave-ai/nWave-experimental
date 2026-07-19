"""pytest-bdd configuration for the slice-01 acceptance set.

ATDD-pure per-slice JIT: this AT set is authored active-RED where the
classification is genuinely new (the "unjustified dependency" and
"malformed dependency row" scenarios) and green-as-a-non-regression-pin
where it guards behaviour the CLI already ships today (see the composition
module's "Active-RED note"). No `@xfail`/`@skip` tags -- every scenario
runs; the RED ones fail with a real `AssertionError` on the wrong verdict
token, never a collection/import error.
"""

from __future__ import annotations
