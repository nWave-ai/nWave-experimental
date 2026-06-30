"""pytest-bdd binding for slice-03 (the code-design-manifest validity fold) -- CT-4.

Driving surface (Mandate-13 Layer 3 subprocess): the REAL ``des
verify-deliver-entry-contract`` gate over a real ``tmp_path`` repo whose
otherwise-structurally-complete contract ships a ``code-design.manifest.yaml`` in
an armed validity state (valid / invalid / absent). The observable is the §17
verdict the manifest-validity fold projects -- a valid (or absent) manifest -> PASS,
an invalid manifest (stale ``sut:`` symbol or bad schema) -> FAIL. Step bodies
delegate to ``ManifestFoldComposition`` (Mandate-12: each body <=2 statements
ending in a composition call; no logic in step bodies).

The Given/When/Then phrases are imported from the single SSOT step module
``steps_contract_freeze`` -- ONE registration per phrase (S1; no cross-file
collision). This module only binds the slice-03 ``.feature`` via ``scenarios``.

active-RED scaffold (atdd_pure -- NOT @skip): RED until DELIVER ships the gate's
manifest-validity FOLD. At HEAD the gate has NO manifest fold (zero "manifest"
references in ``src/des/cli/verify_deliver_entry_contract.py``), so an INVALID
manifest is IGNORED and the otherwise-complete contract RE-PASSES -> the INVALID
Outline example's ``then_verdict_is(FAIL)`` fires its named RED (PASS != FAIL).
The valid/absent examples are the CONTROL arms (they PASS at HEAD and must STILL
PASS after the fold lands -- the fold must not re-block a valid or a consciously
absent manifest). Every current-slice scenario fails (or, for the controls,
passes) for the RIGHT reason -- a named semantic ``AssertionError`` on the INVALID
arm, never a collection / import / setup error.
"""

from __future__ import annotations

from pytest_bdd import scenarios

# Single SSOT step module -- one registration each; re-used, never re-declared (S1).
from .steps_contract_freeze import *


scenarios("../slice-03-manifest-validity-fold.feature")
