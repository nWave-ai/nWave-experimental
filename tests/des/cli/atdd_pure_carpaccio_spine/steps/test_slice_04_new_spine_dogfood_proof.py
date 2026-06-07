"""Step definitions -- slice-04: end-to-end dogfood proof on the new spine.

F-SIMPLIFY-ATDD-PURE-CARPACCIO-SPINE slice-04. Layer 4 (walking-skeleton /
E2E): the simplified spine itself (the 4-phase hand-orchestrated flow over the
slice-01..03 CLIs + the M-2 hook) is the driving surface. Example-only,
traditional assertions (Mandate 9 layer 4 / Mandate 11).

This is the honest DoD proof (§Bootstrap honesty): a thin real slice run ON the
new spine, demonstrating zero park / zero reverify and -- on the unverified
rows -- the M-2 backstop refusing the slice commit FROM WITHIN the flow. The
backstop is NOT poked standalone: slice-04 drives the whole four-phase flow and
observes the M-2 refusal as a step of that flow (C_REVIEWER_AUDIT re-scope).
It is NOT an implicit claim about slices 01-03, which were built on the OLD
spine. RED-by-design held green via the suite ``conftest.py``
``xfail(strict=True)`` mechanism (``_RED_SCAFFOLD_SLICES``).

SUT decision table -- the new-spine delivery flow has these flow-owned rows:

* happy      -- slice ATs GREEN, every phase clears, exit gate run: the slice
                ships with one SliceCommitVerified record, zero park, zero
                reverify (the @walking_skeleton scenario).
* unverified -- the slice cannot ship: its ATs were left RED at A_GREEN, OR the
                exit gate was skipped before D_REFACTOR_COMMIT. Both starve the
                ledger of a SliceCommitVerified record, so the flow's own commit
                step is refused by the M-2 backstop (the error Outline, two
                rows).

The predecessor-not-verified outcome belongs to the carpaccio_slice_gate entry
CLI and is witnessed by the slice-01 / slice-03 entry-gate ATs; the new-spine
flow delegates to that CLI, so it is not re-witnessed here.

Shares ``CarpaccioSpineComposition`` (Pillar 3). Step bodies delegate; no
inline logic (Mandate-12 criterion 3).
"""

from __future__ import annotations

from pathlib import Path

import pytest
from pytest_bdd import given, parsers, scenarios, then, when

from .composition import CarpaccioSpineComposition
from .domain_types import NEW_SPINE_FLAW_BY_PHRASE, FeatureId


scenarios("../slice-04-new-spine-dogfood-proof.feature")


@pytest.fixture
def composition(tmp_path: Path) -> CarpaccioSpineComposition:
    return CarpaccioSpineComposition(project_root=tmp_path / "project")


@pytest.fixture
def result_box() -> dict[str, object]:
    return {}


# --- Given -------------------------------------------------------------------


@given("a feature project on the simplified atdd_pure spine")
def given_project_on_new_spine(composition: CarpaccioSpineComposition) -> None:
    composition.create_feature_project(FeatureId("acceptance-fixture-feature"))


@given("a thin real slice ready to deliver on the simplified spine")
def given_thin_slice_ready(composition: CarpaccioSpineComposition) -> None:
    composition.arrange_deliverable_slice()


@given(parsers.parse("the flow is run with {flaw}"))
def given_new_spine_flaw(composition: CarpaccioSpineComposition, flaw: str) -> None:
    composition.arrange_new_spine_flaw(NEW_SPINE_FLAW_BY_PHRASE[flaw])


# --- When --------------------------------------------------------------------


@when("the slice is delivered through the simplified four-phase flow")
def when_deliver_through_new_spine(
    composition: CarpaccioSpineComposition, result_box: dict[str, object]
) -> None:
    result_box["result"] = composition.deliver_slice_on_new_spine()


# --- Then --------------------------------------------------------------------


@then("the slice ships with a SliceCommitVerified record")
def then_slice_shipped_with_record(
    composition: CarpaccioSpineComposition,
) -> None:
    assert composition.ledger_record_count() == 1, (
        "a slice delivered on the new spine must leave exactly one "
        "SliceCommitVerified record"
    )


@then("no file was manually parked and no reverify was invoked")
def then_zero_park_zero_reverify(
    composition: CarpaccioSpineComposition, result_box: dict[str, object]
) -> None:
    result = result_box["result"]
    assert result.parked_file_count == 0, (
        f"the new spine must require zero manual parking; "
        f"observed {result.parked_file_count} parked files"
    )
    assert result.reverify_invocations == 0, (
        f"the new spine must require zero reverify invocations; "
        f"observed {result.reverify_invocations}"
    )


@then("the involuntary backstop refuses the slice commit during the flow")
def then_backstop_refuses_within_flow(
    composition: CarpaccioSpineComposition, result_box: dict[str, object]
) -> None:
    result = result_box["result"]
    # The M-2 refusal is observed as a STEP of the four-phase flow -- the flow
    # carried the exit-gate/AT flaw all the way to its own commit step and was
    # refused there. ``backstop_verdict`` is the structured JSON the M-2 hook
    # emitted during that commit step.
    assert result.slice_commit_refused, (
        "the simplified flow must be refused at its commit step when the "
        "slice is unverified; the flow reported the commit was NOT refused"
    )
    # RED-honesty guard: a genuine M-2 refusal emits a structured verdict
    # naming the missing-record cause. A flow that crashed, or one whose
    # commit step exited non-zero for an unrelated reason, emits no such
    # verdict -- so this step stays genuinely RED until the new spine and its
    # M-2 backstop exist.
    verdict = result.backstop_verdict
    assert verdict.get("cause") == "missing-slice-commit-verified-record", (
        f"expected the in-flow backstop refusal to name the missing-record "
        f"cause; got verdict={verdict!r}"
    )


@then("the slice ships with no SliceCommitVerified record")
def then_no_record(composition: CarpaccioSpineComposition) -> None:
    assert composition.ledger_record_count() == 0, (
        "an unverified slice must leave NO SliceCommitVerified record -- the "
        f"flow recorded {composition.ledger_record_count()}"
    )
