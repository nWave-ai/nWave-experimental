"""pytest-bdd binding for the DISCUSS gate-IN / gate-OUT / seam scenarios (slice-07).

Driving ports (Mandate-13 driving-port-only, Layer 3 composition):
  * gate-IN  -> the REAL ``PreToolUseService.validate`` via the production
    composition root.
  * gate-OUT -> the REAL ``SubagentStopService.validate`` via the production
    composition root.
  * seam     -> the §21.2.4 idempotence property, driven through the SAME gate-OUT
    service path (re-run on identical content), NOT a direct-domain function call.

Step bodies delegate to the composition root (``composition_slice_07.py``); no
production module is imported-and-called at the step boundary, and no business
logic lives in a step body (Mandate-12: each body is a single delegation).

``scenarios(...)`` binds via the RELATIVE path from this steps/ module. Each step
decorator's literal text is unique within this feature directory (S1 step-text-
uniqueness invariant) and disjoint from the slice-04 step files' literals -- no
literal is declared with its own body in two files.

Active-RED scaffold (ADR-025 + ADR-028, atdd_pure -- NOT @skip): until DELIVER
ships the ``discuss_gate.py`` cores + the ``ProductSsotReader`` /
``FeatureDeltaReader`` capability adapters + the two service branches, the
production services have no DISCUSS gate-IN / gate-OUT branch, so the entering /
returning dispatches are ALLOWED where a VETO / INDETERMINATE block is expected --
the scenarios fail with a semantic ``AssertionError`` (the gate did not deny),
never a collection / import / setup error (pre-DELIVER fail-for-right-reason gate).
"""

from __future__ import annotations

from pathlib import Path

import pytest
from pytest_bdd import given, scenarios, then, when

from .composition_slice_07 import DiscussGateComposition
from .domain_types_slice_07 import SlicePlanShape, SsotPreconditions


scenarios("../slice-07-discuss-gate-wiring.feature")


@pytest.fixture
def discuss_gate() -> DiscussGateComposition:
    return DiscussGateComposition()


# --- Given -------------------------------------------------------------------


@given("the discuss wave is active in a project whose product preconditions are unmet")
def given_discuss_active_preconditions_unmet(
    discuss_gate: DiscussGateComposition, tmp_path: Path
) -> None:
    discuss_gate.given_discuss_wave_active_with_preconditions(
        tmp_path, SsotPreconditions.UNMET
    )


@given(
    "the discuss wave is active in a project whose jobs registry is provided as YAML"
)
def given_discuss_active_jobs_as_yaml(
    discuss_gate: DiscussGateComposition, tmp_path: Path
) -> None:
    discuss_gate.given_discuss_wave_active_with_preconditions(
        tmp_path, SsotPreconditions.JOBS_AS_YAML
    )


@given(
    "the discuss wave is active in a project whose jobs registry is missing entirely"
)
def given_discuss_active_jobs_absent(
    discuss_gate: DiscussGateComposition, tmp_path: Path
) -> None:
    discuss_gate.given_discuss_wave_active_with_preconditions(
        tmp_path, SsotPreconditions.JOBS_ABSENT
    )


@given("no wave is active in a project whose product preconditions are unmet")
def given_no_wave_preconditions_unmet(
    discuss_gate: DiscussGateComposition, tmp_path: Path
) -> None:
    discuss_gate.given_no_wave_active_with_preconditions(
        tmp_path, SsotPreconditions.UNMET
    )


@given("a discuss-wave return whose feature-delta slice plan is infrastructure-only")
def given_discuss_return_infra_only(
    discuss_gate: DiscussGateComposition, tmp_path: Path
) -> None:
    discuss_gate.given_discuss_return_with_slice_plan(
        tmp_path, SlicePlanShape.INFRASTRUCTURE_ONLY
    )


@given("a discuss-wave return whose feature-delta slice plan is value-bearing")
def given_discuss_return_value_bearing(
    discuss_gate: DiscussGateComposition, tmp_path: Path
) -> None:
    discuss_gate.given_discuss_return_with_slice_plan(
        tmp_path, SlicePlanShape.VALUE_BEARING
    )


@given("the product owner has recorded an approved review of the current artefact")
def given_approved_review_recorded(discuss_gate: DiscussGateComposition) -> None:
    # oss-review-verdict-demotion S3: the review gate is always armed; the
    # legal discuss exit needs a keyless APPROVED review of the seeded delta.
    discuss_gate.given_approved_review_recorded()


@given("a discuss-wave return whose feature-delta cannot be read")
def given_discuss_return_unreadable(
    discuss_gate: DiscussGateComposition, tmp_path: Path
) -> None:
    discuss_gate.given_discuss_return_with_slice_plan(
        tmp_path, SlicePlanShape.UNREADABLE
    )


# --- When --------------------------------------------------------------------


@when("the wave-entering dispatch is checked by the gate")
def when_wave_entering_checked(discuss_gate: DiscussGateComposition) -> None:
    discuss_gate.when_wave_entering_dispatch_checked()


@when("a bare non-wave dispatch is checked by the discuss gate-in")
def when_bare_non_wave_checked(discuss_gate: DiscussGateComposition) -> None:
    discuss_gate.when_bare_non_wave_dispatch_checked()


@when("the discuss-wave return is checked by the gate")
def when_discuss_return_checked(discuss_gate: DiscussGateComposition) -> None:
    discuss_gate.when_discuss_return_checked()


@when("the discuss-wave return is checked by the gate twice on the identical artefact")
def when_discuss_return_checked_twice(discuss_gate: DiscussGateComposition) -> None:
    discuss_gate.when_discuss_return_checked_twice()


# --- Then --------------------------------------------------------------------


@then("the entry is blocked")
def then_entry_blocked(discuss_gate: DiscussGateComposition) -> None:
    discuss_gate.then_entry_blocked()


@then(
    "the block names the unmet discuss precondition so it cannot pass as a silent success"
)
def then_block_names_unmet_precondition(discuss_gate: DiscussGateComposition) -> None:
    discuss_gate.then_block_names_unmet_precondition()


@then("the entry is allowed as a greenfield advisory rather than vetoed")
def then_entry_allowed_greenfield_advisory(
    discuss_gate: DiscussGateComposition,
) -> None:
    discuss_gate.then_entry_allowed_greenfield_advisory()


@then("the entry is allowed and left completely untouched")
def then_entry_allowed_untouched(discuss_gate: DiscussGateComposition) -> None:
    discuss_gate.then_entry_allowed_untouched()


@then("the entry is allowed because the product preconditions are satisfied")
def then_entry_allowed_preconditions_satisfied(
    discuss_gate: DiscussGateComposition,
) -> None:
    discuss_gate.then_entry_allowed_preconditions_satisfied()


@then("the handoff is blocked")
def then_handoff_blocked(discuss_gate: DiscussGateComposition) -> None:
    discuss_gate.then_handoff_blocked()


@then("the block names the rejected slice plan so it cannot pass as a silent success")
def then_block_names_rejected_slice_plan(discuss_gate: DiscussGateComposition) -> None:
    discuss_gate.then_block_names_rejected_slice_plan()


@then("the handoff is allowed as no objection found")
def then_handoff_allowed_no_objection(discuss_gate: DiscussGateComposition) -> None:
    discuss_gate.then_handoff_allowed_no_objection()


@then("the handoff is blocked degrade-loud rather than passed silently")
def then_handoff_blocked_degrade_loud(discuss_gate: DiscussGateComposition) -> None:
    discuss_gate.then_handoff_blocked_degrade_loud()


@then("both checks yield the identical gate-out verdict")
def then_both_checks_identical_verdict(discuss_gate: DiscussGateComposition) -> None:
    discuss_gate.then_both_checks_identical_verdict()
