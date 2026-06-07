"""Step definitions -- slice-06: both-touchpoint wiring.

F-DISTILL-HUMAN-SIGNOFF slice-06 (wiring slice, last). The ``verify_coverage_map``
gate runs at TWO touchpoints -- the DISTILL-exit handoff to DELIVER and the
DELIVER-exit handoff to feature-end -- and emits a heartbeat ledger record at
each. The handoff-blocked observable is the gate's non-zero exit code plus the
absence of the per-touchpoint heartbeat.

Hook-only architecture (Ale 2026-05-24 standing: nwave-dev has NO sequencer
and NO engine, ONLY hooks). The verify gate emits the heartbeat into the
AT-completion ledger (``CoverageMapVerifiedAtDistillExit`` +
``CoverageMapVerifiedAtDeliverExit``) -- the U4 SubagentStop hook enforcer (and
its ``verify_deliver_integrity`` CLI mirror) is the consumer that turns a
missing heartbeat into a feature-end block, mirroring the env-e2e + walking-
skeleton 5th-sibling pattern.

Layer 3 (subprocess / FS acceptance) -- the ``verify_coverage_map verify
--touchpoint <name>`` CLI is the driving port; the only driven port is the
real filesystem (tmp_path repo + the AT-completion ledger). Example-based
sad paths (Mandate 11) -- the Scenario Outlines enumerate closed finite
equivalence classes (unsigned states, staleness causes).

Step bodies delegate to ``HumanSignoffComposition`` -- typed lookup plus one
composition call, no inline logic (Mandate-12 criterion 3).
"""

from __future__ import annotations

from pathlib import Path

import pytest
from pytest_bdd import given, parsers, scenarios, then, when

from .composition import HumanSignoffComposition
from .domain_types import (
    STALENESS_CAUSE_BY_PHRASE,
    STALENESS_VERDICT_BY_PHRASE,
    UNSIGNED_STATE_BY_PHRASE,
    FeatureId,
    StalenessVerdict,
)


scenarios("../slice-06-touchpoint-wiring.feature")


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


# --- Given (slice-06 DISTILL-exit outline) ---------------------------------


@given(parsers.parse("the coverage map is in {unsigned_state} at the DISTILL exit"))
def given_coverage_map_unsigned_state(
    composition: HumanSignoffComposition,
    result_box: dict[str, object],
    unsigned_state: str,
) -> None:
    state = UNSIGNED_STATE_BY_PHRASE[unsigned_state]
    composition.stage_distill_exit_unsigned_state(state)


# --- Given (slice-06 DELIVER-exit + happy-path) ----------------------------


@given("a signed coverage map was approved at the DISTILL exit")
def given_signed_at_distill_exit(
    composition: HumanSignoffComposition, result_box: dict[str, object]
) -> None:
    composition.write_scenario_covering_all_domains(result_box["domain_ids"])
    composition.sign_coverage_map()
    composition.run_distill_to_deliver_handoff()


@given(
    parsers.re(
        r"during DELIVER (?P<staleness_cause>"
        r"the acceptance designer edited a signed section of the coverage map"
        r"|an acceptance scenario carrying a covers tag was dropped"
        r")"
    )
)
def given_during_deliver_staleness_cause(
    composition: HumanSignoffComposition,
    result_box: dict[str, object],
    staleness_cause: str,
) -> None:
    cause = STALENESS_CAUSE_BY_PHRASE[staleness_cause]
    composition.stage_deliver_exit_staleness_cause(cause, result_box["domain_ids"])


@given("during DELIVER the signed sections of the coverage map are unchanged")
def given_signed_sections_unchanged(composition: HumanSignoffComposition) -> None:
    composition.assert_coverage_map_body_unchanged_since_signoff()


@given("during DELIVER no acceptance scenario carrying a covers tag was dropped")
def given_no_covers_tag_dropped(composition: HumanSignoffComposition) -> None:
    composition.assert_no_covers_tag_dropped_since_signoff()


# --- When -------------------------------------------------------------------


@when("the workflow attempts the DISTILL to DELIVER handoff")
def when_distill_to_deliver_handoff(
    composition: HumanSignoffComposition, result_box: dict[str, object]
) -> None:
    result_box["result"] = composition.run_distill_to_deliver_handoff()


@when("the workflow attempts the DELIVER to feature end handoff")
def when_deliver_to_feature_end_handoff(
    composition: HumanSignoffComposition, result_box: dict[str, object]
) -> None:
    result_box["result"] = composition.run_deliver_to_feature_end_handoff()


@when("the workflow runs the DISTILL exit handoff and the DELIVER exit re-check")
def when_runs_both_touchpoints(
    composition: HumanSignoffComposition, result_box: dict[str, object]
) -> None:
    result_box["distill_result"] = composition.run_distill_to_deliver_handoff()
    result_box["deliver_result"] = composition.run_deliver_to_feature_end_handoff()


# --- Then -------------------------------------------------------------------


@then("the handoff is blocked at the DISTILL exit")
def then_handoff_blocked_at_distill(
    composition: HumanSignoffComposition, result_box: dict[str, object]
) -> None:
    result = result_box["result"]
    assert composition.handoff_blocked_with_named_refusal(result), (
        f"expected DISTILL exit handoff blocked with a named refusal token "
        f"(SignoffMissing / MalformedInput / StructuralIncomplete, exit 1 or 2); "
        f"got exit {result.exit_code}: {result.stderr}"
    )
    assert composition.distill_exit_heartbeat_absent(), (
        "expected no CoverageMapVerifiedAtDistillExit heartbeat on a blocked "
        "DISTILL-exit handoff (the gate must NOT record a verified-exit on "
        "refusal)"
    )


@then(
    parsers.parse("the handoff is blocked at the DELIVER exit with verdict {verdict}")
)
def then_handoff_blocked_at_deliver(
    composition: HumanSignoffComposition,
    result_box: dict[str, object],
    verdict: str,
) -> None:
    expected = STALENESS_VERDICT_BY_PHRASE[verdict]
    result = result_box["result"]
    assert composition.handoff_blocked(result), (
        f"expected DELIVER exit handoff blocked (non-zero exit); "
        f"got exit {result.exit_code}: {result.stderr}"
    )
    _assert_staleness_verdict(composition, result, expected)
    assert composition.deliver_exit_heartbeat_absent(), (
        "expected no CoverageMapVerifiedAtDeliverExit heartbeat on a blocked "
        "DELIVER-exit handoff (the gate must NOT record a verified-exit on "
        "refusal)"
    )


@then("the workflow proceeds past both touchpoints")
def then_workflow_proceeds_past_both(
    composition: HumanSignoffComposition, result_box: dict[str, object]
) -> None:
    distill_result = result_box["distill_result"]
    deliver_result = result_box["deliver_result"]
    assert distill_result.exit_code == 0, (
        f"expected DISTILL exit handoff exit 0 (proceed); "
        f"got exit {distill_result.exit_code}: {distill_result.stderr}"
    )
    assert deliver_result.exit_code == 0, (
        f"expected DELIVER exit handoff exit 0 (proceed); "
        f"got exit {deliver_result.exit_code}: {deliver_result.stderr}"
    )
    assert composition.distill_exit_heartbeat_present(), (
        "expected CoverageMapVerifiedAtDistillExit heartbeat after a passing "
        "DISTILL-exit handoff -- the gate's heartbeat is the U4 enforcer's "
        "proof the touchpoint ran"
    )
    assert composition.deliver_exit_heartbeat_present(), (
        "expected CoverageMapVerifiedAtDeliverExit heartbeat after a passing "
        "DELIVER-exit handoff -- the gate's heartbeat is the U4 enforcer's "
        "proof the touchpoint ran"
    )


# --- Helpers ----------------------------------------------------------------


def _assert_staleness_verdict(
    composition: HumanSignoffComposition,
    result: object,
    expected: StalenessVerdict,
) -> None:
    """Dispatch the DELIVER-exit verdict to the matching composition observable."""
    if expected is StalenessVerdict.SIGNOFF_STALE:
        assert composition.verify_gate_refuses_with_signoff_stale(result), (
            f"expected SignoffStale exit 1; got exit {result.exit_code}: "
            f"{result.stderr}"
        )
        return
    if expected is StalenessVerdict.OMISSION_DETECTED:
        assert composition.verify_gate_refuses_with_omission_detected(result), (
            f"expected OmissionDetected exit 1; got exit {result.exit_code}: "
            f"{result.stderr}"
        )
        return
    raise ValueError(f"unmapped staleness verdict: {expected!r}")
