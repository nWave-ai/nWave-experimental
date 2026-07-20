# @feature-des-refactor-fixer-swarm
# @slice-01
"""Pile-grammar refusal ATs -- fix-refactor-pile-grammar-undocumented, slice-01.

RCA: Vera (`des-refactor-fixer-swarm` slice-01 EXAMINE) tried FIVE distinct
`techdebt.md` shapes (checkbox, dash, inline, structured, nested) and all
FIVE were rejected with `"0 parsed -- ... does not match the item grammar"`.
`des refactor` never states what the grammar IS, so the CLI's own promise
(drain one pile item) cannot even start, and a hand-writing operator has no
way to learn what the parser accepts. 23 pre-existing green ATs missed this
because every one of them CONSTRUCTS the pile file itself (it knows the
grammar by construction) -- THE FIXTURE KNOWS THE FORMAT, THE USER DOES NOT.

Layer 2 in-process (`composition.call_refactor_main_in_process`) -- drives
the REAL `des.cli.refactor.main` entry directly, no interpreter fork;
subprocess-e2e stays reserved for the ONE `@walking_skeleton` in
test_slice_01_walking_skeleton.py. `capsys` captures the CLI's OWN
stdout/stderr on the SAME call that triggers the refusal -- the exact
surface an operator is already looking at, never a doc they would have to
know to open (negative oracle (a): a fix that only documents the grammar in
prose elsewhere never touches this capture, so it stays RED).

RED-scaffold note: `des.cli.refactor.main`/`_no_items_reason` already names
that a line was "skipped" but never renders the grammar itself, never quotes
a concrete valid example, never names a producing tool (or says honestly
that none exists), and returns exit 0 for a pile whose only content could
not be understood -- every assertion below fails for one of those genuine,
already-implemented-but-incomplete reasons, never a collection/import error.

covers: R1, R2, R3, R4, R5, R6
"""

from __future__ import annotations

import pytest

# Defensive pre-import (module-collection time, OUTSIDE any capsys capture):
# see test_slice_01_observability.py's identical note -- keeps the runtime
# freshness gate's one-shot stderr event out of every test's captured output
# below regardless of collection/execution order.
from des.cli.refactor import main as _preimport_refactor_main  # noqa: F401

from .composition import RefactorSwarmComposition
from .domain_types import EntryGateAgentVerdict


pytestmark = pytest.mark.acceptance

# The load-bearing tokens of the real item grammar (`_ITEM_LINE_RE`,
# src/des/domain/refactor/pile.py). A refusal that merely describes the
# shape in English without these literal symbols has not taught the
# operator anything they can copy-paste.
_GRAMMAR_TOKENS = ("- [ ]", "paradigm=", 'defect="', 'proposed_solution="')


# --- AT-1 (the diagnosed defect): the refusal SHOWS the grammar ------------


def test_unparseable_pile_refusal_shows_the_grammar_with_a_concrete_example(
    tmp_path, capsys
):
    """covers: R1

    Given a pile whose only content line fails the item grammar, When
    `des refactor` runs, Then the refusal itself (stdout/stderr of THIS
    call) renders the grammar's literal shape -- every load-bearing token
    (`- [ ]`, `paradigm=`, `defect="`, `proposed_solution="`) -- so an
    operator can copy a working line without reading source code or a
    separate doc.

    CONTRACT_SHAPE: bounded-change
    """
    composition = RefactorSwarmComposition(tmp_path)
    composition.init_git_repo()
    composition.seed_pile_with_unparseable_line(
        "- [ ] this-line-does-not-match-the-item-grammar-at-all"
    )

    exit_code = composition.call_refactor_main_in_process(agent_cmd="true")
    captured = capsys.readouterr()
    combined = captured.out + captured.err

    missing = [token for token in _GRAMMAR_TOKENS if token not in combined]
    assert not missing, (
        "the refusal must render the item grammar's literal shape so an "
        f"operator can copy a working line; missing token(s) {missing!r} "
        f"from what was actually printed: {combined!r} (exit_code={exit_code})"
    )


def test_unparseable_pile_refusal_names_the_exact_line_that_failed(tmp_path, capsys):
    """covers: R2

    Given a pile whose only content line fails the item grammar, When
    `des refactor` runs, Then the refusal quotes the OFFENDING LINE
    VERBATIM -- an operator with a multi-line hand-written pile must be able
    to find which of their lines is wrong without re-deriving the grammar
    against every line themselves.

    CONTRACT_SHAPE: bounded-change
    """
    composition = RefactorSwarmComposition(tmp_path)
    composition.init_git_repo()
    offending_line = "- [ ] TD-9: not-even-close-to-the-grammar"
    composition.seed_pile_with_unparseable_line(offending_line)

    composition.call_refactor_main_in_process(agent_cmd="true")
    captured = capsys.readouterr()
    combined = captured.out + captured.err

    assert offending_line in combined, (
        "the refusal must quote the exact offending line verbatim so an "
        f"operator can find it in their own file; expected {offending_line!r} "
        f"inside: {combined!r}"
    )


def test_unparseable_pile_refusal_routes_to_a_producing_tool_or_states_none_exists(
    tmp_path, capsys
):
    """covers: R4

    Given a pile whose only content line fails the item grammar, When
    `des refactor` runs, Then the refusal EITHER names a real command that
    writes a grammar-valid pile item (GDP-4: the system produces the
    checked artifact, the operator never hand-assembles it from a
    description) OR -- if no such command exists yet -- says so honestly,
    never leaving the operator to guess whether one exists.

    CONTRACT_SHAPE: bounded-change
    """
    composition = RefactorSwarmComposition(tmp_path)
    composition.init_git_repo()
    composition.seed_pile_with_unparseable_line(
        "- [ ] this-line-does-not-match-the-item-grammar-at-all"
    )

    composition.call_refactor_main_in_process(agent_cmd="true")
    captured = capsys.readouterr()
    lowered = (captured.out + captured.err).lower()

    names_a_producing_tool = any(
        marker in lowered for marker in ("scaffold", "--init", "generate", "template")
    )
    states_none_exists_honestly = (
        "no" in lowered
        and any(word in lowered for word in ("tool", "command", "scaffold"))
        and any(word in lowered for word in ("yet", "exists", "available"))
    )
    assert names_a_producing_tool or states_none_exists_honestly, (
        "the refusal must either name a real producing tool for a valid "
        "pile item, or honestly state that none exists yet -- never leave "
        f"the operator to guess; got: {captured.out + captured.err!r}"
    )


def test_unparseable_pile_refusal_exits_non_zero_never_a_silent_zero(tmp_path, capsys):
    """covers: R3

    Given a pile whose only content line fails the item grammar, When
    `des refactor` runs, Then it exits NON-ZERO -- the exact "prints a
    failure and exits 0" defect class caught twice this week. Asserted
    standalone (not folded into the content assertions above) so a fix that
    gets the message right but leaves the exit code wrong is still caught.

    CONTRACT_SHAPE: bounded-change
    """
    composition = RefactorSwarmComposition(tmp_path)
    composition.init_git_repo()
    composition.seed_pile_with_unparseable_line(
        "- [ ] this-line-does-not-match-the-item-grammar-at-all"
    )

    exit_code = composition.call_refactor_main_in_process(agent_cmd="true")

    assert exit_code != 0, (
        "a pile whose only content could not be understood is a refusal, "
        f"not a quiet no-op; got exit_code={exit_code}"
    )


# --- AT-5 (negative oracle (b), preservation guard): a VALID pile still ----
# parses -- the fix must not tighten the grammar while explaining it -------


def test_a_grammar_valid_pile_still_drains_normally(tmp_path, capsys):
    """covers: R5

    Given a pile with one grammar-valid item (unchanged shape), When
    `des refactor` runs, Then the item still drains end to end and exits 0
    -- the fix must ADD grammar teaching to the refusal path, never tighten
    or otherwise perturb the accept path for content that already matches
    the grammar. Expected GREEN both before and after the fix (leak-guard
    companion, mirrors the `fix-dispatch-distill-by-construction` /
    `f-vscc-prefactoring-exit` precedent of a preservation twin alongside a
    RED defect pin).

    CONTRACT_SHAPE: unbounded-preservation
    """
    composition = RefactorSwarmComposition(tmp_path)
    composition.init_git_repo()
    composition.prepare_clean_integration_branch()
    composition.seed_pile_item(item_id="TD-001")

    exit_code = composition.call_refactor_main_in_process(
        agent_cmd=composition.agent_cmd_emitting_verdict(
            EntryGateAgentVerdict.REFACTOR_SAFE
        )
    )
    captured = capsys.readouterr()

    assert exit_code == 0, (
        "a grammar-valid pile item must still drain and exit 0 after this "
        f"fix; got exit_code={exit_code}, stderr={captured.err!r}"
    )
    assert not composition.pile_contains("TD-001"), (
        "TD-001 must still be removed from techdebt.md once drained"
    )
    assert composition.paid_contains("TD-001"), (
        "TD-001 must still be recorded in paidtechdebt.md once drained"
    )


# --- AT-6 (silent-swallow repair): a skipped line must surface even when --
# a real item in the same pile successfully drains -------------------------


def test_a_skipped_line_is_still_reported_even_when_a_sibling_item_drains(
    tmp_path, capsys
):
    """covers: R6

    Given a pile with ONE grammar-valid item AND one line that fails the
    grammar, When `des refactor` runs, Then the valid item still drains
    (real work happens, exit 0) AND the malformed sibling line is still
    named on stdout/stderr -- `DrainResult.skipped_lines` is populated by
    the parser regardless of whether any item parsed, but `_report` today
    only ever surfaces it down the `result.item_id is None` branch, so a
    malformed line sitting NEXT TO a valid one is silently swallowed the
    instant that valid item drains. A silently-dropped operator mistake is
    the same GDP-6 (no-silent-wrong) class as the primary defect, just on
    the mixed-pile path instead of the all-unparseable path.

    CONTRACT_SHAPE: bounded-change
    """
    composition = RefactorSwarmComposition(tmp_path)
    composition.init_git_repo()
    composition.prepare_clean_integration_branch()
    bad_line = "- [ ] this-sibling-line-does-not-match-the-item-grammar"
    composition.seed_pile_with_valid_item_and_unparseable_line(
        item_id="TD-001", bad_line=bad_line
    )

    exit_code = composition.call_refactor_main_in_process(
        agent_cmd=composition.agent_cmd_emitting_verdict(
            EntryGateAgentVerdict.REFACTOR_SAFE
        )
    )
    captured = capsys.readouterr()
    combined = captured.out + captured.err

    assert exit_code == 0, (
        "the valid sibling item must still drain successfully; got "
        f"exit_code={exit_code}, stderr={captured.err!r}"
    )
    assert composition.paid_contains("TD-001"), (
        "TD-001 must still be recorded in paidtechdebt.md once drained"
    )
    assert bad_line in combined, (
        "the malformed sibling line must be named on stdout/stderr even "
        "though a real item in the same pile successfully drained -- it "
        f"must never be silently swallowed; got: {combined!r}"
    )
