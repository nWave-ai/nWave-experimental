"""Paradigm-invariant ATs -- slice-05 (des-refactor-fixer-swarm).

Value statement (feature-delta Slice Plan, slice-05): "A fixer never applies
the wrong paradigm's lens to an item -- FP tooling never touches an OOP
module and vice versa; an item with an unrecognized/absent declared paradigm
is refused BEFORE dispatch, never silently guessed."

Binds AT-9 (Architecture & Contract Tests table) + D10 ("Read from the pile
item's declared field; refuse (never guess/cross-apply) on mismatch or
absence"). Witnesses the C4 `paradigm` container (Container Diagram, DESIGN
section) via the REAL entry point -- `RefactorDrainService.drain_one` (Layer
3 composition, D11 dormant-seam reconciliation) -- asserting the observable
refusal effect, never by importing `select_paradigm_lens` directly. That
module (`src/des/domain/refactor/paradigm_select.py`) does NOT exist on disk
yet (CREATE_NEW, Reuse Analysis) and this suite deliberately does not import
it: the composition drives the STABLE, already-implemented `drain_one` entry,
and the absent invariant surfaces as a genuine, already-reachable semantic
assertion failure (MISSING_FUNCTIONALITY) rather than a collection error --
no RED scaffold file is required to make this suite RED-not-BROKEN (the
in-process active-RED pattern's P1-P4 invariants are satisfied by construction
since the entry point itself is fully real and already wired).

--- Paradigm-value convention (DISTILL-authored disambiguation) -------------

The recognized closed set is exactly `{"object-oriented", "functional"}`
(`DeclaredParadigm`, domain_types.py) -- matching this feature's own
already-committed pile-grammar precedent (`composition.py`'s
`_DEFAULT_PARADIGM`, `des/cli/refactor.py`'s grammar example) and this repo's
own `CLAUDE.md` "## Development Paradigm" convention. This is deliberately
NOT the `oop`/`fp` abbreviation pair used by the unrelated `nw-design
--paradigm=[auto|oop|fp]` CLI knob -- a different command, a different
vocabulary.

AT-9's "does not match the dispatched lens (or is absent/unrecognized)"
reduces, under D10's single-source read (the item's OWN declared field, no
second lens to compare against within this slice's scope), to ONE refusal
condition: **the declared token is not a member of the recognized closed
set.** "Mismatch" and "unrecognized" therefore collapse into the SAME
observable refusal path below (test B) -- there is no separate mechanism to
distinguish a near-miss abbreviation (`"OOP"`) from an outright garbage token
(`"quantum"`); both are simply "not a recognized paradigm."

--- Grammar-scope tension (flagged for the crafter/reviewer, NOT resolved
    here) -----------------------------------------------------------------

`pile.py`'s `_ITEM_LINE_RE` REQUIRES a `paradigm=<\\S+>` token to even
construct a `PileItem` -- a syntactically ABSENT paradigm field (the token
missing entirely, or containing whitespace) never reaches paradigm-select at
all: it fails the item grammar upstream and becomes a `skipped_line`
(pre-existing slice-01 observability contract), not a `PileItem` with an
empty/None `paradigm`. So AT-9's parenthetical "absent" cannot be witnessed
as a paradigm-select REFUSAL under the CURRENT grammar -- it is witnessed as
a grammar-layer skip instead (test F below pins this exact boundary). If a
future slice widens the grammar to make `paradigm=` optional (defaulting to
an empty string on the `PileItem`), THAT is the point `select_paradigm_lens`
would need to treat empty-string as its own "absent" branch of the refusal;
today, doing so is out of this slice's diagnosed scope (the grammar change
itself is not part of D10's Reuse Analysis footprint) and is called out here
rather than silently assumed.

Layer 3 composition (in-process, L2 default) throughout except the CLI
self-explaining-message pair (G1/G2), which use Layer 2 in-process
(`call_refactor_main_in_process`) to observe the real CLI's own stdout/stderr
-- the ONE `@walking_skeleton` subprocess seam for this entire feature stays
in `test_slice_01_walking_skeleton.py` (Mandate 5); nothing here re-forks an
interpreter.

covers: R-DES-REFACTOR-WS
"""

from __future__ import annotations

import pytest

# Defensive pre-import (module-collection time, OUTSIDE any capsys capture):
# see test_slice_01_observability.py's identical note -- keeps the runtime
# freshness gate's one-shot stderr event out of every test's captured output
# below regardless of collection/execution order.
from des.cli.refactor import main as _preimport_refactor_main  # noqa: F401

from .composition import RefactorSwarmComposition
from .domain_types import DeclaredParadigm


pytestmark = pytest.mark.acceptance

# Declared-paradigm tokens that are NOT members of the recognized closed set
# (`DeclaredParadigm`) -- garbage words, near-miss abbreviations, and
# wrong-case variants of a recognized value all collapse to the SAME
# refusal path (see module docstring's disambiguation note).
_UNRECOGNIZED_PARADIGMS = (
    pytest.param("quantum", id="garbage-word"),
    pytest.param("OOP", id="near-miss-abbreviation-oop"),
    pytest.param("FP", id="near-miss-abbreviation-fp"),
    pytest.param("Object-Oriented", id="wrong-case-of-recognized-value"),
    pytest.param("Functional", id="wrong-case-of-recognized-value-fp"),
    pytest.param("imperative", id="real-but-unrecognized-paradigm-word"),
    pytest.param("unspecified", id="semantically-absent-placeholder"),
)


# --- A: recognized paradigms proceed, neither lens cross-applied -----------


@pytest.mark.parametrize("paradigm", list(DeclaredParadigm))
def test_recognized_paradigms_proceed_to_dispatch_without_cross_application(
    tmp_path, paradigm: DeclaredParadigm
):
    """CONTRACT_SHAPE: pure-function

    Given an item whose declared paradigm IS a member of the recognized
    closed set, When the item drains, Then dispatch proceeds normally (a
    worktree is created and the item fully drains) AND the agent actually
    RECEIVES that item's own declared paradigm (not a hardcoded/mis-threaded
    one) -- for BOTH recognized values, never just the one
    ("object-oriented") every pre-slice-05 slice-01 test happened to
    exercise. The accept-side capture assertion closes a coverage gap an
    AT-review pass caught: a regression that hardcodes the lens (e.g. always
    threading "object-oriented" regardless of the item's own declared value)
    would still pass a drained-is-True-only assertion -- the "never
    cross-applied" promise must be witnessed on the ACCEPT side too, not
    only on the refusal side (tests B-D). Doubles as the preservation twin
    for the pre-existing object-oriented accept path (mirrors the
    pile-grammar-refusal suite's R5 leak-guard companion: the invariant must
    ADD a refusal path, never perturb the accept path already shipped in
    slice-01) while extending real coverage to the previously-unexercised
    functional lens for the first time.
    """
    composition = RefactorSwarmComposition(tmp_path)
    composition.init_git_repo()
    composition.prepare_clean_integration_branch()
    composition.seed_pile_item(item_id="TD-001", paradigm=paradigm.value)

    result = composition.run_drain_one_item(agent_cmd=composition.capturing_agent_cmd())

    assert result.drained is True, (
        f"a recognized declared paradigm ({paradigm.value!r}) must proceed "
        f"to dispatch and drain normally; got drained={result.drained!r}, "
        f"reason={result.reason!r}"
    )
    assert result.worktree_head_sha_at_creation is not None, (
        f"a recognized paradigm ({paradigm.value!r}) must reach worktree "
        "creation -- never refused"
    )
    assert not composition.pile_contains("TD-001")
    assert composition.paid_contains("TD-001")
    received = composition.observed_agent_cmd_input()
    assert paradigm.value in received, (
        f"the agent must receive THIS item's own declared paradigm "
        f"({paradigm.value!r}), never a hardcoded/mis-threaded lens; what "
        f"the agent actually received: {received!r}"
    )


# --- B: unrecognized/mismatched paradigms refuse before the worktree -------


@pytest.mark.parametrize("declared_paradigm", _UNRECOGNIZED_PARADIGMS)
def test_unrecognized_paradigm_refuses_dispatch_before_worktree_creation(
    tmp_path, declared_paradigm: str
):
    """CONTRACT_SHAPE: pure-function

    Given an item's declared paradigm is NOT a member of the recognized
    closed set (garbage word, near-miss abbreviation, or wrong-case variant
    of a recognized value), When the item is drained, Then dispatch is
    refused BEFORE any worktree is created -- `DrainResult.
    worktree_head_sha_at_creation` stays `None`, `drained`/`merged` stay
    `False`, `git worktree list` is unchanged, and the refusal carries a
    NAMED reason naming "paradigm" (never a silent skip, never a bare
    `False`) -- mirrors the WHAT/WHY/HOW shape the existing probe-failure
    refusals (`_probe_failure_reason`) already establish for this same
    pre-worktree refusal point.
    """
    composition = RefactorSwarmComposition(tmp_path)
    composition.init_git_repo()
    composition.seed_pile_item(item_id="TD-001", paradigm=declared_paradigm)
    worktrees_before = composition.worktree_list()

    result = composition.run_drain_one_item()

    assert result.drained is False, (
        f"an unrecognized declared paradigm ({declared_paradigm!r}) must "
        f"never report a drained item; got drained={result.drained!r}"
    )
    assert result.merged is False, (
        f"an unrecognized declared paradigm ({declared_paradigm!r}) must "
        "never be merged"
    )
    assert result.worktree_head_sha_at_creation is None, (
        f"an unrecognized declared paradigm ({declared_paradigm!r}) must "
        "refuse BEFORE any worktree is created; got "
        f"worktree_head_sha_at_creation={result.worktree_head_sha_at_creation!r}"
    )
    assert composition.worktree_list() == worktrees_before, (
        "a paradigm refusal must never create a worktree for the refused "
        f"item; git worktree list changed: before={worktrees_before!r}, "
        f"after={composition.worktree_list()!r}"
    )
    assert result.reason is not None, (
        "a paradigm refusal must carry a NAMED reason -- never a silent "
        "False with no explanation"
    )
    assert "paradigm" in result.reason.lower(), (
        "the refusal reason must name WHAT failed (the paradigm mismatch); "
        f"got reason={result.reason!r}"
    )


# --- C: the agent is never invoked for a refused item -----------------------


def test_unrecognized_paradigm_never_invokes_the_agent(tmp_path):
    """CONTRACT_SHAPE: pure-function

    Given an item's declared paradigm is unrecognized, When the drain runs,
    Then the configured `agent_cmd` is NEVER invoked -- the refusal fires
    strictly before agent dispatch, not merely before worktree creation.
    Uses the SAME `capturing_agent_cmd` observation marker
    `test_slice_01_walking_skeleton.py` uses to prove the agent DID run on a
    real drain; here its ABSENCE is the proof the agent never ran.
    """
    composition = RefactorSwarmComposition(tmp_path)
    composition.init_git_repo()
    composition.seed_pile_item(item_id="TD-001", paradigm="quantum")

    composition.run_drain_one_item(agent_cmd=composition.capturing_agent_cmd())

    assert composition.agent_was_never_invoked(), (
        "an item with an unrecognized declared paradigm must never reach "
        "agent dispatch -- the agent_cmd observation marker must not exist"
    )


# --- D: a refused item is never silently guessed to a default lens ---------


def test_unrecognized_paradigm_is_never_silently_rewritten_to_a_default_lens(
    tmp_path,
):
    """CONTRACT_SHAPE: pure-function

    Given an item's declared paradigm is unrecognized, When the drain
    refuses, Then the item's ORIGINAL declared paradigm token is left
    UNCHANGED in `techdebt.md` -- never silently rewritten/normalized to a
    guessed default (e.g. defaulting unrecognized input to
    "object-oriented"). A refusal must be visibly a refusal, never a covert
    correction.
    """
    composition = RefactorSwarmComposition(tmp_path)
    composition.init_git_repo()
    composition.seed_pile_item(item_id="TD-001", paradigm="quantum")

    composition.run_drain_one_item()

    assert composition.pile_contains("quantum"), (
        "the item's original (unrecognized) declared paradigm token must "
        "stay verbatim in techdebt.md -- a refusal must never silently "
        "rewrite it to a guessed default lens"
    )
    assert not composition.paid_contains("TD-001"), (
        "an item refused for an unrecognized paradigm must never be "
        "recorded in paidtechdebt.md"
    )


# --- F: the grammar-scope boundary -- a syntactically absent paradigm ------
# never reaches paradigm-select at all (it is caught as a skipped_line) -----


@pytest.mark.parametrize(
    "malformed_line",
    [
        pytest.param(
            '- [ ] TD-009: defect="some defect" proposed_solution="some fix"',
            id="paradigm-token-entirely-absent",
        ),
        pytest.param(
            '- [ ] TD-010: paradigm=object oriented defect="x" proposed_solution="y"',
            id="paradigm-value-contains-a-space",
        ),
    ],
)
def test_a_syntactically_absent_paradigm_field_never_reaches_paradigm_select(
    tmp_path, malformed_line: str
):
    """CONTRACT_SHAPE: bounded-change

    Given a pile line whose `paradigm=<token>` field is missing entirely, or
    whose value contains internal whitespace (breaking the `\\S+` token
    boundary), When `des refactor` parses the pile, Then the line fails the
    EXISTING item grammar (`_ITEM_LINE_RE`) upstream of paradigm-select --
    it is reported as a `skipped_line`, zero `PileItem` is constructed for
    it, and no worktree is created. This pins the grammar-scope boundary the
    module docstring flags: AT-9's parenthetical "absent" paradigm is
    witnessed HERE (a grammar-layer skip), never as a paradigm-select
    refusal -- the two are genuinely different observable landing points
    under the CURRENT grammar, and this AT exists so a future change to
    either layer cannot silently blur that boundary.
    """
    composition = RefactorSwarmComposition(tmp_path)
    composition.init_git_repo()
    composition.seed_pile_with_unparseable_line(malformed_line)
    worktrees_before = composition.worktree_list()

    result = composition.run_drain_one_item()

    assert result.drained is False
    assert result.item_id is None, (
        "a syntactically absent/malformed paradigm field must fail the item "
        "grammar entirely -- zero PileItem constructed, never a PileItem "
        "with an empty paradigm reaching paradigm-select"
    )
    assert result.parsed_count == 0
    assert malformed_line in result.skipped_lines, (
        "the malformed line must surface in skipped_lines (the existing "
        f"grammar-miss observability contract); got {result.skipped_lines!r}"
    )
    assert composition.worktree_list() == worktrees_before, (
        "a grammar-layer skip must never create a worktree either"
    )


# --- G: the CLI self-explains a paradigm refusal (WHAT/WHY/HOW) ------------


def test_paradigm_refusal_message_names_the_declared_value_and_the_recognized_set(
    tmp_path, capsys
):
    """CONTRACT_SHAPE: bounded-change

    Given an item's declared paradigm is unrecognized, When `des refactor`
    runs, Then the refusal printed on stdout/stderr names the offending
    declared value VERBATIM and names at least one recognized paradigm --
    an operator must be able to fix their `techdebt.md` entry without
    reading source code (mirrors the pile-grammar-refusal suite's
    WHAT/WHY/HOW convention for the SAME pre-worktree refusal point).
    """
    composition = RefactorSwarmComposition(tmp_path)
    composition.init_git_repo()
    composition.seed_pile_item(item_id="TD-001", paradigm="quantum")

    composition.call_refactor_main_in_process(agent_cmd="true")
    captured = capsys.readouterr()
    combined = captured.out + captured.err

    assert "quantum" in combined, (
        "the refusal must name the offending declared paradigm value "
        f"verbatim; got: {combined!r}"
    )
    recognized_named = any(member.value in combined for member in DeclaredParadigm)
    assert recognized_named, (
        "the refusal must name at least one recognized paradigm so the "
        f"operator knows how to fix their pile entry; got: {combined!r}"
    )


def test_paradigm_refusal_exits_non_zero_never_a_silent_zero(tmp_path, capsys):
    """CONTRACT_SHAPE: bounded-change

    Given an item's declared paradigm is unrecognized, When `des refactor`
    runs, Then it exits NON-ZERO -- asserted standalone (not folded into the
    message-content assertions above) so a fix that gets the message right
    but leaves the exit code wrong is still caught, mirroring the
    pile-grammar-refusal suite's identical standalone exit-code AT.
    """
    composition = RefactorSwarmComposition(tmp_path)
    composition.init_git_repo()
    composition.seed_pile_item(item_id="TD-001", paradigm="quantum")

    exit_code = composition.call_refactor_main_in_process(agent_cmd="true")

    assert exit_code != 0, (
        f"a paradigm refusal is a refusal, not a quiet no-op; got exit_code={exit_code}"
    )


# --- H: repeated-refusal idempotency (self-completeness audit C2b/C4a) -----


def test_a_repeated_drain_attempt_on_an_already_refused_item_is_idempotent(
    tmp_path,
):
    """CONTRACT_SHAPE: pure-function

    Given an item was already refused for an unrecognized paradigm (the item
    stays pending, per test D), When `des refactor` is run AGAIN over the
    same still-pending pile, Then the SECOND attempt refuses identically --
    same outcome shape, no worktree created either time, the item still
    unchanged in `techdebt.md` -- an illegal "drain a refused item" event
    from the refused-and-still-pending state must be stable, never
    escalate into a different (or worse, a silently-successful) outcome on
    a repeat attempt.
    """
    composition = RefactorSwarmComposition(tmp_path)
    composition.init_git_repo()
    composition.seed_pile_item(item_id="TD-001", paradigm="quantum")

    first = composition.run_drain_one_item()
    worktrees_after_first = composition.worktree_list()
    second = composition.run_drain_one_item()

    for attempt_name, result in (("first", first), ("second", second)):
        assert result.drained is False, f"{attempt_name} attempt must never drain"
        assert result.worktree_head_sha_at_creation is None, (
            f"{attempt_name} attempt must never create a worktree"
        )
        assert result.reason is not None and "paradigm" in result.reason.lower(), (
            f"{attempt_name} attempt must refuse with a named paradigm reason; "
            f"got reason={result.reason!r}"
        )
    assert composition.worktree_list() == worktrees_after_first, (
        "a repeated refusal must never create a worktree on the second "
        "attempt either -- git worktree list must stay identical"
    )
    assert composition.pile_contains("quantum"), (
        "the item's original declared paradigm must stay unchanged in "
        "techdebt.md across both refused attempts"
    )
    assert not composition.paid_contains("TD-001")
