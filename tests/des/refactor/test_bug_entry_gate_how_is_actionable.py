# @feature-fix-drain-single-item-silent-noop
# @slice-01
"""Following the entry-gate refusal's own `Fix:` line must actually get the
maintainer unstuck.

RCA (blind-examiner finding against `docs/product/expectations/
fix-drain-single-item-silent-noop/a-drain-that-does-nothing-tells-me-why-and-
what-to-do.md`, then reproduced against a synthetic repo). A drain blocked at
the entry gate today refuses with a HOW that reads:

    Fix: make your own --agent-cmd print exactly one of those tokens on its
    stdout as its last act -- for example `your-agent ... && echo
    REFACTOR_SAFE`. ...

A maintainer does exactly that -- edits their `./fixer.sh` to echo
`REFACTOR_SAFE` -- re-runs, and gets the BYTE-IDENTICAL refusal, with nothing
whatsoever indicating why their edit had no effect. Measured::

    fixer edited to echo REFACTOR_SAFE, NOT committed  -> identical refusal, exit 1
    fixer edited to echo REFACTOR_SAFE, COMMITTED      -> "Drained 1 item: TD-001", exit 0
    fixer at an absolute path OUTSIDE the repo, uncommitted -> drained, exit 0

Mechanism: `RefactorDrainService.drain_one` dispatches the agent through
`ShellAgentInvocationAdapter.invoke(..., cwd=worktree_path)`, and that worktree
is `GitWorktreeAdapter.create_worktree_from_tip(..., "HEAD")` -- an ISOLATED
CHECKOUT OF THE LAST COMMIT. A repo-relative `--agent-cmd` therefore resolves
INSIDE that checkout, so the copy that runs is the committed one and an
uncommitted working-tree edit is invisible to the drain. (An out-of-repo
absolute path is unaffected: it resolves to the same live file from any cwd.)
The refusal never mentions any of this, so following its HOW verbatim loops the
maintainer on an unchanged error -- the charter's positive oracle, violated:
"following that action verbatim (without reading any source) makes a subsequent
run actually do the work or fail for a genuinely different, equally-explained
reason."

WHY BOTH A BEHAVIOURAL AND A CONTENT TEST. The load-bearing test is
BEHAVIOURAL (`test_following_the_refusals_own_fix_verbatim_...`): it runs the
real CLI twice -- once before the maintainer follows the advice, once after --
and requires the two terminals to be TELLABLE APART, which is the charter's
oracle stated literally and is not satisfiable by any rewording that leaves the
two runs identical. Distinguishability alone is not sufficient, though: a
second refusal that merely DIFFERS while still not naming the constraint would
leave the maintainer equally stuck. So a second test pins the CONTENT of that
refusal -- deliberately as an enumerated CONCEPT VOCABULARY (a committed-state
word AND an isolation word AND at least one of the concrete routes forward),
never a loose one-word substring match and never this file's preferred
phrasing. What is asserted is the operator-meaningful information: that only
committed content ran, inside a separate checkout, and what to do about it.
Feasibility note for the fix: the repository already exposes an
uncommitted-changes read on this very port (`GitWorktreePort.
has_uncommitted_changes`), so distinguishing the two runs needs no new
capability.

THE CURE MUST NOT BECOME THE DISEASE. Both placements that work TODAY --
committed-inside-the-repo, and uncommitted-outside-the-repo -- are pinned here
as still draining at exit 0, and pinned free of the new advisory noise (the
charter's "runs that were already fine must NOT acquire new warnings" negative
oracle). Those two placements are also exactly the two escape routes the
refusal is expected to name, so the guard and the explanation stay in step.

Layer 2 in-process (`composition.call_refactor_main_in_process`) -- drives the
REAL `des.cli.refactor.main` entry, no interpreter fork; subprocess-e2e stays
reserved for the ONE `@walking_skeleton` in test_slice_01_walking_skeleton.py.
`capsys` captures the CLI's OWN stdout/stderr -- the exact surface a maintainer
is looking at, never a harness or implementation internal. Every repo, and
every fixer script, is built fresh under `tmp_path`; nothing here ever points
at this project's own tree.

RED-scaffold note: the entry gate, the worktree-from-tip creation and the
refusal rendering are all ALREADY IMPLEMENTED, so every assertion below is
reached and fails on a genuine observable -- two byte-identical refusals, and a
refusal that never names the constraint -- never a collection/import/fixture
error.

covers: EXP-fix-drain-single-item-silent-noop-1
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

import pytest

# Defensive pre-import (module-collection time, OUTSIDE any capsys capture):
# importing `des.cli.refactor` triggers `des.cli`'s package `__init__`, which
# fires the runtime freshness gate's ONE-SHOT `des.runtime.freshness.*` stderr
# event on first import in this process. Forcing that one-shot print to happen
# here, before any test's `capsys` fixture is active, keeps every capture below
# free of freshness noise regardless of collection/execution order.
from des.cli.refactor import main as _preimport_refactor_main  # noqa: F401

from .composition import RefactorSwarmComposition
from .domain_types import EntryGateAgentVerdict


pytestmark = pytest.mark.acceptance


#: The one pending item every arrangement seeds.
_ITEM_ID = "TD-001"

#: The refusal must say that what ran was COMMITTED content. Enumerated forms
#: rather than one bare word, so the failure message can tell the implementer
#: exactly which vocabulary is accepted.
_COMMITTED_STATE_FORMS = ("commit", "committed", "uncommitted")

#: ...and that it ran somewhere OTHER than the maintainer's working tree.
#: Requiring this alongside the committed-state word is what makes the
#: assertion an explanation of the mechanism rather than a stray word match.
_ISOLATION_FORMS = (
    "worktree",
    "work tree",
    "separate checkout",
    "isolated copy",
    "isolated checkout",
    "clean checkout",
)

#: At least one concrete route that would actually make the maintainer's edit
#: visible to the next run: commit it, or point --agent-cmd somewhere git does
#: not shadow. Both routes are accepted -- this file does not dictate which.
_ROUTE_FORWARD_FORMS = (
    "git commit",
    "commit the",
    "commit it",
    "commit that",
    "commit your",
    "committing",
    "outside the repo",
    "outside your repo",
    "outside this repo",
    "outside the repository",
    "absolute path",
)


def _scratch_project_with_one_pending_item(root: Path) -> RefactorSwarmComposition:
    """A pristine, hermetic scratch git repository under `tmp_path` holding one
    correctly-written pending item and one committed, passing toy test for a
    fixer to touch -- the charter's day-one precondition. Delegates every step
    to the composition root; nothing here reaches this project's own tree."""
    root.mkdir(parents=True, exist_ok=True)
    composition = RefactorSwarmComposition(root)
    composition.init_git_repo()
    composition.seed_toy_passing_test()
    composition.seed_pile_item(item_id=_ITEM_ID)
    return composition


def _terminal(capsys) -> str:
    """Everything the maintainer sees from one run -- stdout and stderr are one
    terminal to them, so they are read as one."""
    captured = capsys.readouterr()
    return (captured.out + captured.err).strip()


def _missing(lowered: str, accepted_forms: tuple[str, ...]) -> bool:
    return not any(form in lowered for form in accepted_forms)


# --- The behavioural oracle: the advice, followed verbatim, changes the run --


def test_following_the_refusals_own_fix_verbatim_changes_what_the_maintainer_sees(
    tmp_path, capsys
):
    """Given a drain refused because the maintainer's repo-relative fixer
    emitted no entry-gate verdict, When the maintainer does exactly what that
    refusal's `Fix:` line tells them -- make the fixer print `REFACTOR_SAFE` --
    and runs again, Then the second run is TELLABLE APART from the first: it
    either does the work, or refuses for a genuinely different, equally
    explained reason.

    Byte-identical is the defect. The drain executes the fixer inside an
    isolated worktree checked out from the last commit, so the maintainer's
    uncommitted edit never ran at all -- and today nothing in either terminal
    says so, leaving them to repeat the same action forever.

    One variable across the two runs: whether the maintainer has followed the
    advice. Same repo, same pile, same `--agent-cmd` string, same driving
    surface -- so any difference in what they see is attributable to their edit
    and nothing else.

    Deliberately NOT satisfiable by rewording the refusal: a reworded refusal
    is still emitted identically by both runs. It is also not satisfiable by
    varying the exit code alone -- the comparison is on what the terminal SAYS.

    CONTRACT_SHAPE: bounded-change

    covers: EXP-fix-drain-single-item-silent-noop-1
    """
    composition = _scratch_project_with_one_pending_item(tmp_path / "repo")
    agent_cmd = composition.install_committed_fixer_script(emits_verdict=False)

    before_advice_exit = composition.call_refactor_main_in_process(agent_cmd=agent_cmd)
    before_advice_output = _terminal(capsys)

    composition.operator_edits_fixer_to_emit_verdict_without_committing()

    verdict_token = EntryGateAgentVerdict.REFACTOR_SAFE.value
    assert composition.fixer_script_change_is_uncommitted(), (
        "arrangement integrity: the maintainer's edit must be UNCOMMITTED -- "
        "that is the whole point of the scenario; git reports the fixer script "
        "as clean"
    )
    assert verdict_token not in composition.committed_fixer_script_text(), (
        "arrangement integrity: the COMMITTED copy of the fixer (the one an "
        "isolated worktree cut from HEAD actually runs) must still lack "
        f"{verdict_token!r}; it already carries it, so this scenario is not "
        "reproducing the defect at all"
    )

    after_advice_exit = composition.call_refactor_main_in_process(agent_cmd=agent_cmd)
    after_advice_output = _terminal(capsys)

    assert before_advice_output != "", (
        "the comparison is vacuous unless the first run said something -- got "
        f"empty stdout+stderr (exit_code={before_advice_exit})"
    )
    assert after_advice_output != "", (
        "the run AFTER following the advice must still say something -- got "
        f"empty stdout+stderr (exit_code={after_advice_exit})"
    )
    assert after_advice_output != before_advice_output, (
        "a maintainer who followed the refusal's own `Fix:` instruction "
        "verbatim must be able to SEE that something changed -- their edit "
        "was invisible to the drain (it runs the fixer inside a worktree "
        "checked out from the last commit) and both runs printed byte-"
        "identical output, so the only next move the product offers is to "
        "repeat the action that just failed:\n"
        f"  before following the advice (exit={before_advice_exit}): "
        f"{before_advice_output!r}\n"
        f"  after  following the advice (exit={after_advice_exit}): "
        f"{after_advice_output!r}"
    )


# --- The content oracle: the refusal names the constraint that explains it ---


def test_the_refusal_explains_that_only_committed_fixer_content_ever_ran(
    tmp_path, capsys
):
    """Given a maintainer whose repo-relative fixer emits the entry-gate
    verdict in their working tree but has not been committed, When
    `des refactor` refuses, Then the refusal names WHICH command it ran (WHAT),
    explains that only COMMITTED content ran, in a checkout separate from their
    working tree (WHY), and names at least one concrete route that would make
    their edit take effect -- commit it, or point `--agent-cmd` at a path
    outside the repo (HOW).

    The behavioural test above requires the two runs to differ; this one
    requires the difference to be an EXPLANATION. A second refusal that merely
    varied would leave the maintainer just as unable to act.

    The assertion is on an enumerated CONCEPT VOCABULARY, not on wording: any
    of several accepted forms satisfies each of the three concepts, and the
    failure message lists them. This is deliberately a content assertion -- the
    fact being pinned (that the constraint is EXPLAINED, not merely that
    behaviour differs) has no other observable surface than the text the
    maintainer reads.

    Scoped to the repo-relative fixer, the only shape where the constraint
    bites; whether the product also mentions it elsewhere is left open.

    CONTRACT_SHAPE: bounded-change

    covers: EXP-fix-drain-single-item-silent-noop-1
    """
    composition = _scratch_project_with_one_pending_item(tmp_path / "repo")
    agent_cmd = composition.install_committed_fixer_script(emits_verdict=False)
    composition.operator_edits_fixer_to_emit_verdict_without_committing()

    exit_code = composition.call_refactor_main_in_process(agent_cmd=agent_cmd)
    output = _terminal(capsys)
    lowered = output.lower()

    assert output != "", (
        "a refused run must tell the maintainer something -- got completely "
        f"empty stdout+stderr (exit_code={exit_code})"
    )
    assert agent_cmd in output, (
        "the refusal must name WHICH command it ran, so a maintainer with more "
        "than one script can see which of theirs this is about; expected "
        f"{agent_cmd!r} inside: {output!r}"
    )
    assert not _missing(lowered, _COMMITTED_STATE_FORMS), (
        "the refusal must say that what ran was the COMMITTED content -- "
        "otherwise a maintainer staring at a fixer that plainly prints "
        f"{EntryGateAgentVerdict.REFACTOR_SAFE.value} has no way to know their "
        f"edit never ran; accepted forms {_COMMITTED_STATE_FORMS!r}, got: "
        f"{output!r}"
    )
    assert not _missing(lowered, _ISOLATION_FORMS), (
        "the refusal must say WHERE it ran the command -- a checkout separate "
        "from the maintainer's own working tree -- so the committed-content "
        "fact is explained rather than merely asserted; accepted forms "
        f"{_ISOLATION_FORMS!r}, got: {output!r}"
    )
    assert not _missing(lowered, _ROUTE_FORWARD_FORMS), (
        "the refusal must name at least one concrete route that would make "
        "the maintainer's edit take effect on the next run -- commit it, or "
        "point --agent-cmd at a path outside the repo (both work today); "
        f"accepted forms {_ROUTE_FORWARD_FORMS!r}, got: {output!r}"
    )


# --- The no-regression guard: both placements that work today keep working ---


@dataclass(frozen=True)
class WorkingFixerPlacement:
    """One place a maintainer can put a verdict-emitting fixer such that
    `des refactor` sees it TODAY -- and, not by coincidence, one of the two
    escape routes the refusal above is expected to name."""

    label: str
    install: Callable[[RefactorSwarmComposition], str]


_WORKING_FIXER_PLACEMENTS: tuple[WorkingFixerPlacement, ...] = (
    WorkingFixerPlacement(
        label="committed-inside-the-repo",
        install=lambda composition: composition.install_committed_fixer_script(
            emits_verdict=True
        ),
    ),
    WorkingFixerPlacement(
        label="uncommitted-outside-the-repo",
        install=lambda composition: composition.install_out_of_repo_fixer_script(
            emits_verdict=True
        ),
    ),
)


@pytest.mark.parametrize(
    "placement",
    _WORKING_FIXER_PLACEMENTS,
    ids=[placement.label for placement in _WORKING_FIXER_PLACEMENTS],
)
def test_a_fixer_the_drain_can_actually_see_still_drains_and_is_not_scolded(
    tmp_path, capsys, placement: WorkingFixerPlacement
):
    """Given a fixer that emits the entry-gate verdict AND sits where the drain
    can actually see it -- committed inside the repo, or at an absolute path
    outside it -- When `des refactor` runs, Then the item is drained, reported,
    moved to the paid pile, and the run exits 0 WITHOUT acquiring the
    uncommitted-fixer advisory.

    Pinned alongside the fix so that teaching the blocked path about committed
    content cannot be achieved by degrading, or nagging, the healthy one (the
    charter's explicit negative oracle: runs that were already fine must not
    acquire new warnings, banners or repeated scolding). Both placements are
    verified-true today; this is a guard, not a claim about missing behaviour.

    CONTRACT_SHAPE: bounded-change

    covers: EXP-fix-drain-single-item-silent-noop-1
    """
    composition = _scratch_project_with_one_pending_item(tmp_path / "repo")
    agent_cmd = placement.install(composition)

    exit_code = composition.call_refactor_main_in_process(agent_cmd=agent_cmd)
    output = _terminal(capsys)
    lowered = output.lower()

    assert exit_code == 0, (
        f"a fixer the drain can see ({placement.label}) that emits "
        f"{EntryGateAgentVerdict.REFACTOR_SAFE.value} must still drain "
        f"cleanly; got exit_code={exit_code}, output: {output!r}"
    )
    assert "drained 1 item" in lowered and _ITEM_ID in output, (
        f"a successful drain must still report itself, naming the item; got: {output!r}"
    )
    assert composition.paid_contains(_ITEM_ID), (
        f"the drained item must reach paidtechdebt.md ({placement.label}) -- "
        "reporting a drain that did not move the item is the charter's "
        "forbidden false claim"
    )
    assert not composition.pile_contains(_ITEM_ID), (
        f"the drained item must no longer be pending in techdebt.md ({placement.label})"
    )
    assert "uncommitted" not in lowered, (
        "a run that was already fine must not acquire the uncommitted-fixer "
        f"advisory -- the cure must not tax the healthy path; got: {output!r}"
    )
    assert "outside the repo" not in lowered, (
        "a run that was already fine must not be told where to move its fixer "
        f"-- it is already somewhere that works; got: {output!r}"
    )
