"""pytest-bdd binding for slice-02 (per-slice re-verify) -- freeze holds (CT-5/CT-7).

Driving surface (Mandate-13 Layer 3 subprocess): the REAL ``des
verify-deliver-entry-contract`` gate re-invoked per slice over a real ``tmp_path``
repo whose live ``feature-delta.md`` is mutated AFTER the freeze. The observables
are the re-verify §17 verdict (drift -> FAIL) and the count of ``ContractFrozen``
baselines the REAL ``AtCompletionLedger`` carries (feature-level granularity, CT-7).
Step bodies delegate to ``ContractReVerifyComposition`` (Mandate-12: each body <=2
statements ending in a composition call; no logic in step bodies).

The Given/When/Then phrases are imported from the single SSOT step module
``steps_contract_freeze`` -- ONE registration per phrase (S1; no cross-file
collision). This module only binds the slice-02 ``.feature`` via ``scenarios``.

active-RED scaffold (atdd_pure -- NOT @skip): RED until DELIVER ships the gate's
per-slice RE-VERIFY behaviour -- (1) diff the live feature-delta against the frozen
``ContractFrozen`` baseline (a post-freeze mutation beyond the status-flip "slice
shipped" -> FAIL/HALT), and (2) re-earn the freeze WITHOUT minting a second
baseline (single feature-level baseline, CT-7). At HEAD the gate re-runs the SAME
structural check and re-writes ``ContractFrozen`` on every PASS, so the drift
scenarios RE-PASS (PASS != FAIL) and the single-baseline scenario sees two records
(2 != 1) -- every current-slice scenario fails for the RIGHT reason (a named
semantic ``AssertionError``), never a collection / import / setup error.
"""

from __future__ import annotations

from pytest_bdd import scenarios

# Single SSOT step module -- one registration each; re-used, never re-declared (S1).
from .steps_contract_freeze import *


scenarios("../slice-02-per-slice-reverify-freeze-holds.feature")
