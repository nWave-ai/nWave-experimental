"""Step definitions -- slice-01: BypassCause StrEnum value-object extraction.

F-PISTA1V2-PHASE225-BYPASSCAUSE slice-01. Layer 3 (subprocess + FS acceptance):
the production gate script `scripts/hooks/spine_ledger_gate.py` is the driving
port for AT-1 and AT-3; AT-2 imports the `BypassCause` symbol from the same
production module under the parity-unit exemption (Mandate-13 footnote — see
at-scaffold-notes-slice-01.md for the exemption rationale and the
fix-installer-self-referential-des-import slice-01 precedent).

Example-based (Mandate 11 -- layer 3 sad paths enumerated explicitly). Three
ATs: a five-row parametrize outline (AT-1 cause-branch parity), one
type-safety scenario (AT-2 enum-shape + per-member values), one regression
walking-skeleton (AT-3 predecessor-suite all-pass). PBT precluded by
OR-reduction (Mandate 9 v2: real I/O on subprocess + filesystem + ledger
writer + pytest subprocess).

Step bodies delegate to `BypassCauseFixture` (Mandate-12 criterion 3:
≤2 statements per body, final statement is a composition method call,
zero control flow in step bodies).

RED-for-the-right-reason:

  * AT-1 parity outline -- the gate ships literal `_CAUSE_*` constants today;
    the outline PASSES on the current implementation (cause strings already
    match the documented vocabulary). RED-edge fires only if DELIVER's refactor
    drifts a cause-value spelling. Negative regression guard: GREEN before AND
    after DELIVER, RED only on regression.

  * AT-2 type-safety -- the `BypassCause` symbol does NOT exist on the
    production module today. `inspect_value_object()` catches the ImportError
    and surfaces it via `import_error` field; `assert_value_object_is_str_enum`
    raises AssertionError on the first Then step. That is the correct RED:
    assertion fires because the StrEnum extraction is unimplemented (Mandate 7
    RED-not-BROKEN).

  * AT-3 regression-zero -- the predecessor suite is GREEN today (15/15).
    `run_predecessor_suite()` runs pytest as a subprocess and asserts the
    documented 15-pass outcome. PASSING today; RED fires only if DELIVER's
    refactor regresses any predecessor scenario.

Mandate-13 (driving-port-only): AT-1 and AT-3 invoke production via real
subprocess (`python -m scripts.hooks.spine_ledger_gate` and `python -m pytest`
respectively). AT-2 imports the `BypassCause` symbol -- parity-unit exemption
documented in at-scaffold-notes-slice-01.md; pattern mirrors
fix-installer-self-referential-des-import slice-01 AT-2 (`Scenario Outline:
inline canonical_tree_hash byte-matches the SSOT module-level function`).

Skip-at-file-head (ADR-028 + friction #26): the whole module is gated under
`pytestmark = pytest.mark.skip(...)` so DELIVER's crafter unskips ONE scenario
at a time during the inner TDD loop. The skip carries a `reason` naming the
slice and the DELIVER-side unskip protocol.
"""

from __future__ import annotations

import os
from collections.abc import Iterator
from pathlib import Path

import pytest
from pytest_bdd import given, parsers, scenarios, then, when

from .composition import (
    BypassCauseFixture,
    GateInvocation,
    ValueObjectInspection,
)


# Skip-at-file-head retired by DELIVER A_GREEN_ATS slice-01: the BypassCause
# StrEnum extraction has shipped; AT-1 + AT-2 + AT-3 all GREEN under the
# refactored gate. The historical RED-edge scaffold (AT-2 fired AssertionError
# on the missing `BypassCause` symbol) is preserved in commit history; AT-1
# + AT-3 stay GREEN as negative regression guards across future slices.


scenarios("../slice-01-bypass-cause-enum.feature")


# --- Fixtures --------------------------------------------------------------


@pytest.fixture
def fixture(tmp_path: Path) -> Iterator[BypassCauseFixture]:
    """Per-test BypassCause fixture rooted at an isolated tmp target.

    Yields a fresh fixture, then pops `NWAVE_SPINE_LEDGER_GATE_BYPASS` on
    teardown so AT-1's env-bypass row cannot leak the var into a sibling
    test's subprocess pytest invocation. The pre-commit hook runs
    `pytest -n 2 --dist=loadgroup`; without the teardown pop the env-var
    leaks across xdist workers, AT-3's pytest subprocess inherits
    `env={**os.environ}` and short-circuits every predecessor kill-switch
    scenario through the env-bypass branch — teardown error + intermittent
    regression-suite RED (caught empirically pre-commit 2026-05-28).
    """
    yield BypassCauseFixture(target_root=tmp_path / "target")
    os.environ.pop("NWAVE_SPINE_LEDGER_GATE_BYPASS", None)


@pytest.fixture
def result_box() -> dict[str, object]:
    """Carrier for captured invocations across When/Then steps."""
    return {}


# --- Background ------------------------------------------------------------


@given("the spine-ledger gate ships seven cause vocabulary constants")
def given_seven_cause_constants(fixture: BypassCauseFixture) -> None:
    # Documents the SUT vocabulary. No filesystem side-effect; composition
    # method is invoked for Pillar 1 readability (the assertion would fire
    # in `assert_value_object_member_value` if the cause set drifted).
    _ = fixture


@given(
    "every constant value participates in either a stdout verdict or an audit event payload"
)
def given_constants_emit_observable(fixture: BypassCauseFixture) -> None:
    # Documents the observable surface (stdout + audit log). AT-1 verifies
    # stdout cause; the audit-log slice-00 contract is the predecessor
    # feature's responsibility (AT-3 regression guard).
    _ = fixture


@given(
    "the predecessor feature `atdd-spine-ledger-enforcement-gate-v2` shipped "
    "15 acceptance tests pinning the existing cause vocabulary"
)
def given_predecessor_at_count(fixture: BypassCauseFixture) -> None:
    # Anchors AT-3's expected pass count to the documented 15.
    assert fixture.predecessor_at_count() == 15


# --- AT-1 cause-branch parity (5-row parametrize outline) ------------------


@given(
    parsers.parse(
        'a target machine wired to exercise the "{branch}" cause branch of the gate'
    )
)
def given_wired_branch(fixture: BypassCauseFixture, branch: str) -> None:
    fixture.wire_branch(branch)


@when("the operator runs the spine-ledger gate against the staged invocation inputs")
def when_run_gate(fixture: BypassCauseFixture, result_box: dict[str, object]) -> None:
    result_box["invocation"] = fixture.run_gate()


@then(parsers.parse('the gate\'s stdout JSON carries cause "{expected_cause}"'))
def then_stdout_carries_cause(
    fixture: BypassCauseFixture,
    result_box: dict[str, object],
    expected_cause: str,
) -> None:
    fixture.assert_branch_cause(result_box["invocation"], expected_cause)  # type: ignore[arg-type]


@then("the gate's stdout is a valid single-line JSON verdict")
def then_stdout_single_line_json(
    fixture: BypassCauseFixture, result_box: dict[str, object]
) -> None:
    fixture.assert_stdout_is_single_line_json(result_box["invocation"])  # type: ignore[arg-type]


@then("the gate's exit code matches the documented branch contract")
def then_exit_code_matches_contract(
    fixture: BypassCauseFixture, result_box: dict[str, object]
) -> None:
    invocation: GateInvocation = result_box["invocation"]  # type: ignore[assignment]
    expected = BypassCauseFixture.expected_exit_code_for_branch(
        _resolve_branch_from_cause(invocation.stdout_json.get("cause", ""))
    )
    fixture.assert_branch_exit_code(invocation, expected)


def _resolve_branch_from_cause(cause: str) -> str:
    """Reverse-map a stdout cause value to its branch table key.

    The `Then` step has no direct handle to the branch parametrize value
    (pytest-bdd outline expansion does not propagate the row scalar past the
    Given step). Using the cause value as the lookup key keeps the step body
    pure-delegation while preserving universe-bound mapping (cause IS the
    port-exposed observable per Mandate 8).
    """
    for branch in (
        "env-bypass",
        "file-bypass",
        "dormant",
        "block-refused",
        "block-allowed",
    ):
        if BypassCauseFixture.expected_cause_for_branch(branch) == cause:
            return branch
    raise AssertionError(
        f"Stdout cause {cause!r} does not match any documented branch. "
        f"The gate may have regressed on the cause vocabulary."
    )


# --- AT-2 type-safety value-object inspection ------------------------------


@given('the spine-ledger gate module exposes a value object named "BypassCause"')
def given_value_object_exposed(fixture: BypassCauseFixture) -> None:
    # Documents the contract; the assertion fires in the Then-side helper
    # `assert_value_object_is_str_enum` if the symbol is absent. No filesystem
    # setup needed.
    _ = fixture


@when("the maintainer inspects the value object's type and members")
def when_inspect_value_object(
    fixture: BypassCauseFixture, result_box: dict[str, object]
) -> None:
    result_box["inspection"] = fixture.inspect_value_object()


@then("BypassCause is a subclass of StrEnum")
def then_is_str_enum(
    fixture: BypassCauseFixture, result_box: dict[str, object]
) -> None:
    fixture.assert_value_object_is_str_enum(result_box["inspection"])  # type: ignore[arg-type]


@then(
    parsers.parse(
        'BypassCause carries a member "{member_name}" whose value is "{expected_value}"'
    )
)
def then_member_value(
    fixture: BypassCauseFixture,
    result_box: dict[str, object],
    member_name: str,
    expected_value: str,
) -> None:
    fixture.assert_value_object_member_value(
        result_box["inspection"],  # type: ignore[arg-type]
        member_name,
        expected_value,
    )


# --- Unused-imports guard (ruff F401) --------------------------------------

# Type re-exports for downstream slice authors who extend this step set.
_TYPE_REEXPORTS = (GateInvocation, ValueObjectInspection)
