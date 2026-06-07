"""Step definitions -- slice-04: signature contract (block -> trailer -> ledger triple).

F-DISTILL-HUMAN-SIGNOFF slice-04. The signoff block carries the canonical
content digest; the trailer is a mechanical projection of the block; the
ledger record is written by hook-invoked deterministic code (nwave-dev has
NO sequencer / NO engine, only hooks — Ale 2026-05-24). The three surfaces
are bound to ONE identity.

Layer 3 (subprocess / FS acceptance) for AT1 + AT2; layer 1 (static AST scan)
for AT3 (the architecture test). Example-based sad paths (Mandate 11).

Step bodies delegate to ``HumanSignoffComposition`` -- typed lookup + one
composition call, no inline logic (Mandate-12 criterion 3). The When-step
asserts the manifest + signed-coverage-map + signoff-digest sidecar are
unchanged by the verify path via ``assert_state_delta`` over a port-exposed
universe (Mandate 8).

This slice is RED-for-the-right-reason against the slice-03 production
``verify_coverage_map`` scaffold -- the ``emit-trailer`` subcommand does not
exist yet AND the deterministic ledger writer module (hook-invoked) does not
exist yet. The DELIVER loop adds the mechanical projection + hook-invoked
deterministic ledger writer + architecture-test allowlist of legitimate
caller modules; the present scaffold drives that delivery.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from pytest_bdd import given, scenarios, then, when

from tests.common.state_delta import assert_state_delta, unchanged

from .composition import HumanSignoffComposition
from .domain_types import (
    EXIT_CODE_BY_TRAILER_REFUSAL,
    CallGraphLayer,
    FeatureId,
    TrailerRefusalToken,
)


scenarios("../slice-04-signature-contract.feature")


# --- Fixtures --------------------------------------------------------------


@pytest.fixture
def composition(tmp_path: Path) -> HumanSignoffComposition:
    return HumanSignoffComposition(feature_root=tmp_path / "feature")


@pytest.fixture
def result_box() -> dict[str, object]:
    return {}


# --- Background -------------------------------------------------------------


@given("a feature whose design wave has produced a component manifest")
def given_design_wave_produced_manifest(
    composition: HumanSignoffComposition, result_box: dict[str, object]
) -> None:
    composition.create_feature_dir(FeatureId("acceptance-fixture-feature"))
    result_box["domain_ids"] = (
        composition.write_manifest_with_one_domain_per_dimension()
    )


@given("a coverage map has been authored and signed by a human")
def given_coverage_map_signed(composition: HumanSignoffComposition) -> None:
    composition.sign_coverage_map()


# --- Given ------------------------------------------------------------------


@given("the commit trailer has been hand edited away from the signoff block")
def given_trailer_hand_edited(composition: HumanSignoffComposition) -> None:
    composition.write_commit_trailer_hand_edited_away_from_block()


# --- When -------------------------------------------------------------------


@when("the engine emits the trailer derived from the signoff block")
def when_engine_emits_trailer(
    composition: HumanSignoffComposition, result_box: dict[str, object]
) -> None:
    # AT1 happy: the commit trailer must already exist on disk so the Then
    # step can compare emit-trailer output against it byte-for-byte (the
    # mechanical projection contract). Authoring it from the same block the
    # CLI re-derives is the SSOT trick -- only the production CLI's correctness
    # makes the two values agree.
    composition.write_commit_trailer_matching_signoff_block()
    before = composition.capture_slice04_universe()
    result_box["result"] = composition.run_emit_trailer()
    after = composition.capture_slice04_universe()
    # AT1 happy path: emit-trailer is a pure read over the signoff block; it
    # MUST NOT mutate any of the slice-03/04 port-exposed observables. The
    # ledger record itself is appended elsewhere (the verify path); emit-trailer
    # is the projection-only subcommand.
    assert_state_delta(
        before=before,
        after=after,
        universe={
            "manifest.present",
            "coverage_map.present",
            "feature_delta.present",
            "attestation.present",
            "signoff.present",
            "signoff_digest.present",
            "commit_trailer.present",
        },
        expected={
            "manifest.present": unchanged(),
            "coverage_map.present": unchanged(),
            "feature_delta.present": unchanged(),
            "attestation.present": unchanged(),
            "signoff.present": unchanged(),
            "signoff_digest.present": unchanged(),
            "commit_trailer.present": unchanged(),
        },
    )


@when("the reviewer verifies the coverage map")
def when_reviewer_verifies(
    composition: HumanSignoffComposition, result_box: dict[str, object]
) -> None:
    # AT2 sad path: the trailer is already hand-edited on disk (from the
    # Given step). Snapshot ledger BEFORE invocation so Then can assert
    # "no new signed record was appended".
    result_box["ledger_before"] = composition.capture_slice04_universe()[
        "ledger.signed_off_record_count"
    ]
    result_box["result"] = composition.run_verify_coverage_map()


@when("a static call graph scan inspects the repository")
def when_static_scan(
    composition: HumanSignoffComposition, result_box: dict[str, object]
) -> None:
    result_box["denylist_offenders"] = composition.static_call_graph_scan(
        CallGraphLayer.DENYLIST
    )
    result_box["allowlist_offenders"] = composition.static_call_graph_scan(
        CallGraphLayer.ALLOWLIST
    )


# --- Then -------------------------------------------------------------------


@then(
    "the emitted trailer matches the commit trailer carried alongside the coverage map"
)
def then_emitted_matches_commit(
    composition: HumanSignoffComposition, result_box: dict[str, object]
) -> None:
    result = result_box["result"]
    assert result.exit_code == 0, (
        f"expected exit 0 (emit-trailer succeeded); got {result.exit_code}: {result.stderr}"
    )
    assert composition.trailer_matches_commit_trailer(result), (
        f"emit-trailer stdout does not match the on-disk commit trailer.\n"
        f"emitted: {result.stdout!r}\n"
        f"on-disk: {composition.commit_trailer_path().read_text(encoding='utf-8')!r}"
    )


@then(
    "the ledger carries one signed coverage map record whose digest matches the signoff block"
)
def then_ledger_has_one_signed_record(
    composition: HumanSignoffComposition,
) -> None:
    assert composition.ledger_has_one_signed_off_record_with_matching_digest(), (
        "ledger does not carry exactly one CoverageMapSignedOff record whose "
        "reviewed_content_digest matches the signoff block digest"
    )


@then("the verify gate refuses for a trailer mismatch")
def then_verify_refuses_trailer_mismatch(
    composition: HumanSignoffComposition, result_box: dict[str, object]
) -> None:
    result = result_box["result"]
    token = TrailerRefusalToken.TRAILER_MISMATCH
    expected_exit = EXIT_CODE_BY_TRAILER_REFUSAL[token]
    assert result.exit_code == expected_exit, (
        f"expected exit {expected_exit} ({token.value}); "
        f"got {result.exit_code}: {result.stderr}"
    )
    assert composition.stderr_contains_refusal_token(token.value, result), (
        f"refusal token {token.value!r} missing from stderr\n--\n{result.stderr}"
    )


@then("the ledger does not gain a new signed coverage map record")
def then_ledger_unchanged(
    composition: HumanSignoffComposition, result_box: dict[str, object]
) -> None:
    after_count = composition.capture_slice04_universe()[
        "ledger.signed_off_record_count"
    ]
    before_count = result_box["ledger_before"]
    assert composition.ledger_signed_off_record_count_unchanged(
        before_count, after_count
    ), (
        f"ledger gained a CoverageMapSignedOff record on refusal: "
        f"before={before_count} after={after_count}"
    )


@then("no agent dispatch path reaches the signed coverage map ledger writer")
def then_no_agent_dispatch(result_box: dict[str, object]) -> None:
    offenders = result_box["denylist_offenders"]
    assert offenders == (), (
        f"static scan found agent-dispatch modules importing the ledger writer: "
        f"{offenders}"
    )


@then(
    "the only callers of the signed coverage map ledger writer are engine modules in the production deterministic tree"
)
def then_only_engine_callers(result_box: dict[str, object]) -> None:
    offenders = result_box["allowlist_offenders"]
    assert offenders == (), (
        f"static scan found non-engine modules calling the ledger writer: {offenders}"
    )
