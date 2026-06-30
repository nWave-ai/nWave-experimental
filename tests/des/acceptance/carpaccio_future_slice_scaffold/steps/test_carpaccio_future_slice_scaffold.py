"""Step definitions: E2 contract gate scopes collection to shipped+entering slices.

Feature: fix-carpaccio-future-slice-scaffold-blocks-commit (C3, cohort S).

The E2 feature-scoped contract gate (``run_contract_gate``, the
``_mode_feature_scoped`` path, run_contract_gate.py:1356) today collects ALL the
feature's ``@feature-{id}`` ``.feature`` scenarios under the scope directories
-- including a not-yet-entered ``@slice-02`` active-RED scaffold. So a non-final
slice-01 commit fails E2 (exit 2). The gate ALREADY receives ``--entering-slice``
but consumes it only for the M-8 intersection check (line 1397), NOT to narrow
the ``_collect_node_ids`` collection (lines 1409-1411). The fix scopes the
collection to shipped+entering slices.

Layer 3 (subprocess / FS acceptance). Example-only, no PBT machinery
(Mandate 9/11). Step bodies delegate to ``FutureSliceScaffoldComposition``; no
inline business logic (Mandate-12 criterion 3). The fixture feature tree is
hermetic under ``tmp_path`` -- it NEVER lands as a real ``tests/**/*.feature``
in this repo (the exact pollution bug class).

atdd_pure active-RED contract: AC-1 (exit-0) and AC-2 (slice-02 excluded) FAIL
at HEAD for the RIGHT reason -- the gate runs the whole feature scope, so it
collects + runs the slice-02 RED driver (exit 2) and the slice-02 tag IS in the
collected set. AC-3/AC-4 are live-green preservation guards. The bindings
import the production CLI directly, so a RED here is a business-logic gap
(wrong exit / wrong collected set), never an ImportError.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from pytest_bdd import given, parsers, scenarios, then, when
from tests.common.state_delta import assert_state_delta, unchanged

from .composition import FutureSliceScaffoldComposition, GateRun
from .domain_types import SliceId, SliceShape


scenarios("../slice-01-carpaccio-future-slice-scaffold.feature")


@pytest.fixture
def composition(tmp_path: Path) -> FutureSliceScaffoldComposition:
    """Production-wired composition over a hermetic tmp_path fixture tree."""
    return FutureSliceScaffoldComposition(root=tmp_path / "target")


@pytest.fixture
def run_box() -> dict[str, object]:
    """Carrier for the gate run + the pre-run universe snapshot."""
    return {}


# --- Given -------------------------------------------------------------------


@given("a feature with slice-01 entering and a slice-02 active-RED scaffold on disk")
def given_non_final_with_future_red(
    composition: FutureSliceScaffoldComposition,
) -> None:
    composition.build_fixture_tree(SliceShape.NON_FINAL_WITH_FUTURE_RED)


@given(
    parsers.parse(
        'a feature whose single shipped slice "{slice_id}" is the final entering slice'
    )
)
def given_final_single(
    composition: FutureSliceScaffoldComposition, slice_id: str
) -> None:
    composition.build_fixture_tree(SliceShape.FINAL_SINGLE)


# --- When --------------------------------------------------------------------


@when(parsers.parse('the E2 contract gate runs for entering slice "{slice_id}"'))
def when_gate_runs(
    composition: FutureSliceScaffoldComposition,
    run_box: dict[str, object],
    slice_id: str,
) -> None:
    run_box["universe_before"] = composition.capture_universe()
    run_box["run"] = composition.run_contract_gate_for(SliceId(slice_id))


# --- Then --------------------------------------------------------------------


def _run(run_box: dict[str, object]) -> GateRun:
    return run_box["run"]  # type: ignore[return-value]


@then("the contract gate passes")
def then_gate_passes(run_box: dict[str, object]) -> None:
    run = _run(run_box)
    assert run.exit_code == 0, (
        "the feature-scoped contract gate must PASS (exit 0) for a non-final "
        "entering slice with a future-slice RED scaffold present; "
        f"got exit {run.exit_code}:\n{run.output}"
    )


@then(
    parsers.parse(
        "the gate collects only the {expected:d} shipped+entering slice node, "
        "not the future scaffold"
    )
)
def then_collects_only_entering(run_box: dict[str, object], expected: int) -> None:
    count = _run(run_box).collected_node_count
    assert count == expected, (
        "the feature-scoped gate must collect ONLY the shipped+entering slice "
        f"node(s) ({expected}); the not-yet-entered future-slice scaffold must "
        f"NOT be pulled into the entering slice-01 scope. Collected node count "
        f"was {count} (HEAD pulls the whole feature scope, including slice-02)."
    )


@then(parsers.parse('the collected scope excludes the future slice "{slice_id}"'))
def then_scope_excludes_future(run_box: dict[str, object], slice_id: str) -> None:
    collected = _run(run_box).collected_slices
    assert slice_id not in collected, (
        f"the future slice {slice_id!r} must NOT appear in the collected scope "
        f"for an entering slice-01 gate; collected slices were {sorted(collected)}"
    )


@then(parsers.parse('the collected scope includes the entering slice "{slice_id}"'))
def then_scope_includes_entering(run_box: dict[str, object], slice_id: str) -> None:
    collected = _run(run_box).collected_slices
    assert slice_id in collected, (
        f"the entering slice {slice_id!r} must appear in the collected scope; "
        f"collected slices were {sorted(collected)}"
    )


@then("no skip marker is added to the future slice feature file")
def then_no_skip_pollution(
    composition: FutureSliceScaffoldComposition,
    run_box: dict[str, object],
) -> None:
    # Mandate 8: the fix lives in the GATE, not the AT files. Running the gate
    # must leave the future-slice `.feature` file byte-unchanged -- in
    # particular it must add no `@skip`/`@pending` token (the atdd_pure
    # never-@skip canon). The universe is the future-slice file text.
    assert not composition.future_slice_has_skip_marker(), (
        "the fix must add NO @skip/@pending marker to any future-slice "
        ".feature file -- the scope lives in the gate, not the AT files"
    )
    assert_state_delta(
        before=run_box["universe_before"],  # type: ignore[arg-type]
        after=composition.capture_universe(),
        universe={"future_slice.feature_text"},
        expected={"future_slice.feature_text": unchanged()},
    )
