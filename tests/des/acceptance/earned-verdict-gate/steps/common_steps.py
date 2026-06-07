"""Shared step vocabulary for the oss-earned-verdict-gate suite.

Mandate-12 (SSOT via Types + Services + DSL): the slice ``.feature`` files
share ONE step vocabulary. Each decorator below is a parameterized template
over a typed-enum parameter (from ``domain_types.py``) -- the DSL emerges from
the typed domain concepts, not from one decorator per literal phrase.

Mandate-12 criterion 3: every step body is <=2 statements, ends in a single
``composition.<service>(...)`` call (or a typed-lookup + call), and contains no
control flow. Business logic lives in the production CORE behind the
``earned-verdict`` CLI; the composition transports envelopes; this module only
names domain facts and delegates (Mandate 10 shared-vocabulary contract).
"""

from __future__ import annotations

import shutil
from collections.abc import Iterator

import pytest
from pytest_bdd import given, parsers, then, when

from .composition import EarnedVerdictComposition
from .domain_types import (
    REASON_BY_PHRASE,
    RUN_SHAPE_BY_HEALTH,
    STATUS_BY_PHRASE,
)


@pytest.fixture
def composition() -> Iterator[EarnedVerdictComposition]:
    """The production composition root, fresh per scenario.

    Teardown removes the mkdtemp workspace the composition stages during the
    CLI subprocess call, so the suite leaves no ``/tmp`` residue.
    """
    comp = EarnedVerdictComposition()
    yield comp
    if comp._workspace is not None:
        shutil.rmtree(comp._workspace, ignore_errors=True)


# --- Given: stage the two RUN envelopes --------------------------------------


@given(parsers.parse('a baseline run that is "{health}"'))
def given_baseline_run(composition: EarnedVerdictComposition, health: str) -> None:
    composition.given_baseline_run(RUN_SHAPE_BY_HEALTH[health])


@given(parsers.parse('a perturbed run that is "{health}"'))
def given_perturbed_run(composition: EarnedVerdictComposition, health: str) -> None:
    composition.given_perturbed_run(RUN_SHAPE_BY_HEALTH[health])


# --- When: compute the earned verdict ----------------------------------------


@when("the earned-verdict gate computes the verdict over the two runs")
def when_compute_verdict(composition: EarnedVerdictComposition) -> None:
    composition.result = composition.compute_earned_verdict()


# --- Then: assert on the emitted earned_verdict.v1 ---------------------------


@then(parsers.parse('the earned verdict status is "{status}"'))
def then_verdict_status(composition: EarnedVerdictComposition, status: str) -> None:
    assert composition.result.status == STATUS_BY_PHRASE[status]


@then(parsers.parse('the earned verdict reason is "{reason}"'))
def then_verdict_reason(composition: EarnedVerdictComposition, reason: str) -> None:
    assert composition.result.reason == REASON_BY_PHRASE[reason]


@then("the emitted verdict conforms to the earned-verdict contract")
def then_verdict_conforms(composition: EarnedVerdictComposition) -> None:
    assert composition.emitted_envelope_is_valid_earned_verdict() is True


@then("the emitted verdict echoes the seam and node it was asked about")
def then_verdict_echoes_inputs(composition: EarnedVerdictComposition) -> None:
    assert composition.emitted_echo_matches_inputs() is True
