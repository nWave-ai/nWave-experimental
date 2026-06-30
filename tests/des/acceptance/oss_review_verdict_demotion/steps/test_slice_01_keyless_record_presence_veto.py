"""Step definitions: the AT-review slice gate enforces the record-presence veto
with no signing key (oss-review-verdict-demotion, S1).

Decision SSOT: docs/analysis/oss-hmac-signing-demotion-2026-06-11.md.
Hard contracts (b) record-absence blocks, (c) legacy record tolerated, (d)
content-seal stays -- all from the feature-delta DISCUSS [REF] Hard contracts.

Mandate 13: the driving port is the production carpaccio-slice-gate CLI
(``des.cli.carpaccio_slice_gate.main`` via argv), invoked through the
``DemotionGateComposition`` composition root. No direct-domain import of
``check_at_review``.

Layer 3 (subprocess/FS acceptance). Example-only, no PBT machinery (Mandate
9 v2 / 11): the only driven adapter is the real filesystem (tmp_path), so the
slice is @real-io and each S1 state is a named example, not a Hypothesis @given.

The gate has a pure-function contract: it mutates no file. The When-step
asserts via ``assert_state_delta`` over a port-exposed filesystem universe that
NO repository file is written AND no signing-key file appears (Mandate 8).

Step bodies delegate to ``DemotionGateComposition``; no inline business logic
(Mandate-12 criterion 3) -- each body is a typed lookup plus a composition call.

RED contract (fail-for-right-reason): on the pre-demotion tree the gate resolves
a signing key FIRST and raises ``key-absent`` when none is found. All three S1
scenarios run keyless, so the pre-demotion gate rejects ``key-absent`` -- the
clear/reason assertions fail with AssertionError (missing functionality: the
keyless record-presence path). Not a test bug: every dependency resolves
cleanly. The S1 crafter greens them by removing the key resolution +
``_hmac_verifies`` and keeping the record checks.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from pytest_bdd import given, parsers, scenarios, then, when

from tests.common.state_delta import assert_state_delta, unchanged

from .composition import DemotionGateComposition, GateResult
from .domain_types import (
    RECORD_STATE_BY_PHRASE,
    REJECT_REASON_BY_PHRASE,
    VERDICT_BY_PHRASE,
    FeatureId,
    ReviewVerdictRecordState,
)


scenarios("../slice-01-keyless-record-presence-veto.feature")


@pytest.fixture
def composition(tmp_path: Path) -> DemotionGateComposition:
    """Production-wired composition root over a tmp_path repository."""
    return DemotionGateComposition(repo_dir=tmp_path / "repo")


@pytest.fixture
def result_box() -> dict[str, GateResult]:
    """Carrier for the gate result across When -> Then steps."""
    return {}


# --- Given -------------------------------------------------------------------


@given("a repository for an atdd_pure feature with no reviewer signing key anywhere")
def given_keyless_repository(composition: DemotionGateComposition) -> None:
    composition.create_keyless_repo(FeatureId("oss-review-verdict-demotion"))


@given(parsers.parse("the entering slice has {record_phrase}"))
def given_review_record(
    composition: DemotionGateComposition, record_phrase: str
) -> None:
    composition.provision_review_record(RECORD_STATE_BY_PHRASE[record_phrase])


@given("the AT-completion ledger carries no review verdict for the entering slice")
def given_absent_record(composition: DemotionGateComposition) -> None:
    composition.provision_review_record(ReviewVerdictRecordState.ABSENT)


# --- When --------------------------------------------------------------------


@when("the operator runs the carpaccio slice gate for the entering slice")
def when_run_gate(
    composition: DemotionGateComposition,
    result_box: dict[str, GateResult],
) -> None:
    before = composition.capture_universe()
    result_box["result"] = composition.run_gate()
    result_box["universe_before"] = before  # type: ignore[assignment]


# --- Then --------------------------------------------------------------------


@then("the slice is cleared to enter implementation")
def then_cleared(result_box: dict[str, GateResult]) -> None:
    result = result_box["result"]
    assert result.verdict is VERDICT_BY_PHRASE["cleared to enter implementation"], (
        result.payload
    )


@then("the slice is blocked with an AT-review rejection")
def then_blocked(result_box: dict[str, GateResult]) -> None:
    result = result_box["result"]
    assert result.verdict is VERDICT_BY_PHRASE["blocked with an AT-review rejection"], (
        result.payload
    )


@then(parsers.parse('the rejection names the reason "{reason}"'))
def then_rejection_reason(result_box: dict[str, GateResult], reason: str) -> None:
    payload = result_box["result"].payload
    assert payload.get("event") == "ATReviewGateRejected", payload
    assert payload.get("reason") == REJECT_REASON_BY_PHRASE[reason].value, payload


@then("the legacy signature field triggered no verification and no parse error")
def then_legacy_field_ignored(
    composition: DemotionGateComposition,
    result_box: dict[str, GateResult],
) -> None:
    """Hard contract (c): the stray ``hmac_sha256`` is tolerated-and-ignored.

    The observable proxy: the gate CLEARED (exit 0) with the legacy field
    present AND no key resolvable anywhere. A gate that attempted to verify the
    signature would have needed a key (and rejected when none was found) or
    rejected on the non-verifying constant -- so a CLEARED verdict under a
    keyless repo proves no verification was attempted and no parse error
    escaped. The gate produced its normal cleared JSON, not an error payload.
    """
    assert composition.no_signing_key_provisioned()
    payload = result_box["result"].payload
    assert payload.get("event") == "SliceCleared", payload


@then("the gate writes no file in the repository")
def then_gate_writes_no_file(
    composition: DemotionGateComposition,
    result_box: dict[str, GateResult],
) -> None:
    """Pure-function contract: the gate mutates no repository file (Mandate 8).

    The universe is every file the gate reads -- the feature-delta, the slice
    ``.feature``, the AT-completion ledger, the workflow config -- plus the
    keyless invariant: ``signing_key.exists`` must stay False (the gate never
    materializes a key). Each universe slot is asserted ``unchanged``.
    """
    assert_state_delta(
        before=result_box["universe_before"],  # type: ignore[arg-type]
        after=composition.capture_universe(),
        universe={
            "feature_delta.bytes",
            "feature_file.bytes",
            "ledger.exists",
            "ledger.bytes",
            "config.bytes",
            "signing_key.exists",
        },
        expected={
            "feature_delta.bytes": unchanged(),
            "feature_file.bytes": unchanged(),
            "ledger.exists": unchanged(),
            "ledger.bytes": unchanged(),
            "config.bytes": unchanged(),
            "signing_key.exists": unchanged(),
        },
    )
