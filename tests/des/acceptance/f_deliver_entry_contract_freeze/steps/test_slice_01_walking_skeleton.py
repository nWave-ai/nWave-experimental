"""pytest-bdd binding for slice-01 (walking skeleton) -- DELIVER-entry contract freeze.

Driving surface (Mandate-13 Layer 3 subprocess): the REAL ``des
verify-deliver-entry-contract`` gate over a real ``tmp_path`` repo carrying a real
``feature-delta.md`` + real ``.feature`` AT modules. The observables are the §17
verdict (parsed from the gate's JSON envelope) and the ``ContractFrozen`` record
the REAL ``AtCompletionLedger`` carries afterwards. Step bodies delegate to
``ContractFreezeComposition`` (Mandate-12: each body <=2 statements ending in a
composition call; no logic in step bodies).

The Given/When/Then phrases are imported from the single SSOT step module
``steps_contract_freeze`` -- ONE registration per phrase (S1; no cross-file
collision). This module only binds the slice-01 ``.feature`` via ``scenarios``.

active-RED scaffold (atdd_pure -- NOT @skip): RED until DELIVER ships
``src/des/cli/verify_deliver_entry_contract.py``, registers the
``verify-deliver-entry-contract`` subcommand, and adds the ``ContractFrozen``
ledger record. Every current-slice scenario fails for the RIGHT reason -- a named
semantic ``AssertionError`` (the subcommand is unregistered -> no verdict
envelope -> verdict is ``None`` -> the LOCKED-FIVE / verdict-equality / freeze
assertions fire), never a collection / import / setup error.
"""

from __future__ import annotations

from pytest_bdd import scenarios

# Single SSOT step module -- one registration each; re-used, never re-declared (S1).
from .steps_contract_freeze import *


scenarios("../slice-01-walking-skeleton-contract-frozen.feature")
