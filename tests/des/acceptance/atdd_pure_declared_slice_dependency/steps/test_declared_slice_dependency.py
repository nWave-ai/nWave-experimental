"""Step definitions: slice-01 -- the declared slice-dependency order check.

slice-01 of `slice-dependency-declared` (mikado node D94, ADR-CARPACCIO-
DEPENDENCY-001). Max parametrize density (Mandate 9/11, layer-3 example-only):

  * walking-skeleton (@wiring_e2e @walking_skeleton) -- 1 example-based
    scenario: drive the real `handle_pre_tool_use` hook via the Claude Code
    JSON stdin protocol and assert a declared predecessor permits a dispatch
    the positional default alone would have blocked. Genuine end-to-end, not
    fixture-folded.
  * declared-predecessor-honored outline -- CT-2's two cases (K = N-1 no-op,
    K < N-1 genuine skip) collapsed into one decision table.
  * silent-fallback outline -- CT-1 + CT-7's degraded-read universe (absent /
    unreadable / section-absent / malformed-table / row-absent / annotation-
    empty feature-delta), all resolving to the SAME positional `slice-(N-1)`
    default, byte-identical to pre-feature behaviour.
  * malformed-declaration outline -- CT-3/CT-4/CT-5/CT-6's four malformed
    classes (multi-target, non-`slice-NN` shape, absent-from-plan target,
    self-/forward-reference), each set up so the TRUE positional predecessor
    IS verified (today's code would ALLOW) -- the malformed declaration must
    still BLOCK.
  * remedy-message scenario -- CT-2b: the block on an unresolved silent row
    names both the rebuild-predecessor path and the declare-depends-on
    alternative.

Layer 3 (in-process hook / composition-root acceptance) -- example-only sad
paths, no PBT machinery (Mandate 9/11). Step bodies delegate to
`DeclaredSliceDependencyComposition`; no inline logic (Mandate-12 criterion 3).

RED contract: `_carpaccio_order_block` still computes the predecessor as bare
`slice-(N-1)` arithmetic on this branch -- every DECLARED/MALFORMED scenario
fails RED for a real observed-verdict/event mismatch; the SILENT-fallback
outline's rows are byte-identical regression pins and may already be GREEN.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from pytest_bdd import given, parsers, scenarios, then, when

from .composition import DeclaredSliceDependencyComposition, InterceptOutcome
from .domain_types import (
    PLAN_SHAPE_BY_PHRASE,
    VERDICT_BY_PHRASE,
    SliceId,
)


scenarios("../declared-slice-dependency.feature")


@pytest.fixture
def composition(tmp_path: Path) -> DeclaredSliceDependencyComposition:
    """Production-wired declared-slice-dependency composition, tmp-rooted."""
    return DeclaredSliceDependencyComposition(tmp_path)


@pytest.fixture
def outcome_box() -> dict[str, InterceptOutcome]:
    """Carrier for the M8 order-check outcome."""
    return {}


def _outcome(outcome_box: dict[str, InterceptOutcome]) -> InterceptOutcome:
    return outcome_box["outcome"]


# --- Given -------------------------------------------------------------------


@given(parsers.parse("a crafter dispatch enters {slice_id}"))
def given_enter_slice(
    composition: DeclaredSliceDependencyComposition, slice_id: str
) -> None:
    composition.enter_slice(SliceId(slice_id))


@given(parsers.parse('a Slice Plan where {slice_id} declares "{annotation}"'))
def given_declared_annotation(
    composition: DeclaredSliceDependencyComposition, slice_id: str, annotation: str
) -> None:
    composition.declare_dependency(SliceId(slice_id), annotation)


@given(parsers.parse("the Slice Plan is {plan_shape}"))
def given_plan_shape(
    composition: DeclaredSliceDependencyComposition, plan_shape: str
) -> None:
    composition.apply_plan_shape(PLAN_SHAPE_BY_PHRASE[plan_shape])


@given(parsers.parse("{slice_id} carries a verified slice commit in the ledger"))
def given_verified(
    composition: DeclaredSliceDependencyComposition, slice_id: str
) -> None:
    composition.mark_verified(SliceId(slice_id))


@given(parsers.parse("{slice_id} carries no verified slice commit in the ledger"))
def given_unverified(
    composition: DeclaredSliceDependencyComposition, slice_id: str
) -> None:
    composition.mark_unverified(SliceId(slice_id))


# --- When --------------------------------------------------------------------


@when("the M8 carpaccio order check evaluates the dispatch")
def when_evaluate(
    composition: DeclaredSliceDependencyComposition,
    outcome_box: dict[str, InterceptOutcome],
) -> None:
    outcome_box["outcome"] = composition.evaluate()


@when("the real PreToolUse hook processes the dispatch")
def when_drive_real_hook(
    composition: DeclaredSliceDependencyComposition,
    outcome_box: dict[str, InterceptOutcome],
) -> None:
    outcome_box["outcome"] = composition.drive_real_pre_tool_use_hook()


# --- Then --------------------------------------------------------------------


@then(parsers.parse("the dispatch is {verdict}"))
def then_verdict(outcome_box: dict[str, InterceptOutcome], verdict: str) -> None:
    assert _outcome(outcome_box).verdict == VERDICT_BY_PHRASE[verdict]


@then(parsers.parse("the block names the {event} event"))
def then_block_event(outcome_box: dict[str, InterceptOutcome], event: str) -> None:
    assert _outcome(outcome_box).event == event


@then(
    "the block explains both the rebuild remedy and the declare-depends-on alternative"
)
def then_block_names_both_remedies(outcome_box: dict[str, InterceptOutcome]) -> None:
    outcome = _outcome(outcome_box)
    combined = f"{outcome.reason or ''} {outcome.how or ''}"
    # The pre-existing remedy (rebuild the predecessor's SliceCommitVerified
    # record) must still be present -- this scenario never DROPS the old cure.
    assert "SliceCommitVerified record" in combined
    # The NEW alternative (declare depends-on a genuinely-satisfied earlier
    # slice) must ALSO be present -- CT-2b's whole point.
    assert "depends-on" in combined
