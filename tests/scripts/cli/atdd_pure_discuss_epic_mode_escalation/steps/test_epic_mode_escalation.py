"""Step definitions: Phase 1.5 detection escalates an oversized request.

discuss-epic-mode slice-04 (the Phase 1.5 oversized-detection escalation contract).

Honest mechanical-vs-prompt boundary: the escalation is an LLM-mediated
prompt-surface act (DESIGN slice-02/04/05 text contracts: the slice's "code" is
SKILL / COMMAND text, NO ``src/des`` surface; Phase 1.5 detection is prose with no
validator / gate / structured detection config on the tip). These ATs pin the ESC
contract (ESC-1..ESC-6) on the escalation OUTCOME -- the trigger (ESC-1), the named
signals (ESC-2), the ``--epic`` proposal (ESC-3), the confirmation ask (ESC-4), the
decline path (ESC-5), and the right-sized guardrail (ESC-6) -- witnessed against a
suite-local reference producer (a golden-file analogue of Luna's emission), NOT a
prose-grep of SKILL.md (presence-watcher anti-pattern).

Layer 3 (FS acceptance). Example-only, no PBT machinery (Mandate 9/11): the ESC is
a finite, enumerable closed contract over the 5-signal closed list.

Step bodies delegate to ``EscalationComposition``; no inline business logic
(Mandate-12 criterion 3) -- each body is a typed lookup plus a composition call, or
a composition observation plus a single assertion.

Active-RED contract (atdd_pure): every ESC observation FAILS on the current tip and
PASSES once slice-04 lands. The escalation procedure is undefined today, so the
oversized-detection produces no escalation outcome -- the observation reads
``ESCALATION_ABSENT``. A deliberate missing-functionality RED (absent outcome and
absent ESC pins), not a test bug. The composition module imports ZERO production
code, so the RED is a semantic AssertionError, never a collection / import error.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from pytest_bdd import given, parsers, scenarios, then, when

from tests.common.state_delta import assert_state_delta, set_to

from .composition import EscalationComposition, EscalationObservation
from .domain_types import (
    ESCALATION_DECISION_BY_PHRASE,
    EscalationOutcome,
    OversizedSignal,
)


scenarios("../epic-mode-escalation.feature")


# Gherkin-phrase -> typed-signal lookup. The Given names fired signals by their
# human-readable descriptions (ESC-2 vocabulary); this maps each phrase fragment to
# its typed ``OversizedSignal`` so the step body stays a single parse + composition
# call (Mandate-12 criterion 3: no control flow in step bodies).
_SIGNAL_BY_PHRASE: dict[str, OversizedSignal] = {
    sig.value: sig for sig in OversizedSignal
}


def _parse_signal_phrase(phrase: str) -> tuple[OversizedSignal, ...]:
    """Parse a comma/``and``-joined signal phrase into the typed signal tuple.

    Module-level helper (NOT a step body) so the Given step stays a delegation.
    """
    cleaned = phrase.replace(", and ", ", ").replace(" and ", ", ")
    fragments = [frag.strip() for frag in cleaned.split(", ") if frag.strip()]
    return tuple(_SIGNAL_BY_PHRASE[frag] for frag in fragments)


@pytest.fixture
def composition(tmp_path: Path) -> EscalationComposition:
    """Composition root over a tmp_path repository."""
    return EscalationComposition(repo_dir=tmp_path / "repo")


@pytest.fixture
def result_box() -> dict[str, object]:
    """Carrier for observations across When -> Then steps."""
    return {}


# --- Given -------------------------------------------------------------------


@given("a maintainer running discuss on a request")
def given_maintainer(composition: EscalationComposition) -> None:
    composition.submit_request(())


@given(parsers.parse("the request fires the oversized signals {phrase}"))
def given_request_fires_signals(
    composition: EscalationComposition, phrase: str
) -> None:
    composition.submit_request(_parse_signal_phrase(phrase))


@given(parsers.parse("the maintainer will choose {decision_phrase}"))
def given_maintainer_will_choose(
    composition: EscalationComposition, decision_phrase: str
) -> None:
    composition.choose(ESCALATION_DECISION_BY_PHRASE[decision_phrase])


# --- When --------------------------------------------------------------------


@when("the maintainer runs the oversized-detection on the request")
def when_run_detection(
    composition: EscalationComposition, result_box: dict[str, object]
) -> None:
    composition.run_phase_1_5_detection()
    result_box["observation"] = composition.observe_escalation()


@when("the maintainer answers the confirmation ask")
def when_answer_confirmation(
    composition: EscalationComposition, result_box: dict[str, object]
) -> None:
    result_box["universe_before"] = composition.capture_universe()
    result_box["outcome"] = composition.resolve_decision()


# --- Then --------------------------------------------------------------------


@then("the detection escalates the request to epic-mode")
def then_escalated(result_box: dict[str, object]) -> None:
    """ESC-1: a request firing 2+ signals is escalated.

    On the current tip the escalation contract is undefined, so the observation
    reads ``ESCALATION_ABSENT`` and this pin fails -- the active-RED
    missing-functionality signal.
    """
    observation = result_box["observation"]
    assert isinstance(observation, EscalationObservation)
    assert observation.outcome is EscalationOutcome.ESCALATED, (
        "ESC-1: 2+ fired signals trigger an escalation"
    )


@then("the escalation names each fired signal")
def then_names_signals(
    composition: EscalationComposition, result_box: dict[str, object]
) -> None:
    """ESC-2 explain: the escalation names each fired signal, not a generic blurb."""
    observation = result_box["observation"]
    assert isinstance(observation, EscalationObservation)
    assert observation.named_signals == composition.submitted_signals, (
        "ESC-2: the escalation names exactly the fired signals"
    )


@then("the escalation proposes epic-mode naming the --epic flag")
def then_names_epic_flag(result_box: dict[str, object]) -> None:
    """ESC-3: the message proposes epic-mode and names the literal ``--epic``.

    The discoverability floor (KPI-3): the literal flag is present in the rendered
    escalation text, so a user who never heard of epic-mode finds it at the moment
    of need -- 0 external doc reads.
    """
    observation = result_box["observation"]
    assert isinstance(observation, EscalationObservation)
    assert observation.proposes_epic_mode, "ESC-3: proposes epic-mode"
    assert observation.names_epic_flag, "ESC-3: names the literal --epic flag"
    assert "--epic" in observation.message_text, (
        "ESC-3 / KPI-3: the rendered escalation text names --epic"
    )


@then("the escalation asks the maintainer to confirm without auto-switching")
def then_asks_confirmation(result_box: dict[str, object]) -> None:
    """ESC-4: closed confirmation options, never an auto-switch."""
    observation = result_box["observation"]
    assert isinstance(observation, EscalationObservation)
    assert len(observation.confirmation_options) == 2, (
        "ESC-4: the escalation asks confirmation with the closed option set "
        "(epic-mode / continue feature-level) -- never auto-switches"
    )


@then("standard feature-level discuss continues")
def then_feature_level_continues(result_box: dict[str, object]) -> None:
    """ESC-5: a declined escalation continues standard feature-level discuss."""
    assert result_box["outcome"] is EscalationOutcome.FEATURE_LEVEL_CONTINUED, (
        "ESC-5: declining continues standard feature-level DISCUSS"
    )


@then("the run created no epic workspaces")
def then_no_epic_workspaces(
    composition: EscalationComposition, result_box: dict[str, object]
) -> None:
    """ESC-5: a declined escalation produces zero epic artifacts.

    The universe is the epic-workspace count: declining must NOT author an
    epic-delta. On the current tip the detection never ran a real escalation, so
    the outcome assertion above fires first -- this delta pins the no-eager-artifact
    invariant at GREEN.
    """
    assert_state_delta(
        before=result_box["universe_before"],
        after=composition.capture_universe(),
        universe={"epic_workspaces.count"},
        expected={"epic_workspaces.count": set_to(0)},
    )


@then("the detection raises no escalation")
def then_no_escalation(result_box: dict[str, object]) -> None:
    """ESC-6 guardrail: a right-sized request (fewer than 2 signals) is not escalated.

    On the current tip the detection is undefined -> ``ESCALATION_ABSENT`` (NOT
    ``NO_ESCALATION``), so this pin fails -- the active-RED signal. At GREEN a
    sub-threshold request resolves to ``NO_ESCALATION``.
    """
    observation = result_box["observation"]
    assert isinstance(observation, EscalationObservation)
    assert observation.outcome is EscalationOutcome.NO_ESCALATION, (
        "ESC-6: a right-sized request raises no escalation"
    )


@then("the maintainer sees no new prompts")
def then_no_new_prompts(result_box: dict[str, object]) -> None:
    """ESC-6 / Guardrail 1: zero new prompts on a right-sized request."""
    observation = result_box["observation"]
    assert isinstance(observation, EscalationObservation)
    assert observation.confirmation_options == (), (
        "ESC-6 / Guardrail 1: a right-sized request shows zero confirmation prompts"
    )
