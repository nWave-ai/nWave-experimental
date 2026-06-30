"""Step definitions: the DISCUSS PO-review veto enforces record-presence with no
signing key and never disarms on key absence (oss-review-verdict-demotion, S3).

Decision SSOT: docs/analysis/oss-hmac-signing-demotion-2026-06-11.md.
Hard contracts (a) key-absence-never-disarms, (b) record-absence-always-blocks
-- from the feature-delta DISCUSS [REF] Hard contracts; the S3 row.

THE ESCAPE being closed: ``src/des/application/subagent_stop_service.py:372``
-- ``if record is None and key is None: return None`` (the gate silently
UNARMED when no key is provisioned and no record exists). Post-demotion
record-presence is the check; key absence disarms nothing.

Mandate 13: the driving port is the production DISCUSS gate-OUT -- the REAL
``SubagentStopService.validate`` built via the production composition root
(``service_factory.create_subagent_stop_service``), invoked through the
``DiscussVetoComposition`` composition root. NO direct-domain import of
``DiscussReviewGate.evaluate`` or ``_evaluate_discuss_po_review``.

Layer 3 (subprocess/FS acceptance). Example-only, no PBT machinery (Mandate
9 v2 / 11): the only driven adapter is the real filesystem (tmp_path), so the
slice is @real-io and each S3 state is a named example, not a Hypothesis @given.

The DISCUSS gate is a DECISION over read state: it mutates no file. The
When-step asserts via ``assert_state_delta`` over a port-exposed filesystem
universe that NO repository file is written AND no signing-key file appears
(Mandate 8). The decision (allow/block) + reason class are asserted by the Then
steps off the returned HookDecision.

Step bodies delegate to ``DiscussVetoComposition``; no inline business logic
(Mandate-12 criterion 3) -- each body is a typed lookup plus a composition call.

RED contract (fail-for-right-reason): on the pre-demotion tree (tip a77815c3e)
the gate resolves a signing key and carries the line-372 escape. All three S3
scenarios run keyless, so the absent case takes the escape and ALLOWS (where a
BLOCK is expected), and the approved/needs-revision cases reject
INDETERMINATE("key-absent") (where ALLOW / a reviewer veto is expected) -- each
fails with a semantic AssertionError (missing functionality: the keyless
record-presence path + the closed escape). Not test bugs: every dependency
resolves cleanly (Mandate 7: RED, not BROKEN). The crafter greens them by
deleting the line-372 escape + the key resolution and dropping the keyed legs
from ``DiscussReviewGate.evaluate``.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from pytest_bdd import given, parsers, scenarios, then, when

from tests.common.state_delta import assert_state_delta, unchanged

from .composition_slice_03 import DiscussDecision, DiscussVetoComposition
from .domain_types_slice_03 import (
    DECISION_BY_PHRASE,
    INDETERMINATE_REASON_TOKENS,
    RECORD_STATE_BY_PHRASE,
    REJECT_REASON_BY_PHRASE,
    VETO_REASON_TOKENS,
    DiscussReviewVerdictState,
    FeatureId,
)


scenarios("../slice-03-keyless-discuss-veto-and-escape-closed.feature")


@pytest.fixture
def composition(tmp_path: Path) -> DiscussVetoComposition:
    """Production-wired composition root over a tmp_path repository."""
    return DiscussVetoComposition(repo_dir=tmp_path / "repo")


@pytest.fixture
def result_box() -> dict[str, object]:
    """Carrier for the gate decision + universe across When -> Then steps."""
    return {}


# --- Given -------------------------------------------------------------------


@given(
    "a discuss-wave return for an atdd_pure feature with no reviewer signing key anywhere"
)
def given_keyless_discuss_return(composition: DiscussVetoComposition) -> None:
    composition.arm_keyless_discuss_return(FeatureId("oss-review-verdict-demotion"))


@given(
    "the DISCUSS review reader is wired and no review verdict is recorded for the feature"
)
def given_no_verdict_recorded(composition: DiscussVetoComposition) -> None:
    composition.provision_review_verdict(DiscussReviewVerdictState.KEYLESS_ABSENT)


@given(parsers.parse("the feature has {record_phrase}"))
def given_review_verdict(
    composition: DiscussVetoComposition, record_phrase: str
) -> None:
    composition.provision_review_verdict(RECORD_STATE_BY_PHRASE[record_phrase])


# --- When --------------------------------------------------------------------


@when("the discuss-wave handoff is checked at the subagent-stop gate")
def when_check_discuss_handoff(
    composition: DiscussVetoComposition,
    result_box: dict[str, object],
) -> None:
    before = composition.capture_universe()
    result_box["result"] = composition.run_discuss_gate()
    assert_state_delta(
        before=before,
        after=composition.capture_universe(),
        universe={
            "floor.bytes",
            "feature_delta.bytes",
            "ledger.exists",
            "ledger.bytes",
            "signing_key.exists",
        },
        expected={
            "floor.bytes": unchanged(),
            "feature_delta.bytes": unchanged(),
            "ledger.exists": unchanged(),
            "ledger.bytes": unchanged(),
            "signing_key.exists": unchanged(),
        },
    )


# --- Then --------------------------------------------------------------------


def _decision(result_box: dict[str, object]) -> DiscussDecision:
    return result_box["result"]  # type: ignore[return-value]


@then("the handoff to design is blocked degrade-loud as indeterminate")
def then_blocked_indeterminate(result_box: dict[str, object]) -> None:
    decision = _decision(result_box)
    assert (
        decision.decision is DECISION_BY_PHRASE["blocked degrade-loud as indeterminate"]
    ), decision.reason


@then(parsers.parse('the indeterminate block names the reason "{reason}"'))
def then_indeterminate_reason(result_box: dict[str, object], reason: str) -> None:
    text = (_decision(result_box).reason or "").lower()
    expected = REJECT_REASON_BY_PHRASE[reason].value
    assert expected in text, _decision(result_box).reason


@then("the indeterminate block never masquerades as a reviewer veto")
def then_indeterminate_not_veto(result_box: dict[str, object]) -> None:
    text = (_decision(result_box).reason or "").lower()
    assert any(token in text for token in INDETERMINATE_REASON_TOKENS), text
    assert not any(token in text for token in VETO_REASON_TOKENS), text


@then("the handoff to design is allowed as no objection found from the review")
def then_allowed_no_objection(result_box: dict[str, object]) -> None:
    decision = _decision(result_box)
    assert (
        decision.decision
        is DECISION_BY_PHRASE["allowed as no objection found from the review"]
    ), decision.reason


@then("the handoff to design is blocked by the reviewer veto")
def then_blocked_by_veto(result_box: dict[str, object]) -> None:
    decision = _decision(result_box)
    assert decision.decision is DECISION_BY_PHRASE["blocked by the reviewer veto"], (
        decision.reason
    )


@then(
    "the veto names the reviewer decision read from the recorded verdict, never the agent's say-so"
)
def then_veto_names_reviewer_decision(result_box: dict[str, object]) -> None:
    text = (_decision(result_box).reason or "").lower()
    assert any(token in text for token in VETO_REASON_TOKENS), text
    assert not any(token in text for token in INDETERMINATE_REASON_TOKENS), text
