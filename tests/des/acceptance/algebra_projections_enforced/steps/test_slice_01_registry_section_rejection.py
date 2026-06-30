"""Step definitions: the registry-section check rejects an undeclared section.

algebra-projections-enforced slice-01 (DISCUSS WD-1/WD-3(a), DESIGN DA-1/DA-2/
DA-6, ADR-001 D1/D3).

Layer 3 (subprocess/FS acceptance). Example-only, no PBT machinery
(Mandate 9/11): the four feature-delta shapes form a finite, enumerable closed
set (all-declared / undeclared-section / legacy-tuple-only / registry-only), so a
small set of explicit examples is the correct paradigm — the falsifier-gate
forbids PBT on a closed-world finite domain at this layer; sad paths are
enumerated explicitly (Mandate 11).

The check has a pure-function contract (it reads the feature-delta + the live
registry and returns a verdict). The When-step captures the before-universe; a
Then asserts via ``assert_state_delta`` over a port-exposed filesystem universe
that the feature-delta is NOT mutated (Mandate 8).

Step bodies delegate to ``RegistrySectionComposition``; no inline business logic
(Mandate-12 criterion 3) — each body is a typed lookup plus a composition call.

active-RED scaffold (atdd_pure — NOT @skip). At HEAD ``des validate-feature-delta``
does not accept ``--require-registry-sections``; invoked with that flag it prints
usage and returns exit 1, emitting no JSON verdict. So every verdict assertion
observes ``UNRECOGNISED_INVOCATION`` and RED-fails for the right reason
(missing functionality). DELIVER ships the flag + the live-registry classifier to
turn these GREEN.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from pytest_bdd import given, parsers, scenarios, then, when

from .composition import RegistrySectionComposition
from .domain_types import (
    DELTA_SHAPE_BY_PHRASE,
    VERDICT_BY_PHRASE,
    WaveId,
)


scenarios("../slice-01-registry-backed-section-rejection.feature")


@pytest.fixture
def composition() -> RegistrySectionComposition:
    """Production-wired composition root driving the real validate-feature-delta CLI."""
    return RegistrySectionComposition()


# --- Given -------------------------------------------------------------------


@given(parsers.parse("a feature-delta {shape_phrase}"))
def given_feature_delta(
    composition: RegistrySectionComposition, shape_phrase: str
) -> None:
    composition.given_delta_shape(DELTA_SHAPE_BY_PHRASE[shape_phrase])


# --- When --------------------------------------------------------------------


@when(
    parsers.parse("the maintainer runs the registry-section check for the {wave} wave")
)
def when_run_check(
    composition: RegistrySectionComposition, tmp_path: Path, wave: str
) -> None:
    composition.when_the_check_runs_for_wave(WaveId(wave), tmp_path)


# --- Then --------------------------------------------------------------------


@then(parsers.parse("the registry-section check {verdict_phrase}"))
def then_verdict(composition: RegistrySectionComposition, verdict_phrase: str) -> None:
    composition.then_verdict_is(VERDICT_BY_PHRASE[verdict_phrase])


@then("the rejection names the undeclared section")
def then_names_section(composition: RegistrySectionComposition) -> None:
    composition.then_rejection_names_the_section()


@then("the check leaves the feature-delta unchanged")
def then_unchanged(composition: RegistrySectionComposition) -> None:
    composition.then_feature_delta_unchanged()
