"""Step definitions: direction (b) completeness at the DELIVER-entry gate — a
missing mandatory locked section is a FAIL naming it; an empty-body (heading-
present) section still freezes (algebra-projections-enforced slice-02, DISCUSS
WD-3(b)/WD-5, DESIGN DD-A4 revised by ADR-002, ADR-002 D1).

Layer 3 (subprocess/FS acceptance). Example-only, no PBT machinery (Mandate 9/11):
the locked-section presence cross-check is a finite, enumerable closed-world
classification at this layer (omits-one / one-empty), so a small set of explicit
examples is the correct paradigm; sad paths are enumerated explicitly (Mandate 11).

The gate has a pure-function contract (it reads the feature-delta + returns a
verdict). The When-step captures the before-universe; a Then asserts via
``assert_state_delta`` over a port-exposed filesystem universe that the
feature-delta is NOT mutated (Mandate 8).

Step bodies delegate to ``MandatorySectionComposition``; no inline business logic
(Mandate-12 criterion 3) — each body is a typed lookup plus a composition call.

Classification (PRESERVATION-GUARD, NOT active-RED): ADR-002 routes direction-(b)
completeness to the REAL DELIVER-entry gate ``des verify-deliver-entry-contract``,
which is REGISTERED AND FUNCTIONAL at HEAD. The gate ALREADY calls
``missing_registry_sections(content, _DELIVER_LOCKED_CONTRACT)`` at
``verify_deliver_entry_contract.py:193`` (naming the missing section) and presence
is ALREADY heading-based (``validate_feature_delta.py:574``, an empty-body section
freezes). Both scenarios therefore PASS at HEAD — they pin the direction-(b)
SEMANTICS as a regression guardrail (distinct from the byte-stable witnesses, which
pin that ALL FOUR sections are named after the migration swap).
"""

from __future__ import annotations

from pathlib import Path

import pytest
from pytest_bdd import given, parsers, scenarios, then, when

from .composition_slice_02 import MandatorySectionComposition
from .domain_types_slice_02 import (
    MANDATORY_DELTA_SHAPE_BY_PHRASE,
    FreezeVerdict,
)


scenarios("../slice-02-mandatory-section-presence.feature")


@pytest.fixture
def mandatory_composition() -> MandatorySectionComposition:
    """Production-wired composition root driving the real verify-deliver-entry CLI."""
    return MandatorySectionComposition()


# --- Given -------------------------------------------------------------------


@given(parsers.parse("a DELIVER-entry contract {shape_phrase}"))
def given_contract(
    mandatory_composition: MandatorySectionComposition, shape_phrase: str
) -> None:
    mandatory_composition.given_delta_shape(
        MANDATORY_DELTA_SHAPE_BY_PHRASE[shape_phrase]
    )


# --- When --------------------------------------------------------------------


@when("the contract-freeze gate runs at the DELIVER gate-IN")
def when_freeze_gate_runs(
    mandatory_composition: MandatorySectionComposition, tmp_path: Path
) -> None:
    mandatory_composition.when_the_freeze_gate_runs(tmp_path)


# --- Then --------------------------------------------------------------------


@then("the freeze gate refuses the contract for a missing mandatory section")
def then_refuses(mandatory_composition: MandatorySectionComposition) -> None:
    mandatory_composition.then_verdict_is(FreezeVerdict.FAIL)


@then("the refusal names the omitted locked section")
def then_names_section(mandatory_composition: MandatorySectionComposition) -> None:
    mandatory_composition.then_rejection_names_the_omitted_section()


@then("the freeze gate freezes the contract")
def then_freezes(mandatory_composition: MandatorySectionComposition) -> None:
    mandatory_composition.then_verdict_is(FreezeVerdict.PASS)


@then("the freeze gate emits no diagnostic")
def then_no_diagnostic(mandatory_composition: MandatorySectionComposition) -> None:
    mandatory_composition.then_no_diagnostic()


@then("the freeze gate leaves the contract unchanged")
def then_unchanged(mandatory_composition: MandatorySectionComposition) -> None:
    mandatory_composition.then_feature_delta_unchanged()
