# @feature-fix-drain-single-item-silent-noop
# @slice-01
"""A BLOCKED single-item drain must be REPORTED, never a silent exit 0.

RCA (reproduced against a synthetic repo): `des refactor --pile <pile>
--agent-cmd <cmd>` on a pile holding ONE valid pending item whose drain is
BLOCKED (not refused) exits 0 having printed nothing at all. The captured
`DrainResult` was::

    drained=False  item_id='TD-001'  merged=False
    merge_blocked_reason='EntryGateVerdictMissing'  reason=None

`des.cli.refactor._report` branches on `result.reason`, then `result.drained`,
then `result.item_id is None`. An item that WAS parsed but did NOT drain and
carries no `reason` matches NONE of them and falls through to the bare
`return 0` -- the blocking reason sits unread in `merge_blocked_reason`. The
sibling `_report_batch` already gets this right (`result.reason or
result.merge_blocked_reason`), so the single-item path is the odd one out.
Exit 1 for a blocked drain is a CONFORMANCE RESTORATION: `nWave/gates/
refactor.yaml` has declared `DrainRefused -> exit_code: 1` since slice-01 and
this path never conformed.

WHY THE MATRIX IS DERIVED, NOT HAND-LISTED. Six silent paths accumulated in
`_report` precisely because its observability was verified by hand-picked
example. So the scenarios below are enumerated FROM `DrainResult` ITSELF: the
reason-carrying fields are read out of the dataclass at import time
(`_reason_carrying_fields`), and `_ARRANGEMENTS` must bind a real,
operator-reachable Given to EVERY one of them. A future refusal branch that
adds (or renames) a reason-carrying field without an operator-visible witness
fails `test_a_reason_carrying_result_field_is_never_...` LOUDLY, before it can
become the seventh silent path.

Layer 2 in-process (`composition.call_refactor_main_in_process`) -- drives the
REAL `des.cli.refactor.main` entry, no interpreter fork; subprocess-e2e stays
reserved for the ONE `@walking_skeleton` in test_slice_01_walking_skeleton.py.
`capsys` captures the CLI's OWN stdout/stderr on the SAME call that produced
the blocked state -- the exact surface an operator is looking at. Every repo
is built fresh under `tmp_path` by the composition; nothing here ever points
at this project's own tree.

Expected-reason values are read back from PRODUCTION code
(`select_paradigm_lens(...).reason`, `ENTRY_GATE_VERDICT_MISSING`,
`EntryGateVerdict`), never re-typed as a literal -- a reworded refusal cannot
silently drift away from what this file asserts an operator must see.

RED-scaffold note: `merge_blocked_reason` is populated by the ALREADY
IMPLEMENTED entry gate, so every assertion below is reached and fails on a
genuine observable -- an empty capture and `exit_code == 0` where a refusal
was owed -- never a collection/import/fixture error.
"""

from __future__ import annotations

import dataclasses
from collections.abc import Callable
from dataclasses import dataclass

import pytest

# Defensive pre-import (module-collection time, OUTSIDE any capsys capture):
# importing `des.cli.refactor` triggers `des.cli`'s package `__init__`, which
# fires the runtime freshness gate's ONE-SHOT `des.runtime.freshness.*` stderr
# event on first import in this process. Forcing that one-shot print to happen
# here, before any test's `capsys` fixture is active, keeps every capture below
# free of freshness noise regardless of collection/execution order.
from des.application.refactor_drain_service import DrainResult
from des.cli.refactor import main as _preimport_refactor_main  # noqa: F401
from des.domain.refactor.entry_gate import (
    ENTRY_GATE_VERDICT_MISSING,
    EntryGateVerdict,
)
from des.domain.refactor.paradigm_select import select_paradigm_lens

from .composition import RefactorSwarmComposition
from .domain_types import EntryGateAgentVerdict


pytestmark = pytest.mark.acceptance


#: A declared paradigm token outside `RecognizedParadigm`'s closed set -- the
#: Given that drives a pre-worktree refusal whose reason lands in
#: `DrainResult.reason` (the branch `_report` already handles correctly).
_UNRECOGNIZED_PARADIGM = "banana-oriented"

#: The item id every arrangement seeds -- an operator with a multi-item pile
#: must be told WHICH item was blocked.
_ITEM_ID = "TD-001"


def _reason_carrying_fields() -> frozenset[str]:
    """Every `DrainResult` field that can carry a blocking reason, read out of
    the dataclass itself.

    The predicate is the field-naming convention the type already uses
    (`reason`, `merge_blocked_reason`). Renaming a reason field out of that
    convention, or adding a new one, changes this set -- and the exhaustiveness
    guard below turns that change into a LOUD failure rather than a silently
    unreported drain outcome.
    """
    return frozenset(
        field.name
        for field in dataclasses.fields(DrainResult)
        if field.name.endswith("reason")
    )


@dataclass(frozen=True)
class BlockedDrainArrangement:
    """One real, operator-reachable Given that drives `des refactor` into a
    non-drained outcome whose blocking reason lands in `reason_field`.

    `expected_reason` is a callable that asks PRODUCTION code what it would
    say, so the assertion tracks the real message instead of pinning a
    hand-copied literal.
    """

    reason_field: str
    label: str
    arrange: Callable[[RefactorSwarmComposition], None]
    agent_cmd: Callable[[RefactorSwarmComposition], str]
    expected_reason: Callable[[], str]


def _arrange_unrecognized_paradigm(composition: RefactorSwarmComposition) -> None:
    """A pile item declaring a paradigm outside the recognized closed set --
    refused BEFORE any worktree/agent invocation, reason in `DrainResult.reason`."""
    composition.init_git_repo()
    composition.prepare_clean_integration_branch()
    composition.seed_pile_item(item_id=_ITEM_ID, paradigm=_UNRECOGNIZED_PARADIGM)


def _arrange_missing_entry_gate_verdict(composition: RefactorSwarmComposition) -> None:
    """A grammar-valid item whose dispatched agent emits free-form commentary
    and NO recognized entry-gate verdict -- the item parses, work happens, the
    drain is BLOCKED at the entry gate, reason in `merge_blocked_reason`."""
    composition.init_git_repo()
    composition.prepare_clean_integration_branch()
    composition.seed_toy_passing_test()
    composition.seed_pile_item(item_id=_ITEM_ID)


#: One arrangement per reason-carrying field of `DrainResult`. The
#: exhaustiveness guard below asserts this registry covers the DERIVED set
#: exactly -- neither missing a field nor witnessing one that no longer exists.
_ARRANGEMENTS: tuple[BlockedDrainArrangement, ...] = (
    BlockedDrainArrangement(
        reason_field="reason",
        label="unrecognized-declared-paradigm",
        arrange=_arrange_unrecognized_paradigm,
        agent_cmd=lambda composition: composition.agent_cmd_emitting_verdict(
            EntryGateAgentVerdict.REFACTOR_SAFE
        ),
        expected_reason=lambda: select_paradigm_lens(_UNRECOGNIZED_PARADIGM).reason,
    ),
    BlockedDrainArrangement(
        reason_field="merge_blocked_reason",
        label="missing-entry-gate-verdict",
        arrange=_arrange_missing_entry_gate_verdict,
        agent_cmd=lambda composition: (
            composition.agent_cmd_emitting_no_recognized_verdict()
        ),
        expected_reason=lambda: ENTRY_GATE_VERDICT_MISSING,
    ),
)


# --- The exhaustiveness guard: the matrix is derived, never hand-picked ----


def test_a_reason_carrying_result_field_is_never_left_without_an_operator_visible_witness():
    """Given `DrainResult` declares the fields a blocked drain records its
    reason in, When this file's arrangement registry is compared against them,
    Then EVERY reason-carrying field is witnessed by a real Given that an
    operator can reach -- a new (or renamed) refusal field cannot be added
    without a scenario proving `des refactor` actually reports it.

    This is the guard that makes the scenarios below a MATRIX rather than a
    hand-picked pair: observability verified by example is exactly how six
    silent paths accumulated in `_report`.

    CONTRACT_SHAPE: unbounded-preservation
    """
    derived = _reason_carrying_fields()
    witnessed = frozenset(arrangement.reason_field for arrangement in _ARRANGEMENTS)

    assert derived, (
        "DrainResult declares no reason-carrying field at all -- the "
        "derivation predicate has gone blind and every scenario below is "
        "now vacuous"
    )
    assert derived == witnessed, (
        "every reason-carrying DrainResult field must have an arrangement in "
        "_ARRANGEMENTS driving the REAL CLI into that state, so no refusal "
        "shape can ship unreported; unwitnessed field(s): "
        f"{sorted(derived - witnessed)!r}, stale witness(es) for fields that "
        f"no longer exist: {sorted(witnessed - derived)!r}"
    )


# --- The matrix: every blocked shape is reported and exits non-zero --------


@pytest.mark.parametrize(
    "arrangement",
    _ARRANGEMENTS,
    ids=[arrangement.label for arrangement in _ARRANGEMENTS],
)
def test_a_blocked_drain_is_never_a_silent_no_op_whatever_field_carries_its_reason(
    tmp_path, capsys, arrangement: BlockedDrainArrangement
):
    """Given a pile whose single valid item cannot be drained, When
    `des refactor` runs, Then the operator SEES the blocking condition on
    stdout/stderr and the command exits NON-ZERO -- never the "printed
    nothing, exited 0, changed nothing" no-op that is indistinguishable from
    a successful run against an empty pile.

    Parametrized over the reason-carrying fields DERIVED from `DrainResult`,
    so a blocked shape cannot become reportable-in-principle yet unreported
    in practice.

    CONTRACT_SHAPE: bounded-change
    """
    composition = RefactorSwarmComposition(tmp_path)
    arrangement.arrange(composition)

    exit_code = composition.call_refactor_main_in_process(
        agent_cmd=arrangement.agent_cmd(composition)
    )
    captured = capsys.readouterr()
    combined = captured.out + captured.err
    expected_reason = arrangement.expected_reason()

    assert combined.strip() != "", (
        "a drain blocked with a reason in "
        f"DrainResult.{arrangement.reason_field} must tell the operator "
        "something -- got completely empty stdout AND stderr, the exact "
        f"silent no-op this test exists to forbid (exit_code={exit_code})"
    )
    assert expected_reason in combined, (
        "the blocking condition the drain actually recorded in "
        f"DrainResult.{arrangement.reason_field} must reach the operator's "
        f"terminal; expected to find {expected_reason!r} inside: {combined!r}"
    )
    assert "drained 1 item" not in combined.lower(), (
        "a blocked drain must never report itself as a completed drain; "
        f"got: {combined!r}"
    )
    assert exit_code != 0, (
        "an item that was parsed but could not be drained is a refusal, not "
        "a quiet success -- `nWave/gates/refactor.yaml` has declared "
        f"DrainRefused -> exit_code 1 since slice-01; got exit_code={exit_code}"
    )


# --- Actionability: the report explains, it does not echo a token ----------


def test_a_blocked_drain_report_explains_what_why_and_how_not_just_an_internal_token(
    tmp_path, capsys
):
    """Given a drain blocked because the dispatched agent emitted no
    recognized entry-gate verdict, When `des refactor` runs, Then its report
    names WHICH item was blocked (WHAT), shows at least one recognized verdict
    token so the operator learns what a valid agent answer looks like (WHY it
    was blocked), and either routes to a producing tool or states honestly
    that none exists (HOW) -- the standing "every failure explains what, why,
    how" mandate.

    Deliberately NOT satisfiable by echoing the bare internal token
    `EntryGateVerdictMissing`: that string contains no item id, no recognized
    verdict token, and no route forward. Modelled on the unparseable-pile
    refusal (`test_slice_01_pile_grammar_refusal.py`), including its honesty
    clause that no scaffolding tool exists.

    CONTRACT_SHAPE: bounded-change
    """
    composition = RefactorSwarmComposition(tmp_path)
    _arrange_missing_entry_gate_verdict(composition)

    composition.call_refactor_main_in_process(
        agent_cmd=composition.agent_cmd_emitting_no_recognized_verdict()
    )
    captured = capsys.readouterr()
    combined = captured.out + captured.err
    lowered = combined.lower()

    assert _ITEM_ID in combined, (
        "the report must name WHICH item was blocked -- an operator with a "
        "multi-item pile cannot act on an unattributed refusal; expected "
        f"{_ITEM_ID!r} inside: {combined!r}"
    )

    recognized_tokens_shown = [
        verdict.value for verdict in EntryGateVerdict if verdict.value in combined
    ]
    assert recognized_tokens_shown, (
        "the report must show at least one recognized entry-gate verdict "
        "token, so the operator learns what their agent was supposed to "
        "emit -- echoing the internal "
        f"{ENTRY_GATE_VERDICT_MISSING!r} token alone teaches nothing; got: "
        f"{combined!r}"
    )

    names_a_producing_tool = any(
        marker in lowered
        for marker in ("des ", "--agent-cmd", "template", "scaffold", "generate")
    )
    states_none_exists_honestly = (
        "no" in lowered
        and any(word in lowered for word in ("tool", "command", "scaffold"))
        and any(word in lowered for word in ("yet", "exists", "available"))
    )
    assert names_a_producing_tool or states_none_exists_honestly, (
        "the report must either route to a real command that fixes the "
        "blocked state, or honestly state that none exists yet -- never "
        f"leave the operator to guess the next step; got: {combined!r}"
    )
