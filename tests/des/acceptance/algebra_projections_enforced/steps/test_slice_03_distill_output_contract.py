"""Step definitions: a DISTILL feature-delta is enforced against distill's contract.

algebra-projections-enforced slice-03 (DISCUSS slice-03, DESIGN Point 4 +
Reuse Analysis row `distill.yaml`, ADR-FLOW-006 D3/C2).

Layer 3 (subprocess/FS acceptance). Example-only, no PBT machinery
(Mandate 9/11): the three DISTILL feature-delta shapes form a finite, enumerable
closed set (all-declared / undeclared-section / single-declared), so a small set
of explicit examples is the correct paradigm — the falsifier-gate forbids PBT on a
closed-world finite domain at this layer; sad paths are enumerated explicitly
(Mandate 11).

The check has a pure-function contract (it reads the feature-delta + the live
distill registry and returns a verdict). A Then asserts via ``assert_state_delta``
over a port-exposed filesystem universe that the feature-delta is NOT mutated
(Mandate 8).

Step bodies delegate to ``DistillRegistrySectionComposition``; no inline business
logic (Mandate-12 criterion 3) — each body is a typed lookup plus a composition
call.

active-RED scaffold (atdd_pure — NOT @skip). At HEAD ``nWave/waves/distill.yaml``
carries NO ``output_contract`` block, so the distill registry contract is empty:
an all-declared DISTILL delta is rejected (``undeclared-section``), and a
bogus-section delta names the FIRST declared section rather than the bogus one. So
every slice-03 scenario RED-fails for the right reason (the missing distill
output_contract block). DELIVER A_GREEN adds the 8-entry
``output_contract.ref_sections`` block to distill.yaml to turn these GREEN.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from pytest_bdd import given, parsers, scenarios, then, when

from .composition_slice_03 import DistillRegistrySectionComposition
from .domain_types_slice_03 import (
    DISTILL_DELTA_SHAPE_BY_PHRASE,
    DISTILL_VERDICT_BY_PHRASE,
    WaveId,
)


scenarios("../slice-03-distill-output-contract-enforced.feature")


@pytest.fixture
def distill_composition() -> DistillRegistrySectionComposition:
    """Production-wired composition root driving the real validate-feature-delta CLI."""
    return DistillRegistrySectionComposition()


# --- Given -------------------------------------------------------------------


@given(parsers.parse("a DISTILL feature-delta {shape_phrase}"))
def given_distill_feature_delta(
    distill_composition: DistillRegistrySectionComposition, shape_phrase: str
) -> None:
    distill_composition.given_distill_delta_shape(
        DISTILL_DELTA_SHAPE_BY_PHRASE[shape_phrase]
    )


# --- When --------------------------------------------------------------------


@when(
    parsers.parse("the maintainer runs the registry-section check for the {wave} wave")
)
def when_run_check(
    distill_composition: DistillRegistrySectionComposition,
    tmp_path: Path,
    wave: str,
) -> None:
    distill_composition.when_the_check_runs_for_wave(WaveId(wave), tmp_path)


# --- Then --------------------------------------------------------------------


@then(parsers.parse("the registry-section check {verdict_phrase}"))
def then_verdict(
    distill_composition: DistillRegistrySectionComposition, verdict_phrase: str
) -> None:
    distill_composition.then_verdict_is(DISTILL_VERDICT_BY_PHRASE[verdict_phrase])


@then("the rejection names the undeclared distill section")
def then_names_section(
    distill_composition: DistillRegistrySectionComposition,
) -> None:
    distill_composition.then_rejection_names_the_section()


@then("the check leaves the feature-delta unchanged")
def then_unchanged(
    distill_composition: DistillRegistrySectionComposition,
) -> None:
    distill_composition.then_feature_delta_unchanged()
