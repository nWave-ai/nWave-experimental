"""Step definitions -- slice-03: the four-state manifest resolver.

F-DESIGN-COMPONENT-MANIFEST slice-03. Layer 3 (FS acceptance): the
resolve_manifest_state() resolver is the driving port; the real filesystem
(tmp_path) is the only driven port. The four-state shape universe is
enumerated as Scenario Outline rows -- example-based at layer 3 (Mandate 9/11),
not a Hypothesis @given.

The resolver classifies SHAPE ONLY -- grounding is the caller's separate
validate-tool call (residuality F6); these scenarios never assert grounding.
Step bodies delegate to ``ComponentManifestComposition``; the When-step asserts
the manifest/marker files are unchanged by classification via
``assert_state_delta`` over a port-exposed universe (Mandate 8).

SUT state machine (C2 -- nw-at-completeness-check). ``resolve_manifest_state()``
is a pure classifier with no transitions: a feature's design directory maps to
exactly one of four terminal states, determined by manifest presence x schema
validity x marker presence:

    design dir + present manifest + schema-valid + non-empty domains  -> A
    design dir + present manifest + schema-valid + [] + rationale     -> B
    design dir + absent manifest  + not-applicable marker + reason     -> B
    design dir + absent manifest  + no marker                          -> C
    design dir + present manifest + schema-invalid                     -> D

The four states are mutually exclusive and exhaustive -- there is no illegal
event (the resolver accepts any design-dir path and always returns one state),
so C2b (illegal-event-from-each-state) is satisfied vacuously: a malformed
manifest is state D, an absent one state C, never an exception. The
``situation`` outline exercises C / B / D; the two named scenarios exercise A
and the second B sub-state (honest empty list).
"""

from __future__ import annotations

from pathlib import Path

import pytest
from pytest_bdd import given, parsers, scenarios, then, when

from tests.common.state_delta import assert_state_delta, unchanged

from .composition import ComponentManifestComposition
from .domain_types import (
    MANIFEST_STATE_BY_PHRASE,
    FeatureId,
    ManifestState,
    NotApplicableReason,
)


scenarios("../slice-03-four-state-resolver.feature")


@pytest.fixture
def composition(tmp_path: Path) -> ComponentManifestComposition:
    return ComponentManifestComposition(feature_root=tmp_path / "feature")


@pytest.fixture
def result_box() -> dict[str, object]:
    return {}


# --- Given -------------------------------------------------------------------


@given("a feature whose design directory has been prepared")
def given_design_dir_prepared(composition: ComponentManifestComposition) -> None:
    composition.create_feature_dir(FeatureId("acceptance-fixture-feature"))


@given("the architect has written a well-formed component manifest")
def given_well_formed_manifest(
    composition: ComponentManifestComposition,
) -> None:
    composition.write_valid_manifest()


@given("the architect has declared an honestly empty component manifest")
def given_empty_manifest(composition: ComponentManifestComposition) -> None:
    composition.write_empty_manifest_with_rationale()


@given(parsers.parse("the feature's component manifest is {situation}"))
def given_manifest_situation(
    composition: ComponentManifestComposition, situation: str
) -> None:
    if situation == "absent with no waiver":
        return  # design dir prepared, no manifest, no marker
    if situation == "absent with a not-applicable waiver and a reason":
        composition.write_not_applicable_marker(NotApplicableReason.LEGACY_PRE_ARTIFACT)
        return
    if situation == "present but malformed":
        from .domain_types import MalformedShape

        composition.write_malformed_manifest(MalformedShape.NOT_A_MAPPING)
        return
    raise AssertionError(f"unknown manifest situation: {situation!r}")


# --- When --------------------------------------------------------------------


@when("the manifest readiness is resolved")
def when_resolve(
    composition: ComponentManifestComposition, result_box: dict[str, object]
) -> None:
    before = composition.capture_universe()
    result_box["state"] = composition.resolve_state()
    after = composition.capture_universe()
    assert_state_delta(
        before=before,
        after=after,
        universe={"manifest.present", "feature_delta.present"},
        expected={
            "manifest.present": unchanged(),
            "feature_delta.present": unchanged(),
        },
    )


# --- Then --------------------------------------------------------------------


@then(parsers.parse("the manifest readiness is {phrase}"))
def then_state(result_box: dict[str, object], phrase: str) -> None:
    expected: ManifestState = MANIFEST_STATE_BY_PHRASE[phrase]
    actual = result_box["state"]
    assert actual == expected, f"expected manifest state {expected.name}; got {actual}"
