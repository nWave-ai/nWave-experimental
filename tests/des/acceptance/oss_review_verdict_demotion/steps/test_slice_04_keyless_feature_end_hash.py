"""Step definitions: the feature-end deep-review produces a deterministic content
hash with no key and refuses to mint theater (oss-review-verdict-demotion, S4).

Decision SSOT: docs/analysis/oss-hmac-signing-demotion-2026-06-11.md -- the row
"feature_end_sign_service (verdict_hash): keyed HMAC -> deterministic content
hash; anti-theater preserved by non-empty-reviewer + known-verdict checks".
feature-delta D-feature-end-hash + the S4 slice-plan row.

The surface being demoted: ``src/des/application/feature_end_sign_service.py``
-- ``sign_feature_end_review`` HMACs the verdict under the reviewer signing key
(108-121) and REFUSES when the key is unresolvable (108-114). Post-demotion the
verdict hash is ``sha256(canonical_signed_json(signed_region, SIGNED_FIELDS))``
-- keyless; the key-unresolvable refusal is gone; the non-empty-reviewer +
known-verdict refusals (90-106) stay verbatim.

Mandate 13: the driving port is the production ``des feature-end sign``
subcommand, invoked over the single ``des`` entry point as a subprocess through
the ``FeatureEndSealComposition`` composition root (Layer 3 subprocess, the SAME
surface as the oss-feature-end-emit-cli slice-02 producer). NO direct-domain
import of ``sign_feature_end_review`` / ``compute_verdict_hmac`` at the step
boundary; the keyless content-hash oracle recomputes via the at_review_signing
SSOT's RETAINED keyless ``canonical_signed_json`` helper (the audit substrate the
emitter consumes, not the SUT).

Layer 3 (subprocess/FS acceptance). Example-only, no PBT machinery (Mandate 9 v2
/ 11): the only driven adapter is the real filesystem (tmp_path), so the slice is
@real-io and each verdict input is a named example, not a Hypothesis @given. The
deterministic content hash IS reproducible, but the SUT is a real-I/O CLI
subprocess at layer 3, where PBT runtime cost is incompatible (Mandate 9 v2).

S1 (step-text uniqueness): every literal step string below is unique within the
feature directory. The S1/S2 slices speak of the carpaccio gate / producer; the
S3 slice speaks of the DISCUSS subagent-stop gate; this S4 slice speaks of the
feature-end deep-review verdict being "sealed" into a content hash -- no literal
is shared across the four slice step modules (no pytest-bdd registry shadow).

Step bodies delegate to ``FeatureEndSealComposition``; no inline business logic
(Mandate-12 criterion 3) -- each body is a typed lookup plus a composition call.

RED contract (fail-for-right-reason): on the pre-demotion tree (tip 0d8a76a91)
the signer loads a signing key and HMACs the verdict, refusing when the key is
unresolvable. All S4 scenarios run keyless, so the happy paths hit the
key-unresolvable refusal (no hash where a content hash is expected) and the
genuineness check cannot match a keyed HMAC against the keyless content hash --
each fails with a semantic AssertionError (missing functionality: the keyless
content-hash path + the removed key refusal). Not test bugs: every dependency
(the at_review_signing keyless helper, pytest-bdd, the real ``des`` dispatcher
subprocess) resolves cleanly (Mandate 7: RED, not BROKEN).
"""

from __future__ import annotations

from pathlib import Path

import pytest
from pytest_bdd import given, scenarios, then, when

from .composition_slice_04 import FeatureEndSealComposition, SealResult
from .domain_types_slice_04 import (
    DeepReviewVerdict,
    SealOutcome,
)


scenarios("../slice-04-keyless-feature-end-content-hash.feature")


@pytest.fixture
def composition(tmp_path: Path) -> FeatureEndSealComposition:
    """Production-wired composition root over a tmp_path repository, no key."""
    return FeatureEndSealComposition(tmp_path / "repo")


@pytest.fixture
def seal_box() -> dict[str, object]:
    """Carrier for the seal result + the verdict input across When -> Then steps."""
    return {}


# --- Given -------------------------------------------------------------------


# The Background needs no provisioning: the composition root never writes a key
# and scrubs the env, so the keyless precondition holds by construction. This
# Given asserts the keyless invariant and keeps the Background a readable phrase.


@given(
    "an orchestrator at the feature-end of a feature with no reviewer signing key anywhere"
)
def given_keyless_feature_end(composition: FeatureEndSealComposition) -> None:
    # The composition root provisions no signing key and scrubs the env var for
    # every subprocess run; instantiating it IS the keyless precondition.
    assert composition.no_signing_key_was_read()


# --- When --------------------------------------------------------------------


@when("the reviewer's APPROVED deep-review verdict is sealed")
def when_seal_approved(
    composition: FeatureEndSealComposition, seal_box: dict[str, object]
) -> None:
    verdict = composition.deep_review_verdict_with(DeepReviewVerdict.APPROVED)
    seal_box["verdict"] = verdict
    seal_box["result"] = composition.seal(verdict)


@when("the reviewer's REJECTED deep-review verdict is sealed")
def when_seal_rejected(
    composition: FeatureEndSealComposition, seal_box: dict[str, object]
) -> None:
    verdict = composition.deep_review_verdict_with(DeepReviewVerdict.REJECTED)
    seal_box["verdict"] = verdict
    seal_box["result"] = composition.seal(verdict)


# --- Then --------------------------------------------------------------------


def _result(seal_box: dict[str, object]) -> SealResult:
    return seal_box["result"]  # type: ignore[return-value]


@then("the command produces a deterministic content hash over that verdict")
def then_hash_is_content_hash(
    composition: FeatureEndSealComposition, seal_box: dict[str, object]
) -> None:
    result = _result(seal_box)
    verdict = seal_box["verdict"]
    assert composition.is_content_hash_shape(result.produced_hash), result.stderr
    assert result.produced_hash == composition.expected_content_hash_for(verdict)  # type: ignore[arg-type]


@then("the content hash is accepted by the feature-end record emitter")
def then_hash_accepted_by_emitter(
    composition: FeatureEndSealComposition, seal_box: dict[str, object]
) -> None:
    assert composition.seal_then_emit_round_trips(seal_box["verdict"])  # type: ignore[arg-type]


@then("the sealing command reports success")
def then_seal_succeeds(seal_box: dict[str, object]) -> None:
    assert _result(seal_box).outcome == SealOutcome.SUCCEEDED


@then("no reviewer signing key was read")
def then_no_key_read(composition: FeatureEndSealComposition) -> None:
    assert composition.no_signing_key_was_read()
