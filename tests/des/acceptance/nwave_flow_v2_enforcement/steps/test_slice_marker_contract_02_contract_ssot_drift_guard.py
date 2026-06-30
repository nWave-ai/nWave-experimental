"""pytest-bdd binding for the slice-02 contract-SSOT + drift-guard scenarios.

Driving surfaces (Mandate-13): AT-2a drives the REAL PreToolUseService.validate
via the production composition root (Layer 3 composition); AT-2b is a pure
Python + filesystem reconciliation over the entry-marker Contract SSOT + the
four command templates (git-free). Step bodies delegate to the composition root
(composition_slice_marker_contract_02.py); no business logic in step bodies
(Mandate-12). Every step decorator's literal is unique within this feature
directory (S1) and disjoint from the other slices' literals.

Active-RED scaffold (atdd_pure -- NOT @skip): AT-2a is RED until slice-01 ships
the wave_entering exemption; AT-2b is RED until DELIVER authors the §22.7.A
Contract SSOT block. Both fail with a semantic AssertionError, never a
collection / import / setup error.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from pytest_bdd import given, parsers, scenarios, then, when

from .composition_slice_marker_contract_02 import ContractSsotComposition
from .domain_types_slice_marker_contract import WaveUnderTest


scenarios("../slice-marker-contract-02-contract-ssot-drift-guard.feature")


@pytest.fixture
def contract() -> ContractSsotComposition:
    return ContractSsotComposition()


# --- Given -----------------------------------------------------------------


@given(parsers.parse("the {wave} wave is active with the template-shipped entry shape"))
def given_wave_entering_with_template_shape(
    contract: ContractSsotComposition, tmp_path: Path, wave: str
) -> None:
    contract.given_wave_entering_with_template_shape(tmp_path, WaveUnderTest(wave))


@given("the entry-marker SSOT file and the four command templates exist in the repo")
def given_ssot_and_templates_exist(contract: ContractSsotComposition) -> None:
    contract.given_ssot_and_templates_exist()


# --- When ------------------------------------------------------------------


@when("the template-shipped dispatch is checked")
def when_template_shipped_dispatch_checked(
    contract: ContractSsotComposition,
) -> None:
    contract.when_template_shipped_dispatch_checked()


@when("the entry-marker contract and the command templates are reconciled")
def when_contract_and_templates_reconciled(
    contract: ContractSsotComposition,
) -> None:
    contract.when_contract_and_templates_reconciled()


# --- Then ------------------------------------------------------------------


@then("the template-shipped entry shape is allowed")
def then_production_shape_allowed(contract: ContractSsotComposition) -> None:
    contract.then_production_shape_allowed()


@then("the contract, the templates, and the fixture agree with no drift")
def then_contract_and_templates_agree(contract: ContractSsotComposition) -> None:
    contract.then_contract_and_templates_agree()


# --- Regression preservation (RCA bb3d52546 false-positive fix) ------------
#
# The drift guard exists to catch a GENUINE drift: a template POSITIVELY
# requiring classic markers on the ENTERING dispatch (rejected Approach (b) /
# fixture-theater regression). The false-positive fix made
# ``_requires_classic_markers_on_entry`` negation-aware + sentence-scoped. These
# two probes pin BOTH directions so the fix cannot silently NEUTER the guard:
#
#   * the real HEAD ``Do not add DES-VALIDATION/...`` negative clause -> False
#     (no false drift on the correct Approach-(a) emitter), AND
#   * a synthetic POSITIVE-requirement line -> True (a real Approach-(b) drift is
#     STILL caught).

# Verbatim from the shipped templates at HEAD (commit bb3d52546): the classic
# tokens appear inside a NEGATIVE "Do not add ..." prohibition clause fused onto
# the same markdown line as the "Include the DES-WAVE marker" sentence whose
# ``include`` governs DES-WAVE -- the exact shape the naive heuristic mis-flagged.
_HEAD_NEGATIVE_ENTRY_LINE = (
    "**Wave-entry dispatch marker contract.** Include the "
    "`<!-- DES-WAVE: design -->` marker line above verbatim in EVERY architect "
    "Agent dispatch prompt. Do not add `DES-VALIDATION`/`DES-PROJECT-ID`/"
    "`DES-STEP-ID` to the architect entry dispatch; the DES-WAVE marker can only "
    "ADD gating, never remove it."
)

# A SYNTHETIC genuine drift: a sentence that POSITIVELY requires the classic
# markers on the entering dispatch (rejected Approach (b)). The guard MUST fire.
_SYNTHETIC_POSITIVE_ENTRY_LINE = (
    "The entering dispatch MUST include `DES-VALIDATION` and `DES-STEP-ID` "
    "in addition to the DES-WAVE marker."
)

# The legitimate non-entering child clause from HEAD: it DOES require the wave's
# DES marker set, but for the CHILD, not the entry -- must NOT be attributed to
# the entering dispatch. (Defensive: uses the literal classic tokens to prove the
# entry-scoping rather than the DES-* shorthand the shipped child line uses.)
_HEAD_CHILD_NON_ENTERING_LINE = (
    "**In-wave child dispatch (non-entering).** Such a child MUST carry the "
    "wave's DES marker set -- copy `DES-VALIDATION`/`DES-STEP-ID` from the "
    "parent dispatch onto the child prompt."
)


@pytest.mark.parametrize(
    ("probe_line", "expected_drift", "why"),
    [
        (
            _HEAD_NEGATIVE_ENTRY_LINE,
            False,
            "HEAD's negative 'Do not add DES-VALIDATION/...' clause is "
            "Approach-(a)-affirming -- it must NOT register as a drift",
        ),
        (
            _SYNTHETIC_POSITIVE_ENTRY_LINE,
            True,
            "a positive 'the entering dispatch MUST include DES-VALIDATION' "
            "requirement is the rejected Approach (b) -- the guard MUST still "
            "catch it (do not neuter the guard)",
        ),
        (
            _HEAD_CHILD_NON_ENTERING_LINE,
            False,
            "the non-entering child legitimately requires the DES marker set; "
            "that requirement must NOT be attributed to the ENTERING dispatch",
        ),
    ],
)
def test_drift_detection_is_negation_aware_and_entry_scoped(
    probe_line: str, expected_drift: bool, why: str
) -> None:
    detected = ContractSsotComposition._requires_classic_markers_on_entry(probe_line)
    assert detected is expected_drift, (
        f"detection={detected!r} but expected {expected_drift!r}: {why}"
    )
