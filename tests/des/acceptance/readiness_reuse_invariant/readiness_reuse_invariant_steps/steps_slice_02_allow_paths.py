"""Step bindings -- slice-02 (ALLOW paths + degrade-LOUD INDETERMINATE).

The readiness gate CLEARS the reuse-first dimension for a feature-delta carrying
EITHER a valid Reuse Analysis (incl. the exemption markers) OR a valid
`## Wave: DESIGN / [REF] Design Skipped` witness. An unreadable feature-delta
degrades LOUD: the 6th invariant refuses with a diagnostic naming the
unreadable source -- never silent-pass, never an unhandled crash.

Mandate-13 (S2 driving-port-only): imports ONLY the composition fixture +
`domain_types`. ZERO direct-domain imports. Driving port = real
`des verify-readiness-pre-dispatch` CLI subprocess via `composition.verify()`.

Mandate-12 criterion 3: every step body is <=2 statements ending in a
`composition.<method>(...)` call; no control flow.

S1 step-text uniqueness: slice-02 literals are distinct from slice-01's. The
shared `@when` / refuse / reuse-first-failed / unchanged-five Then steps are
declared once in slice-01 and reused here via the cross-module
`from ...steps_slice_01_walking_skeleton import *` re-export below (single
source of truth -- a single function object, no shadow registration, per the S1
tolerable-variant "shared-import re-use" rule).
"""

from __future__ import annotations

from pytest_bdd import given, parsers, then, when

from .domain_types import (
    REUSE_SHAPE_BY_PHRASE,
    WITNESS_BY_PHRASE,
    FirstDispatchInvariantId,
    InvariantStatus,
    ReadinessVerdict,
)

# Re-use the slice-01 shared step bodies (single registration; no S1 collision
# -- one function object propagated, the documented tolerable variant). Star
# re-export so the shared `@when`/`@then` callables land in this module's
# namespace and the slice-02 test runner's `scenarios()` resolves them.
from .steps_slice_01_walking_skeleton import *


# --- Given: ALLOW-path + INDETERMINATE workspaces -------------------------


@given(
    parsers.parse(
        "a feature workspace cleared on every other invariant carrying {reuse_phrase}"
    )
)
def given_workspace_with_reuse_only(
    readiness_reuse_composition, reuse_phrase: str
) -> None:
    readiness_reuse_composition.arm_feature_delta(
        REUSE_SHAPE_BY_PHRASE[reuse_phrase],
        WITNESS_BY_PHRASE["no Design Skipped witness"],
    )


@given(
    parsers.parse(
        "a feature workspace with no Reuse Analysis acknowledging the skip with "
        "{witness_phrase}"
    )
)
def given_workspace_with_witness_only(
    readiness_reuse_composition, witness_phrase: str
) -> None:
    readiness_reuse_composition.arm_feature_delta(
        REUSE_SHAPE_BY_PHRASE["no Reuse Analysis"], WITNESS_BY_PHRASE[witness_phrase]
    )


@given(
    parsers.parse(
        "a feature workspace carrying {reuse_phrase} ALONGSIDE {witness_phrase}"
    )
)
def given_workspace_with_reuse_and_witness(
    readiness_reuse_composition, reuse_phrase: str, witness_phrase: str
) -> None:
    readiness_reuse_composition.arm_feature_delta(
        REUSE_SHAPE_BY_PHRASE[reuse_phrase], WITNESS_BY_PHRASE[witness_phrase]
    )


@given("a feature workspace whose feature delta cannot be read as text")
def given_unreadable_workspace(readiness_reuse_composition) -> None:
    readiness_reuse_composition.arm_unreadable_feature_delta()


# --- When (slice-02-specific phrasing for the INDETERMINATE scenario) -------


@when("the maintainer runs the readiness gate against the unreadable workspace")
def when_run_gate_unreadable(readiness_reuse_composition) -> None:
    readiness_reuse_composition.verify()


# --- Then: ALLOW + degrade-LOUD observations -------------------------------


@then("the readiness gate clears the reuse-first dimension")
def then_reuse_first_cleared(readiness_reuse_composition) -> None:
    assert (
        readiness_reuse_composition.last_invariant_status(
            FirstDispatchInvariantId.REUSE_FIRST
        )
        is InvariantStatus.SATISFIED
    )


@then("the readiness gate refuses the unreadable workspace")
def then_gate_refuses_unreadable(readiness_reuse_composition) -> None:
    assert readiness_reuse_composition.last_verdict() is ReadinessVerdict.REFUSED


@then("the diagnostic names the unreadable feature delta")
def then_diagnostic_names_unreadable(readiness_reuse_composition) -> None:
    assert readiness_reuse_composition.last_remediation_contains(
        FirstDispatchInvariantId.REUSE_FIRST, "feature-delta"
    )
