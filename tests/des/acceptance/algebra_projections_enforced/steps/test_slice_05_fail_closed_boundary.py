"""Step definitions: the registry-section check fails closed at the boundary.

algebra-projections-enforced slice-05 (DISCUSS slice-05 Slice Plan / DoD; DESIGN
DA-5 / DD-A5). The LAST slice — after its DELIVER the feature-end fires.

Layer 3 (subprocess/FS acceptance). Example-only, no PBT machinery (Mandate
9/11): the boundary forms a finite, enumerable closed set (unknown-wave / garbled
/ absent / known-readable), so a small set of explicit examples is the correct
paradigm — the falsifier-gate forbids PBT on a closed-world finite domain at this
layer; sad paths are enumerated explicitly (Mandate 11).

The boundary has a fail-closed contract (DA-5): unknown-wave -> REJECT
(`unknown-wave`), unreadable registry -> INDETERMINATE (degrade-LOUD); NEVER
`accepted`, NEVER a crash. The When-step captures the before-universe; a Then
asserts via ``assert_state_delta`` over a port-exposed filesystem universe that
the feature-delta is NOT mutated (Mandate 8) — the read-only contract holds at
the boundary too.

Step bodies delegate to ``RegistrySectionBoundaryComposition``; no inline business
logic (Mandate-12 criterion 3) — each body is a typed lookup plus a composition
call.

active-RED scaffold (atdd_pure — NOT @skip). At HEAD ``des validate-feature-delta
--require-registry-sections`` collapses unknown-wave + unreadable-registry into a
plain-text ``error: ... is unreadable`` stderr + exit 1, emitting NO JSON verdict,
and does NOT parse ``--waves-dir``. So every boundary assertion observes
``UNRECOGNISED_INVOCATION`` and RED-fails for the right reason (missing
functionality). DELIVER ships the typed boundary verdicts + the ``--waves-dir``
override to turn these GREEN.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from pytest_bdd import given, parsers, scenarios, then, when

from .composition_slice_05 import RegistrySectionBoundaryComposition
from .domain_types_slice_05 import (
    BOUNDARY_CASE_BY_PHRASE,
    BOUNDARY_VERDICT_BY_PHRASE,
)


scenarios("../slice-05-fail-closed-boundary.feature")


@pytest.fixture
def composition() -> RegistrySectionBoundaryComposition:
    """Production-wired composition root driving the real validate-feature-delta CLI."""
    return RegistrySectionBoundaryComposition()


# --- Given -------------------------------------------------------------------


@given(parsers.parse("the maintainer checks {case_phrase}"))
def given_boundary_case(
    composition: RegistrySectionBoundaryComposition, case_phrase: str
) -> None:
    composition.given_boundary_case(BOUNDARY_CASE_BY_PHRASE[case_phrase])


# --- When --------------------------------------------------------------------


@when("the maintainer runs the registry-section boundary check")
def when_run_boundary_check(
    composition: RegistrySectionBoundaryComposition, tmp_path: Path
) -> None:
    composition.when_the_boundary_check_runs(tmp_path)


# --- Then --------------------------------------------------------------------


@then(parsers.parse("the registry-section boundary check {verdict_phrase}"))
def then_verdict(
    composition: RegistrySectionBoundaryComposition, verdict_phrase: str
) -> None:
    composition.then_verdict_is(BOUNDARY_VERDICT_BY_PHRASE[verdict_phrase])


@then("the boundary check never reports the feature-delta as accepted")
def then_never_accepted(composition: RegistrySectionBoundaryComposition) -> None:
    composition.then_never_accepted()


@then("the boundary check degrades without crashing")
def then_did_not_crash(composition: RegistrySectionBoundaryComposition) -> None:
    composition.then_did_not_crash()


@then("the boundary check leaves the feature-delta unchanged")
def then_unchanged(composition: RegistrySectionBoundaryComposition) -> None:
    composition.then_feature_delta_unchanged()
