"""BDD bindings for one bounded Codex continued-work opportunity."""

from __future__ import annotations

from pathlib import Path

import pytest
from pytest_bdd import given, parsers, scenarios, then, when
from tests.common.state_delta import assert_state_delta, set_to, unchanged

from .steps.composition import BoundedContinuationComposition
from .steps.domain_types import LimitKind


scenarios("bounded-continuation.feature")


@pytest.fixture
def composition(tmp_path: Path) -> BoundedContinuationComposition:
    return BoundedContinuationComposition(project=tmp_path / "operator-project")


@given(
    parsers.parse('a maintainer has armed one due continued-work unit for "{outcome}"')
)
def armed_due_work(composition: BoundedContinuationComposition, outcome: str) -> None:
    composition.arm_due_work(outcome)


@given("the maintainer also has a future-due continued-work unit")
def future_due_work(composition: BoundedContinuationComposition) -> None:
    composition.add_future_due_work()


@when("the maintainer starts Codex in that project")
def starts_codex(composition: BoundedContinuationComposition) -> None:
    composition.start_codex()


@then(
    parsers.parse('the maintainer sees one bounded execution receipt for "{outcome}"')
)
def sees_one_bounded_execution_receipt(
    composition: BoundedContinuationComposition, outcome: str
) -> None:
    observation = composition.observation
    assert (
        observation is not None
        and observation.offered_opportunity_count == 1
        and "execution receipt" in observation.public_text
        and outcome.lower() in observation.public_text
    ), (
        "WHAT: Codex SessionStart did not show one bounded execution receipt carrying the declared outcome. "
        "WHY: an opportunity alone cannot prove that the generic loop engine ran the operator's work. "
        "HOW: execute the selected due occurrence and project its durable receipt and outcome into SessionStart output."
    )


@then("the receipt names the authorised limits")
def receipt_names_limits(composition: BoundedContinuationComposition) -> None:
    observation = composition.observation
    assert (
        observation is not None
        and "1200" in observation.public_text
        and "30" in observation.public_text
    ), (
        "WHAT: the SessionStart execution receipt omitted its authorised bounds. "
        "WHY: an operator cannot judge whether executed work was controlled without visible limits. "
        "HOW: project the existing token and wall-time limits into the execution receipt."
    )


@then("the future-due unit remains untouched")
def future_work_remains_untouched(composition: BoundedContinuationComposition) -> None:
    assert composition.future_arm.get("selection", {}).get(
        "handle_id"
    ) != composition.due_arm.get("selection", {}).get("handle_id"), (
        "WHAT: the future continued-work request was merged into the due unit instead of being staged separately. "
        "WHY: SessionStart cannot prove that it left a future unit untouched when public control erased that unit. "
        "HOW: preserve a separately addressable future-due unit in the public loop state."
    )
    assert (
        composition.observation is not None
        and composition.observation.offered_opportunity_count == 1
    ), (
        "WHAT: SessionStart executed more than the one due continued-work unit. "
        "WHY: a later unit must remain absent until it is due, rather than becoming additional work in this session. "
        "HOW: select exactly one due unit and leave the separately staged future unit out of execution."
    )
    after_attestations = composition.durable_after["public.loop.attestations"]
    assert isinstance(after_attestations, tuple) and len(after_attestations) == 1, (
        "WHAT: SessionStart did not leave exactly one durable receipt while future work remained staged. "
        "WHY: the single-due-unit contract needs one completed occurrence and one untouched future population. "
        "HOW: persist one canonical tick attestation without selecting the future record."
    )
    assert_state_delta(
        before=composition.durable_before,
        after=composition.durable_after,
        universe={
            "public.loop.list",
            "public.loop.attestations",
            "public.loop.future_due_count",
        },
        expected={
            "public.loop.list": unchanged(),
            "public.loop.attestations": set_to(after_attestations),
            "public.loop.future_due_count": unchanged(),
        },
    )
    assert composition.durable_before["public.loop.attestations"] is not None, (
        "WHAT: public loop inspection omitted the durable occurrence set. "
        "WHY: text cannot prove SessionStart launched a bounded occurrence. "
        "HOW: expose the project's occurrence attestations through `des loop inspect`."
    )
    assert composition.durable_before["public.loop.attestations"] == (), (
        "WHAT: the pre-start public inspection already contained an occurrence receipt. "
        "WHY: the one-run assertion needs a true pre-execution baseline. HOW: capture "
        "the real `des loop inspect` attestation collection before SessionStart."
    )
    assert composition.durable_before["public.loop.future_due_count"] == 1, (
        "WHAT: public loop listing did not retain one future-due unit. "
        "WHY: the operator cannot verify that SessionStart left the later unit untouched without a durable listing. "
        "HOW: expose the separately staged future-due unit in `des loop list`."
    )


@then("inspection shows one applied continued-work receipt")
def inspection_shows_one_applied_receipt(
    composition: BoundedContinuationComposition,
) -> None:
    attestations = composition.durable_after["public.loop.attestations"]
    receipt = (
        attestations[0] if isinstance(attestations, tuple) and attestations else None
    )
    assert isinstance(receipt, dict) and receipt.get("execution_receipt") is not None, (
        "WHAT: public loop inspection did not show the applied SessionStart receipt. "
        "WHY: a host message cannot substitute for durable evidence that the generic loop engine ran. "
        "HOW: retain the tick attestation and its execution receipt in `des loop inspect`."
    )


@given(parsers.parse("a maintainer requests continued work with {limit_kind}"))
def unsafe_limit_requested(
    composition: BoundedContinuationComposition, limit_kind: str
) -> None:
    composition.choose_unsafe_limit(LimitKind(limit_kind))


@when("the maintainer asks to arm the bounded work")
def asks_to_arm_bounded_work(composition: BoundedContinuationComposition) -> None:
    composition.arm_unsafe_work()


@then(
    "the maintainer is told what is unsafe, why it was refused, and how to correct it"
)
def unsafe_limit_is_actionable(composition: BoundedContinuationComposition) -> None:
    observation = composition.observation
    assert observation is not None and observation.refusal_has_what_why_how, (
        "WHAT: unsafe bounded work was not refused with WHAT, WHY, and HOW guidance. "
        "WHY: a silent parser failure or a started unbounded run is unsafe for an operator. "
        "HOW: return a structured public refusal that explains the invalid bound and its correction."
    )


@then("no bounded work was started")
def no_bounded_work_started(composition: BoundedContinuationComposition) -> None:
    assert_state_delta(
        before=composition.before,
        after=composition.after,
        universe={"public.loop.state", "public.loop.attestations"},
        expected={
            "public.loop.state": unchanged(),
            "public.loop.attestations": unchanged(),
        },
    )


@given(
    parsers.parse(
        "a maintainer has armed continued work with a token allowance of {token_allowance:d}"
    )
)
def armed_constrained_work(
    composition: BoundedContinuationComposition, token_allowance: int
) -> None:
    composition.arm_constrained_work(token_allowance)


@when("the maintainer advances that continued work twice")
def advances_constrained_work_twice(
    composition: BoundedContinuationComposition,
) -> None:
    composition.advance_constrained_work_twice()


@then("the first advance consumes no more than the authorised token allowance")
def first_advance_respects_token_allowance(
    composition: BoundedContinuationComposition,
) -> None:
    observation = composition.budget_observation
    resources = (
        observation.first_event.get("resources", {}) if observation is not None else {}
    )
    authorised = resources.get("authorised", {}) if isinstance(resources, dict) else {}
    consumed = resources.get("consumed", {}) if isinstance(resources, dict) else {}
    assert (
        observation is not None
        and observation.first_exit_code == 0
        and authorised.get("max_tokens_per_tick") == 10
        and isinstance(consumed.get("tokens"), int)
        and 0 < consumed["tokens"] <= authorised["max_tokens_per_tick"]
    ), (
        "WHAT: the first continued-work advance spent more tokens than the authorised allowance. "
        "WHY: a declared token bound must control actual cumulative work, not merely appear in an arm acknowledgement. "
        "HOW: measure execution before accepting its receipt and cap or refuse work that would exceed the allowance."
    )


@then("the second advance is refused because the allowance is exhausted")
def second_advance_is_refused_after_budget_exhaustion(
    composition: BoundedContinuationComposition,
) -> None:
    observation = composition.budget_observation
    diagnostic = (
        observation.second_event.get("diagnostic", {})
        if observation is not None
        else {}
    )
    assert (
        observation is not None
        and observation.second_exit_code != 0
        and observation.second_event.get("status") == "refused"
        and diagnostic.get("code") == "TOKEN_BUDGET_EXHAUSTED"
        and all(
            isinstance(diagnostic.get(key), str) and diagnostic[key]
            for key in ("what", "why", "how")
        )
    ), (
        "WHAT: a second continued-work advance was not terminally refused after the token allowance was consumed. "
        "WHY: a bounded run must not take further work without a new operator request. "
        "HOW: persist consumed budget and return an actionable TOKEN_BUDGET_EXHAUSTED refusal before another execution."
    )


@then("inspection reports the terminal state and why continued work stopped")
def inspection_reports_budget_terminal_reason(
    composition: BoundedContinuationComposition,
) -> None:
    observation = composition.budget_observation
    state = observation.inspection.get("state", {}) if observation is not None else {}
    assert (
        observation is not None
        and observation.inspection_exit_code == 0
        and state.get("desired") == "STOPPED"
        and state.get("terminal_reason") == "TOKEN_BUDGET_EXHAUSTED"
    ), (
        "WHAT: loop inspection did not show a terminal state and token-budget reason after exhaustion. "
        "WHY: an empty or ambiguous inspection leaves the operator unable to distinguish stopped work from missing state. "
        "HOW: expose the durable stopped state and TOKEN_BUDGET_EXHAUSTED reason through `des loop inspect`."
    )
