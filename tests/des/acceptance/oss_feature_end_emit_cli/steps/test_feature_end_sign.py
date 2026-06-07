"""Step definitions for slice-02 -- the `des feature-end sign` CLI.

slice-02 of oss-feature-end-emit-cli (DDD-7 RATIFIED 2026-06-03).

Step bodies are delegate-only (Mandate-12 criterion 3): each is a single typed
lookup / one `FeatureEndSignComposition` call + one observable assertion. All
signing logic lives in the production `des feature-end sign` subcommand (a thin
shim over the platform-agnostic signing use-case reusing the at_review_signing
SSOT); the composition root only wires the real subprocess, recomputes the HMAC
independently to prove genuineness, and feeds the produced hash to the real
slice-01 consumer.

S1 (step-text uniqueness): every literal step string below is unique within the
feature directory -- slice-01's steps speak of "records ... to the completion
ledger"; slice-02's steps speak of "signs a deep-review verdict ... into a
verdict hash". No literal is shared across the two slice step files (no shadow).
"""

from __future__ import annotations

from pathlib import Path

import pytest
from pytest_bdd import given, parsers, scenarios, then, when

from .composition_slice_02 import FeatureEndSignComposition, SignResult
from .domain_types_slice_02 import (
    DeepReviewVerdict,
    MalformedVerdictKind,
    SigningKeyState,
    SignOutcome,
    VerdictHash,
)


scenarios("../slice-02-feature-end-sign.feature")


# Scenario-Outline <defect> token -> typed MalformedVerdictKind (Mandate-12
# criterion 2: the composition method consumes the typed enum, never a raw str).
_DEFECT_BY_TOKEN: dict[str, MalformedVerdictKind] = {
    "empty-agent": MalformedVerdictKind.EMPTY_AGENT,
    "unknown-verdict": MalformedVerdictKind.UNKNOWN_VERDICT,
    "missing-verdict": MalformedVerdictKind.MISSING_VERDICT,
}


@pytest.fixture
def composition(tmp_path: Path) -> FeatureEndSignComposition:
    return FeatureEndSignComposition(tmp_path)


@pytest.fixture
def result_holder() -> dict[str, object]:
    return {}


# --- Given --------------------------------------------------------------------


@given(
    "an orchestrator at the feature-end of a feature with the reviewer signing key available",
    target_fixture="key_state",
)
def _given_key_available() -> SigningKeyState:
    return SigningKeyState.PRESENT


@given(
    "an orchestrator at the feature-end of a feature with the reviewer signing key absent",
    target_fixture="key_state",
)
def _given_key_absent() -> SigningKeyState:
    return SigningKeyState.ABSENT


# --- When ---------------------------------------------------------------------


@when("the reviewer's APPROVED deep-review verdict is signed")
def _when_sign_approved(
    composition: FeatureEndSignComposition,
    key_state: SigningKeyState,
    result_holder: dict[str, object],
) -> None:
    verdict = composition.deep_review_verdict_with(DeepReviewVerdict.APPROVED)
    result_holder["verdict"] = verdict
    result_holder["result"] = composition.sign(verdict, key_state=key_state)


@when("the reviewer's REJECTED deep-review verdict is signed")
def _when_sign_rejected(
    composition: FeatureEndSignComposition,
    key_state: SigningKeyState,
    result_holder: dict[str, object],
) -> None:
    verdict = composition.deep_review_verdict_with(DeepReviewVerdict.REJECTED)
    result_holder["verdict"] = verdict
    result_holder["result"] = composition.sign(verdict, key_state=key_state)


@when("a verdict is signed with no deep-review verdict at all")
def _when_sign_no_record(
    composition: FeatureEndSignComposition,
    result_holder: dict[str, object],
) -> None:
    result_holder["result"] = composition.sign_malformed(MalformedVerdictKind.NO_RECORD)


@when(parsers.parse("a verdict is signed with a {defect} deep-review verdict"))
def _when_sign_malformed(
    composition: FeatureEndSignComposition,
    result_holder: dict[str, object],
    defect: str,
) -> None:
    result_holder["result"] = composition.sign_malformed(_DEFECT_BY_TOKEN[defect])


@when("the consolidated feature-end command surface is probed")
def _when_probe_surface(
    composition: FeatureEndSignComposition,
    result_holder: dict[str, object],
) -> None:
    result_holder["reachable"] = composition.is_feature_end_namespace_reachable()


# --- Then ---------------------------------------------------------------------


@then(
    "the command produces a verdict hash that is a genuine signature over that verdict"
)
def _then_hash_is_genuine_signature(
    composition: FeatureEndSignComposition,
    result_holder: dict[str, object],
) -> None:
    result: SignResult = result_holder["result"]  # type: ignore[assignment]
    verdict = result_holder["verdict"]
    assert composition.is_genuine_hmac_shape(result.produced_hash)
    assert result.produced_hash == composition.expected_signature_for(verdict)  # type: ignore[arg-type]


@then("the produced hash is accepted by the feature-end record emitter")
def _then_hash_accepted_by_emitter(
    composition: FeatureEndSignComposition,
    result_holder: dict[str, object],
) -> None:
    result: SignResult = result_holder["result"]  # type: ignore[assignment]
    emit = composition.emit_with_signed_hash(VerdictHash(result.produced_hash))  # type: ignore[arg-type]
    assert emit.outcome == SignOutcome.SUCCEEDED


@then("the signing command reports success")
def _then_sign_succeeds(result_holder: dict[str, object]) -> None:
    result: SignResult = result_holder["result"]  # type: ignore[assignment]
    assert result.outcome == SignOutcome.SUCCEEDED


@then("the command refuses to sign")
def _then_sign_refused(result_holder: dict[str, object]) -> None:
    result: SignResult = result_holder["result"]  # type: ignore[assignment]
    # The refusal must come from the SIGNER's own anti-theater check, NOT a
    # dispatcher miss -- otherwise an unknown `des feature-end sign` subcommand
    # would vacuously satisfy a refusal. `refused_by_signer` requires the
    # signer's structured `SignRefused` payload, keeping this RED until the real
    # signer exists and refuses for the right reason.
    assert result.outcome == SignOutcome.REFUSED
    assert result.refused_by_signer is True


@then("the command produces no verdict hash")
def _then_no_hash(result_holder: dict[str, object]) -> None:
    result: SignResult = result_holder["result"]  # type: ignore[assignment]
    assert result.produced_hash is None


@then("the feature-end signing verb is reachable through the single entry point")
def _then_surface_reachable(result_holder: dict[str, object]) -> None:
    assert result_holder["reachable"] is True


@then("the feature-end record emitter still works under the consolidated surface")
def _then_emit_back_compat(composition: FeatureEndSignComposition) -> None:
    # Back-compat (DDD-7): the consolidated `des feature-end emit` surface still
    # appends a record -- proven by the round-trip of signing a real verdict and
    # feeding the produced genuine hash to the emitter under the consolidated
    # namespace (the whole round-trip lives in the composition service).
    assert composition.sign_then_emit_round_trips() is True
