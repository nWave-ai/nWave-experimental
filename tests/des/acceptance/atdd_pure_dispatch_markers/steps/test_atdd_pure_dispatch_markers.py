"""Step definitions: hg-slice-00 -- atdd_pure dispatch marker recognition.

hg-slice-00 of F-DES-ATDD-PURE-HOOK-GATES (U0 -- ADR-030 D8).

Three ATs, max PBT + parametrize density (feedback_ats_max_pbt_parametrize_
density_2026_05_19):
  * walking-skeleton (@component) -- 1 example-based scenario, reads the REAL
    nw-deliver SKILL.md atdd_pure dispatch template and round-trips it through
    the production DesMarkerParser in-process (pure-domain parse + one file-read,
    no subprocess).
  * recognition Scenario Outline -- 1 parametrized AT collapsing the
    marker {absent / valid / defective} x {mode, phase, slice} universe (M3/M14)
    into a single decision table. NOT a swarm of example-based ATs.
  * phase-entry-diagnostic Scenario Outline -- 1 parametrized AT over the
    missing-marker refusal cases.

Layer 1-2 (pure domain parser, no real I/O except the skill-file read). Step
bodies delegate to `DispatchMarkerComposition`; no inline logic (Mandate-12
criterion 3) -- each body is a typed lookup plus a composition call.

RED contract: every scenario FAILS on master -- the production DesMarkerParser
has no DES-PHASE / DES-SLICE patterns, no atdd_pure DesMarkers fields, and no
`classify_atdd_pure_dispatch` surface; the RED scaffold raises AssertionError
(MISSING_FUNCTIONALITY). They PASS once hg-slice-00 lands.
"""

from __future__ import annotations

import pytest
from pytest_bdd import given, parsers, scenarios, then, when

from .composition import DispatchMarkerComposition, ParseOutcome
from .domain_types import (
    MARKER_PRESENCE_BY_TOKEN,
    RECOGNITION_BY_TOKEN,
    DispatchRecognition,
)


scenarios("../atdd-pure-dispatch-markers.feature")


# RED-scaffold xfail marking lives in this slice's conftest.py
# (`pytest_collection_modifyitems`) -- it survives a step error raised inside a
# pytest-bdd step fixture, which a `pytest_bdd_apply_tag` marker does not.


@pytest.fixture
def composition() -> DispatchMarkerComposition:
    """Production-wired marker-recognition composition root."""
    return DispatchMarkerComposition()


@pytest.fixture
def outcome_box() -> dict[str, ParseOutcome]:
    """Carrier for the parse / classification outcome."""
    return {}


def _outcome(outcome_box: dict[str, ParseOutcome]) -> ParseOutcome:
    return outcome_box["outcome"]


# --- Given -------------------------------------------------------------------


@given("the production nw-deliver atdd_pure dispatch prompt")
def given_production_prompt(composition: DispatchMarkerComposition) -> None:
    composition.use_production_nw_deliver_prompt()


@given(parsers.parse("a dispatch prompt whose mode marker is {mode_marker}"))
def given_mode_marker(composition: DispatchMarkerComposition, mode_marker: str) -> None:
    composition.set_mode_marker(MARKER_PRESENCE_BY_TOKEN[mode_marker])


@given(parsers.parse("whose phase marker is {phase_marker}"))
def given_phase_marker(
    composition: DispatchMarkerComposition, phase_marker: str
) -> None:
    composition.set_phase_marker(MARKER_PRESENCE_BY_TOKEN[phase_marker])


@given(parsers.parse("whose slice marker is {slice_marker}"))
def given_slice_marker(
    composition: DispatchMarkerComposition, slice_marker: str
) -> None:
    composition.set_slice_marker(MARKER_PRESENCE_BY_TOKEN[slice_marker])


# --- When --------------------------------------------------------------------


@when("the DES marker parser parses the dispatch prompt")
def when_parse(
    composition: DispatchMarkerComposition,
    outcome_box: dict[str, ParseOutcome],
) -> None:
    outcome_box["outcome"] = composition.parse_dispatch()


@when("the DES marker parser classifies the dispatch prompt")
def when_classify(
    composition: DispatchMarkerComposition,
    outcome_box: dict[str, ParseOutcome],
) -> None:
    outcome_box["outcome"] = composition.classify_dispatch()


@when("the nw-deliver phase-entry diagnostic checks the dispatch prompt")
def when_diagnostic(
    composition: DispatchMarkerComposition,
    outcome_box: dict[str, ParseOutcome],
) -> None:
    outcome_box["outcome"] = composition.run_phase_entry_diagnostic()


# --- Then --------------------------------------------------------------------


@then("the walking-skeleton dispatch is recognised as a valid atdd_pure dispatch")
def then_valid(outcome_box: dict[str, ParseOutcome]) -> None:
    assert _outcome(outcome_box).recognition == DispatchRecognition.VALID.value


@then(parsers.parse("the dispatch is recognised as {recognition}"))
def then_recognition(outcome_box: dict[str, ParseOutcome], recognition: str) -> None:
    assert _outcome(outcome_box).recognition == RECOGNITION_BY_TOKEN[recognition].value


@then("the parsed mode is atdd_pure")
def then_mode_atdd_pure(outcome_box: dict[str, ParseOutcome]) -> None:
    assert _outcome(outcome_box).mode == "atdd_pure"


@then("the parsed phase is a member of the ATDD-pure phase vocabulary")
def then_phase_in_vocabulary(
    composition: DispatchMarkerComposition,
    outcome_box: dict[str, ParseOutcome],
) -> None:
    assert _outcome(outcome_box).atdd_pure_phase in composition.phase_vocabulary()


@then("the parsed slice id matches the anchored slice shape")
def then_slice_anchored(outcome_box: dict[str, ParseOutcome]) -> None:
    slice_id = _outcome(outcome_box).slice_id
    assert slice_id is not None
    assert slice_id.startswith("slice-") and slice_id[len("slice-") :].isdigit()


@then(parsers.parse("the dispatch is refused for the missing {missing_marker} marker"))
def then_refused_missing(
    outcome_box: dict[str, ParseOutcome], missing_marker: str
) -> None:
    outcome = _outcome(outcome_box)
    assert outcome.recognition == DispatchRecognition.DEFECTIVE.value
    assert outcome.refused_missing_marker == missing_marker
