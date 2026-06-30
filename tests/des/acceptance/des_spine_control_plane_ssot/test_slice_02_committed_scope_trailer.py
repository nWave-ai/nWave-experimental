"""pytest-bdd binding for des-spine-control-plane-ssot slice-02.

Thin binding: registers the slice-02 scenarios, imports the step vocabulary from
`steps.steps_slice_02_committed_scope_trailer`, and provides the
`contract_gate_fixture` composition-root service. No step definitions or business
logic live here — the SSOT for step bodies is the imported step module + the
`ContractGateFixture` composition; the SSOT for the scenarios is the `.feature`
file (code is the SSOT, per the DISTILL mandate).

Slice-02 = the committed-scope trailer (Class C, the un-verifiable-digest
correctness slice): the `des run-contract-gate` producer stamps a PORTABLE
commit-scope trailer on a git tree, or degrades LOUD
(`committed-scope.indeterminate`, no un-verifiable trailer) on a git-absent tree
(AD-23 / ADR-CP-001). The `state` per-scenario scratchpad fixture is reused from
the slice-01 conftest (Mandate-12 step-reuse).
"""

from __future__ import annotations

import pytest
from pytest_bdd import scenarios

from .steps.composition_slice_02 import ContractGateFixture
from .steps.steps_slice_02_committed_scope_trailer import *


@pytest.fixture
def contract_gate_fixture(tmp_path) -> ContractGateFixture:
    """The single composition-root service all slice-02 step methods delegate to."""
    return ContractGateFixture(tmp_path)


scenarios("slice-02-committed-scope-trailer.feature")
