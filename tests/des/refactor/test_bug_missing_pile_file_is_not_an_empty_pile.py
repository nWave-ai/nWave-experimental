# @feature-fix-drain-single-item-silent-noop
# @slice-01
"""A pile path des refactor CANNOT READ is not the same thing as an empty pile.

RCA (reproduced against a synthetic repo, blind-examiner finding against
`docs/product/expectations/fix-drain-single-item-silent-noop/
a-drain-that-does-nothing-tells-me-why-and-what-to-do.md`)::

    des refactor --pile /does/not/exist.md  --agent-cmd ./fixer.sh
      -> "0 parsed -- the pile is empty, nothing to drain"   exit=0
    des refactor --pile <a genuinely empty pile> --agent-cmd ./fixer.sh
      -> "0 parsed -- the pile is empty, nothing to drain"   exit=0

Byte-identical output, both a success exit. A maintainer who typos their pile
path is TOLD their pile is empty and handed a success status. The charter's
positive oracle requires the opposite: "I looked and there was nothing to do"
and "I could not start, so I never looked" must produce visibly DIFFERENT
output, and its negative oracle forbids a success exit for a run that did
nothing unexplained.

Mechanism: `des.domain.refactor.pile.parse_pile_report` opens with
`if not pile_path.is_file(): return PileParseReport(items=(), skipped_lines=())`
-- an unreadable path is folded into the exact value a real, empty, parsed pile
produces, so by the time `des.cli.refactor._report` chooses what to say, the
distinction no longer exists to be reported. `is_file()` is False for THREE
distinct operator mistakes (a mistyped filename, a mistyped directory, and a
`--pile` aimed at a directory), so the shapes below are parametrized rather
than witnessed by one hand-picked example.

WHY THE COMPARISON IS THE TEST. Asserting each case in isolation is not enough:
a build that printed one generic line for BOTH cases and merely varied the exit
code would satisfy "prints something / exits non-zero" while leaving the
maintainer exactly as unable to tell the two apart. So the load-bearing test
runs both cases through the SAME driving surface, in the SAME repo, differing
only in the `--pile` value, and compares the two terminal outputs against each
other -- the charter's actual requirement.

The cure must not become the disease: the charter also carries an explicit
negative oracle against overcorrecting into failing runs that legitimately have
nothing to do, so a genuinely empty pile is pinned here as STILL a clean,
explained, exit-0 outcome.

Layer 2 in-process (`composition.call_refactor_main_in_process_with_pile`) --
drives the REAL `des.cli.refactor.main` entry, no interpreter fork;
subprocess-e2e stays reserved for the ONE `@walking_skeleton` in
test_slice_01_walking_skeleton.py. `capsys` captures the CLI's OWN
stdout/stderr -- the exact surface a maintainer is looking at, never a harness
or implementation internal. Every repo is built fresh under `tmp_path`;
nothing here ever points at this project's own tree.

RED-scaffold note: the unreadable-pile paths below are reached by the ALREADY
IMPLEMENTED `_report` empty-pile branch, so every assertion is executed and
fails on a genuine observable -- an "the pile is empty" claim and `exit_code
== 0` where a named refusal was owed -- never a collection/import/fixture
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


pytestmark = pytest.mark.acceptance


#: An `--agent-cmd` that resolves on PATH, so nothing downstream of the pile
#: read can be blamed for the outcome under test.
_RESOLVABLE_AGENT_CMD = "true"


@dataclass(frozen=True)
class UnreadablePileShape:
    """One real operator mistake that leaves `--pile` pointing at something
    `des refactor` cannot read as a pile file.

    All three collapse to the same `Path.is_file() is False` today, which is
    exactly why they are enumerated: a fix that only special-cases "the file
    does not exist" would still silently treat a `--pile` aimed at a directory
    as an empty pile.
    """

    label: str
    build: Callable[[Path], Path]


def _make_directory(path: Path) -> Path:
    """Create `path` as a real directory and return it -- the `--pile <dir>`
    arrangement (a maintainer who tab-completed one component too few)."""
    path.mkdir(parents=True, exist_ok=True)
    return path


#: Every shape an unreadable `--pile` takes for a maintainer.
_UNREADABLE_PILE_SHAPES: tuple[UnreadablePileShape, ...] = (
    UnreadablePileShape(
        label="mistyped-filename",
        build=lambda repo: repo / "techdbet.md",
    ),
    UnreadablePileShape(
        label="mistyped-directory",
        build=lambda repo: repo / "no-such-directory" / "techdebt.md",
    ),
    UnreadablePileShape(
        label="pile-points-at-a-directory",
        build=lambda repo: _make_directory(repo / "techdebt.d"),
    ),
)


def _scratch_project(root: Path) -> RefactorSwarmComposition:
    """A pristine, hermetic scratch git repository under `tmp_path` -- the
    charter's day-one precondition. Delegates every step to the composition
    root; nothing here reaches this project's own tree."""
    root.mkdir(parents=True, exist_ok=True)
    composition = RefactorSwarmComposition(root)
    composition.init_git_repo()
    return composition


# --- The negative oracle: an unreadable pile is never called an empty one ---


@pytest.mark.parametrize(
    "shape",
    _UNREADABLE_PILE_SHAPES,
    ids=[shape.label for shape in _UNREADABLE_PILE_SHAPES],
)
def test_a_pile_path_that_cannot_be_read_is_never_reported_as_an_empty_pile(
    tmp_path, capsys, shape: UnreadablePileShape
):
    """Given `--pile` points at something des refactor cannot read as a pile
    file, When `des refactor` runs, Then it says it could not READ the pile and
    exits NON-ZERO -- never the "the pile is empty, nothing to drain" success
    that tells a maintainer their typo was an accurate report about their pile.

    CONTRACT_SHAPE: bounded-change

    covers: EXP-fix-drain-single-item-silent-noop-1
    """
    composition = _scratch_project(tmp_path / "repo")
    pile_path = shape.build(composition.project_root)

    exit_code = composition.call_refactor_main_in_process_with_pile(
        pile_path=pile_path, agent_cmd=_RESOLVABLE_AGENT_CMD
    )
    captured = capsys.readouterr()
    combined = captured.out + captured.err
    lowered = combined.lower()

    assert combined.strip() != "", (
        f"an unreadable --pile ({shape.label}) must tell the maintainer "
        "something -- got completely empty stdout AND stderr "
        f"(exit_code={exit_code})"
    )
    assert "the pile is empty" not in lowered, (
        "des refactor must never CLAIM the maintainer's pile is empty when it "
        f"could not read it at all ({shape.label}) -- that is a report about a "
        f"pile it never looked at; got: {combined!r}"
    )
    assert "nothing to drain" not in lowered, (
        "'nothing to drain' is a finding about a pile that WAS read -- an "
        f"unreadable --pile ({shape.label}) never got that far; got: "
        f"{combined!r}"
    )
    assert exit_code != 0, (
        "a run that could not even read its pile did no work and must not "
        "claim success -- `nWave/gates/refactor.yaml` has declared "
        f"DrainRefused -> exit_code 1 since slice-01; got exit_code={exit_code} "
        f"for {shape.label}"
    )


# --- The positive oracle: the two outcomes are told apart from the terminal -


@pytest.mark.parametrize(
    "shape",
    _UNREADABLE_PILE_SHAPES,
    ids=[shape.label for shape in _UNREADABLE_PILE_SHAPES],
)
def test_an_unreadable_pile_and_a_genuinely_empty_pile_are_visibly_different(
    tmp_path, capsys, shape: UnreadablePileShape
):
    """Given the SAME scratch repository and the SAME agent command, When
    `des refactor` is run once against an unreadable pile path and once against
    a pile file that genuinely holds zero pending items, Then a maintainer can
    tell the two runs apart from the terminal alone -- the charter's "I looked
    and there was nothing to do" vs "I could not start, so I never looked".

    One variable: the `--pile` value. Everything else -- repo, driving surface,
    agent command -- is held identical, so any difference in what the
    maintainer sees is attributable to the pile and nothing else.

    Deliberately NOT satisfiable by varying the exit code alone: the assertions
    compare the OUTPUT TEXT of the two runs. A build that printed one generic
    line for both cases and merely exited differently would leave a maintainer
    reading their terminal unable to say which happened -- exactly the defect.

    CONTRACT_SHAPE: bounded-change

    covers: EXP-fix-drain-single-item-silent-noop-1
    """
    composition = _scratch_project(tmp_path / "repo")
    unreadable_pile = shape.build(composition.project_root)
    composition.seed_empty_pile()

    unreadable_exit = composition.call_refactor_main_in_process_with_pile(
        pile_path=unreadable_pile, agent_cmd=_RESOLVABLE_AGENT_CMD
    )
    unreadable_captured = capsys.readouterr()
    unreadable_output = (unreadable_captured.out + unreadable_captured.err).strip()

    empty_exit = composition.call_refactor_main_in_process_with_pile(
        pile_path=composition.pile_path, agent_cmd=_RESOLVABLE_AGENT_CMD
    )
    empty_captured = capsys.readouterr()
    empty_output = (empty_captured.out + empty_captured.err).strip()

    assert empty_output != "", (
        "the comparison is vacuous unless the genuinely-empty-pile run says "
        "something -- got empty stdout+stderr for the empty pile "
        f"(exit_code={empty_exit})"
    )
    assert unreadable_output != "", (
        f"the unreadable pile ({shape.label}) must say something -- got empty "
        f"stdout+stderr (exit_code={unreadable_exit})"
    )
    assert unreadable_output != empty_output, (
        "a maintainer must be able to tell 'I looked and there was nothing to "
        "do' apart from 'I could not start, so I never looked' FROM THE "
        "TERMINAL -- both runs printed byte-identical output:\n"
        f"  unreadable --pile ({shape.label}, exit={unreadable_exit}): "
        f"{unreadable_output!r}\n"
        f"  genuinely empty pile (exit={empty_exit}): {empty_output!r}"
    )
    assert empty_output not in unreadable_output, (
        "the unreadable-pile report must not carry the empty-pile finding "
        "inside it -- appending an explanation to a claim that is still false "
        "leaves the false claim on the maintainer's terminal; empty-pile "
        f"message {empty_output!r} found inside {unreadable_output!r}"
    )
    assert str(unreadable_pile) in unreadable_output, (
        "the unreadable-pile report must name the path it could not read, so "
        "the maintainer can SEE their typo without asking anyone; expected "
        f"{str(unreadable_pile)!r} inside: {unreadable_output!r}"
    )


# --- The no-overcorrection oracle: the cure must not become the disease -----


def test_a_genuinely_empty_pile_is_not_turned_into_a_failing_run(tmp_path, capsys):
    """Given a pile file that exists and genuinely holds zero pending items,
    When `des refactor` runs, Then it stays a clean, explained, exit-0 outcome
    -- the charter's explicit negative oracle against overcorrecting into
    failing runs that legitimately have nothing to do.

    Pinned HERE, alongside the fix, so distinguishing the two cases cannot be
    achieved by degrading the healthy one.

    CONTRACT_SHAPE: pure-function

    covers: EXP-fix-drain-single-item-silent-noop-1
    """
    composition = _scratch_project(tmp_path / "repo")
    composition.seed_empty_pile()

    exit_code = composition.call_refactor_main_in_process_with_pile(
        pile_path=composition.pile_path, agent_cmd=_RESOLVABLE_AGENT_CMD
    )
    captured = capsys.readouterr()
    combined = captured.out + captured.err
    lowered = combined.lower()

    assert exit_code == 0, (
        "a pile that was READ and genuinely holds nothing pending is a clean "
        "outcome, not a refusal -- the cure for the unreadable-pile lie must "
        f"not tax the healthy path; got exit_code={exit_code}, output: "
        f"{combined!r}"
    )
    assert combined.strip() != "", (
        "a genuinely empty pile must still report its outcome -- got "
        "completely empty stdout+stderr"
    )
    assert any(marker in lowered for marker in ("empty", "nothing to drain")), (
        "the empty-pile outcome must still say, in plain language, that there "
        f"was nothing pending to drain; got: {combined!r}"
    )
    assert "refused" not in lowered, (
        "a genuinely empty pile must never be reported as a refusal -- that "
        f"is the overcorrection the charter forbids; got: {combined!r}"
    )


# --- Actionability: WHAT it could not read, and HOW to fix it ---------------


@pytest.mark.parametrize(
    "shape",
    _UNREADABLE_PILE_SHAPES,
    ids=[shape.label for shape in _UNREADABLE_PILE_SHAPES],
)
def test_the_unreadable_pile_refusal_names_the_path_and_a_concrete_next_step(
    tmp_path, capsys, shape: UnreadablePileShape
):
    """Given `--pile` points at something des refactor cannot read, When it
    refuses, Then the refusal names WHAT it could not read (the pile path
    verbatim) and routes the maintainer to a concrete next step naming the
    `--pile` argument at fault -- the standing "every failure explains what,
    why, how" mandate, modelled on the sibling `--agent-cmd` startup-probe
    refusal that already gets this right for the OTHER argument.

    Deliberately NOT satisfiable by a bare "could not read the pile": a
    maintainer with a typo needs to see WHICH path was tried and what to do
    about it.

    CONTRACT_SHAPE: bounded-change

    covers: EXP-fix-drain-single-item-silent-noop-1
    """
    composition = _scratch_project(tmp_path / "repo")
    pile_path = shape.build(composition.project_root)

    composition.call_refactor_main_in_process_with_pile(
        pile_path=pile_path, agent_cmd=_RESOLVABLE_AGENT_CMD
    )
    captured = capsys.readouterr()
    combined = captured.out + captured.err
    lowered = combined.lower()

    assert "Traceback (most recent call last)" not in combined, (
        "an unreadable --pile must refuse in plain language, never surface a "
        f"raw Python traceback; got: {combined!r}"
    )
    assert str(pile_path) in combined, (
        f"the refusal must name WHAT it could not read ({shape.label}); "
        f"expected the path {str(pile_path)!r} inside: {combined!r}"
    )
    assert "--pile" in combined, (
        "the refusal must name the argument at fault, so the maintainer knows "
        f"which one to correct; got: {combined!r}"
    )
    assert any(marker in lowered for marker in ("fix:", "point ", "create ")), (
        "the refusal must route the maintainer to a concrete next step they "
        "can take themselves (as the sibling --agent-cmd probe refusal does: "
        "'Fix: point --agent-cmd at a real, resolvable executable.'); got: "
        f"{combined!r}"
    )
