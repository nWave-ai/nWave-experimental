"""Step SSOT for the f-deliver-entry-contract-freeze suite (S1 + Mandate-12).

Every Given/When/Then phrase is declared ONCE here -- one function object, one
pytest-bdd registration, no shadow possible (S1). Each body is <=2 statements
ending in a composition call; zero control flow (Mandate-12 -- no logic in step
bodies). Every body delegates to ``ContractFreezeComposition`` driving the REAL
``des verify-deliver-entry-contract`` gate (Mandate-13 -- driving-port-only, no
production import at the step boundary).

The ``contract_freeze`` fixture (one fresh composition per scenario) carries the
``tmp_path`` through which the real temp repo is materialised.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from pytest_bdd import given, parsers, then, when

from .composition import (
    ContractFreezeComposition,
    ContractReVerifyComposition,
    ManifestFoldComposition,
)
from .domain_types import ContractShape, FreezeVerdict, ManifestState, PostFreezeEdit


@pytest.fixture
def contract_freeze() -> ContractFreezeComposition:
    """A fresh composition root per scenario (the shared driving-port surface)."""
    return ContractFreezeComposition()


@pytest.fixture
def contract_reverify() -> ContractReVerifyComposition:
    """A fresh re-verify composition per scenario (freeze-then-re-verify surface)."""
    return ContractReVerifyComposition()


@pytest.fixture
def manifest_fold() -> ManifestFoldComposition:
    """A fresh manifest-fold composition per scenario (slice-03 driving surface)."""
    return ManifestFoldComposition()


# --- Given (the contract shape presented at DELIVER gate-IN) ----------------


@given(
    parsers.parse("a DELIVER-entry contract that is {shape}"),
    converters={"shape": ContractShape},
)
def given_contract_shape(
    contract_freeze: ContractFreezeComposition, shape: ContractShape
) -> None:
    contract_freeze.given_contract_shape(shape)


# --- When (the freeze gate driving port) ------------------------------------


@when("the contract-freeze gate runs at the first DELIVER gate-IN")
def when_freeze_gate_runs(
    contract_freeze: ContractFreezeComposition, tmp_path: Path
) -> None:
    contract_freeze.when_the_freeze_gate_runs_at_deliver_entry(tmp_path)


# --- Then (the §17 verdict) -------------------------------------------------


@then(
    parsers.re(r"the freeze gate returns an? (?P<verdict>\w+) verdict"),
    converters={"verdict": FreezeVerdict},
)
def then_verdict_is(
    contract_freeze: ContractFreezeComposition, verdict: FreezeVerdict
) -> None:
    contract_freeze.then_verdict_is(verdict)


# --- Then (the ContractFrozen ledger record) --------------------------------


@then("the contract is frozen in the completion ledger")
def then_contract_frozen(contract_freeze: ContractFreezeComposition) -> None:
    contract_freeze.then_contract_is_frozen()


@then("no contract is frozen in the completion ledger")
def then_contract_not_frozen(contract_freeze: ContractFreezeComposition) -> None:
    contract_freeze.then_contract_is_not_frozen()


# ===========================================================================
# slice-02 -- per-slice re-verify against the frozen baseline (CT-5 / CT-7)
# ===========================================================================


# --- Given (a feature already frozen at the first DELIVER gate-IN) ----------


@given("a contract frozen at the first DELIVER gate-IN")
def given_a_frozen_contract(
    contract_reverify: ContractReVerifyComposition, tmp_path: Path
) -> None:
    contract_reverify.given_a_frozen_contract(tmp_path)


# --- Given (how the live feature-delta diverges from the baseline) ----------


@given(
    parsers.parse("the live feature-delta has {edit} relative to the frozen baseline"),
    converters={"edit": PostFreezeEdit},
)
def given_post_freeze_edit(
    contract_reverify: ContractReVerifyComposition, edit: PostFreezeEdit
) -> None:
    contract_reverify.given_post_freeze_edit(edit)


# --- When (the per-slice gate-IN re-verifies the live delta) ----------------


@when("a per-slice DELIVER gate-IN re-verifies the contract")
def when_per_slice_reverifies(
    contract_reverify: ContractReVerifyComposition,
) -> None:
    contract_reverify.when_the_per_slice_gate_reverifies()


# --- Then (the re-verify §17 verdict + the single-baseline invariant) -------


@then(
    parsers.re(r"the re-verify returns an? (?P<verdict>\w+) verdict"),
    converters={"verdict": FreezeVerdict},
)
def then_reverify_verdict_is(
    contract_reverify: ContractReVerifyComposition, verdict: FreezeVerdict
) -> None:
    contract_reverify.then_reverify_verdict_is(verdict)


@then("the contract is frozen exactly once in the completion ledger")
def then_frozen_exactly_once(
    contract_reverify: ContractReVerifyComposition,
) -> None:
    contract_reverify.then_frozen_exactly_once()


# ===========================================================================
# slice-03 -- the code-design-manifest validity fold (CT-4 / KPI-3)
# ===========================================================================


# --- Given (a complete contract shipping a manifest in some validity state) --


@given(
    parsers.parse(
        "a structurally-complete contract that ships a {manifest} code-design manifest"
    ),
    converters={"manifest": ManifestState},
)
def given_manifest_state(
    manifest_fold: ManifestFoldComposition, manifest: ManifestState
) -> None:
    manifest_fold.given_manifest_state(manifest)


# --- When (the freeze gate folds the manifest at the first gate-IN) ----------


@when("the contract-freeze gate folds the manifest at the first DELIVER gate-IN")
def when_freeze_gate_folds_manifest(
    manifest_fold: ManifestFoldComposition, tmp_path: Path
) -> None:
    manifest_fold.when_the_freeze_gate_folds_the_manifest(tmp_path)


# --- Then (the §17 verdict the fold projects) -------------------------------


@then(
    parsers.re(r"the manifest-fold gate returns an? (?P<verdict>\w+) verdict"),
    converters={"verdict": FreezeVerdict},
)
def then_manifest_fold_verdict_is(
    manifest_fold: ManifestFoldComposition, verdict: FreezeVerdict
) -> None:
    manifest_fold.then_verdict_is(verdict)
