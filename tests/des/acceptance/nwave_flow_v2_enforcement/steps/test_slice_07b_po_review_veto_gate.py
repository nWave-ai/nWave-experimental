"""pytest-bdd binding for the DISCUSS PO-review mechanical veto-gate scenarios (slice-07b).

Driving port (Mandate-13 driving-port-only, Layer 3 composition): the REAL
``SubagentStopService.validate`` via the production composition root, with a
``discuss`` wave-active floor armed AND a value-bearing feature-delta seeded so
the slice-07 structural gate-OUT PASSES -- the NEW PO-review-gate branch is what
decides. Observable = the HookDecision (allow vs block) + the
``DISCUSS_PO_REVIEW_*`` reason token.

Step bodies delegate to the composition root (``composition_slice_07b.py``); no
production module is imported-and-called at the step boundary, and no business
logic lives in a step body (Mandate-12: each body is a single delegation).

``scenarios(...)`` binds via the RELATIVE path from this steps/ module. Each
step decorator's literal text is unique within this feature directory (S1
step-text-uniqueness invariant) and disjoint from the slice-04 / slice-07 step
files' literals -- no literal is declared with its own body in two files.

Active-RED scaffold (ADR-025 + ADR-028, atdd_pure -- NOT @skip): until DELIVER
ships the ``discuss_review_gate.py`` core + the ``DiscussReviewReader`` port +
ledger adapter + the review-gate branch in ``SubagentStopService``, the
production service has no PO-review check, so the discuss-wave return is
ALLOWED where a VETOED / INDETERMINATE block is expected -- AT-1 / AT-2 / AT-4
fail with a semantic ``AssertionError`` (the gate did not block), never a
collection / import / setup error (pre-DELIVER fail-for-right-reason gate).
AT-3 (signed-verified APPROVED + artefact-current -> allow) is
preservation-GREEN at HEAD, exactly like slice-07's AT-6: it pins the §22.0
PASS = no-objection invariant and MUST stay green after DELIVER.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from pytest_bdd import given, scenarios, then, when

from .composition_slice_07b import PoReviewGateComposition
from .domain_types_slice_07b import PoReviewVerdictShape


scenarios("../slice-07b-po-review-veto-gate.feature")


@pytest.fixture
def po_review_gate() -> PoReviewGateComposition:
    return PoReviewGateComposition()


# --- Given -------------------------------------------------------------------


@given("a discuss-wave return carrying a needs-revision product-owner review verdict")
def given_needs_revision_verdict(
    po_review_gate: PoReviewGateComposition, tmp_path: Path
) -> None:
    po_review_gate.given_discuss_return_with_po_review(
        tmp_path, PoReviewVerdictShape.NEEDS_REVISION
    )


@given("a discuss-wave return with no recorded product-owner review verdict")
def given_absent_verdict(
    po_review_gate: PoReviewGateComposition, tmp_path: Path
) -> None:
    po_review_gate.given_discuss_return_with_po_review(
        tmp_path, PoReviewVerdictShape.ABSENT
    )


@given(
    "a discuss-wave return carrying an approved product-owner review verdict for the current artefact"
)
def given_approved_current_verdict(
    po_review_gate: PoReviewGateComposition, tmp_path: Path
) -> None:
    po_review_gate.given_discuss_return_with_po_review(
        tmp_path, PoReviewVerdictShape.APPROVED_CURRENT
    )


# --- When --------------------------------------------------------------------


@when("the discuss-wave handoff is checked against the recorded review verdict")
def when_discuss_handoff_checked(po_review_gate: PoReviewGateComposition) -> None:
    po_review_gate.when_discuss_handoff_checked()


# --- Then --------------------------------------------------------------------


@then("the handoff to design is blocked by the reviewer veto")
def then_handoff_blocked_by_reviewer_veto(
    po_review_gate: PoReviewGateComposition,
) -> None:
    po_review_gate.then_handoff_blocked_by_reviewer_veto()


@then(
    "the veto names the reviewer decision read from the recorded verdict, never the agent's say-so"
)
def then_veto_names_reviewer_decision(
    po_review_gate: PoReviewGateComposition,
) -> None:
    po_review_gate.then_veto_names_reviewer_decision()


@then("the handoff to design is blocked degrade-loud as indeterminate")
def then_handoff_blocked_indeterminate(
    po_review_gate: PoReviewGateComposition,
) -> None:
    po_review_gate.then_handoff_blocked_indeterminate()


@then("the indeterminate block never masquerades as a reviewer veto")
def then_indeterminate_never_masquerades(
    po_review_gate: PoReviewGateComposition,
) -> None:
    po_review_gate.then_indeterminate_never_masquerades_as_veto()


@then("the handoff to design is allowed as no objection found from the review")
def then_handoff_allowed_no_objection_from_review(
    po_review_gate: PoReviewGateComposition,
) -> None:
    po_review_gate.then_handoff_allowed_no_objection_from_review()
