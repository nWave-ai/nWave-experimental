"""Acceptance tests: a lane's node is DERIVED from its branch name, never listed.

The bug these pin, found live on 2026-07-30. `live_nodes()` read a hand-kept
`LANE_NODES` dict, and one of its rows said `lane/codex-recover` worked
D37/D38/D34/D35. That branch genuinely carried four unmerged commits, so the
liveness half of the probe fired *correctly* -- and forced four nodes to
`AL LAVORO` whose real topics (BuildReceiptProducer, CandidateReceipt,
digest-suite-authority, GateEvent-parity) that branch has never touched. The
mapping was the lie, not the liveness.

That is a class, not an incident: a second list of what a branch means has to be
hand-synchronised with the branches forever, and nothing made it fail loudly
when it drifted. Measured at repair time, all 17 surviving entries were dead
(no unmerged work), while two lanes that DID have unmerged work were invisible
to it. Every live reading it produced was false; every true one was missing.

These tests pin:
- a branch whose name declares no node overrides NOTHING, however much
  unmerged work it carries -- the exact shape of the codex-recover bug;
- a branch whose name declares a node projects THAT node, with no list
  anywhere admitting the branch first -- the shape of the misses;
- the ids a branch may resolve against are the document's own, so a name
  citing a node that does not exist projects nothing;
- an ambiguous base (`lane/d03` where D03a and D03b both exist) is reported,
  never guessed -- GDP-8's third state reaching the aggregate;
- a sub-slice suffix survives the case fold and comes back spelled as the
  document spells it.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest


sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "scripts"))

from mikado_board import lane_node, live_nodes


#: The ids of the real tree, as the document spells them -- suffixes included.
DOC_IDS = ("D03a", "D03b", "D24", "D34", "D35", "D37", "D38", "D64", "D95", "F12")


def _git(repo: Path, *args: str) -> None:
    subprocess.run(
        ["git", *args],
        cwd=repo,
        check=True,
        capture_output=True,
        text=True,
        stdin=subprocess.DEVNULL,
    )


@pytest.fixture
def repo(tmp_path: Path) -> Path:
    """A repo on the real trunk name, with one commit to branch from."""
    root = tmp_path / "repo"
    root.mkdir()
    _git(root, "init", "-q", "-b", "feature/atdd-pure-staging")
    _git(root, "config", "user.email", "t@t")
    _git(root, "config", "user.name", "t")
    (root / "seed").write_text("seed\n")
    _git(root, "add", "-A")
    _git(root, "commit", "-qm", "seed")
    return root


def _live_lane(repo: Path, branch: str) -> Path:
    """A worktree on `branch` carrying one commit trunk does not have."""
    tree = repo.parent / branch.replace("/", "-")
    _git(repo, "worktree", "add", "-q", "-b", branch, str(tree))
    (tree / branch.replace("/", "-")).write_text("work\n")
    _git(tree, "add", "-A")
    _git(tree, "commit", "-qm", f"work on {branch}")
    return tree


# --- the bug, exactly ------------------------------------------------------


def test_a_live_branch_naming_no_node_forces_no_node(repo: Path) -> None:
    """`lane/codex-recover`: four real commits, zero claim on any tree node.

    The dict said this branch worked D37/D38/D34/D35. Its name says nothing of
    the sort, so a derived reading cannot make that claim -- and the liveness
    of the branch, which was never in doubt, is powerless to conjure one.
    """
    _live_lane(repo, "lane/codex-recover")

    nodes, ambiguous = live_nodes(repo, DOC_IDS)

    assert nodes == set()
    assert ambiguous == []


def test_the_stale_mapping_cannot_be_reintroduced_by_prose(repo: Path) -> None:
    """Naming the nodes in the branch's own COMMIT does not project them either.

    The join reads the branch NAME and nothing else. A commit subject, a lane
    table cell, or a node row that merely mentions the branch is a DESIGNATION;
    only the name is the property. (D92's row cites `lane/codex-recover` as a
    branch to protect from removal -- read as a work claim, that single row
    would rebuild this bug on a different substrate.)
    """
    tree = _live_lane(repo, "lane/codex-recover")
    (tree / "note").write_text("x\n")
    _git(tree, "add", "-A")
    _git(tree, "commit", "-qm", "work on D37 D38 D34 D35")

    nodes, _ = live_nodes(repo, DOC_IDS)

    assert nodes == set()


def test_a_lane_no_list_ever_admitted_is_projected(repo: Path) -> None:
    """`lane/d95-examine-gate` was live and invisible to the dict. Not any more.

    Nothing registers this branch anywhere; its name is the whole evidence.
    """
    _live_lane(repo, "lane/d95-examine-gate")
    _live_lane(repo, "lane/d64-remeasure-and-reconcile")

    nodes, ambiguous = live_nodes(repo, DOC_IDS)

    assert nodes == {"D95", "D64"}
    assert ambiguous == []


def test_a_merged_lane_projects_nothing_however_it_is_named(repo: Path) -> None:
    """The liveness half stays load-bearing: a name alone is not work."""
    _git(repo, "branch", "lane/d24")

    nodes, ambiguous = live_nodes(repo, DOC_IDS)

    assert nodes == set()
    assert ambiguous == []


# --- the three states ------------------------------------------------------


def test_an_ambiguous_base_is_reported_and_never_guessed(repo: Path) -> None:
    """`lane/d03` against D03a and D03b: undecidable, so it decides nothing."""
    _live_lane(repo, "lane/d03")

    nodes, ambiguous = live_nodes(repo, DOC_IDS)

    assert nodes == set()
    assert ambiguous == [("lane/d03", ("D03a", "D03b"))]


@pytest.mark.parametrize(
    ("branch", "expected"),
    [
        ("lane/d24", "D24"),
        ("lane/d24-removal-exec", "D24"),
        ("lane/d03b", "D03b"),
        ("lane/f12-at-discovery", "F12"),
        ("bugfix/d64-something", "D64"),
    ],
)
def test_a_name_declaring_a_real_node_resolves_to_it(
    branch: str, expected: str
) -> None:
    """Including across namespaces: the claim is in the name, not the prefix."""
    assert lane_node(branch, DOC_IDS) == (expected, ())


@pytest.mark.parametrize(
    "branch",
    [
        "lane/codex-recover",
        "lane/context-consumption-probe",
        "lane/smallres",
        "feat/codex-host-parity",
        "bugfix/c1-matcher-binds-observed-tool",
        "spike/qw5-track-a-spine",
        "lane/d99",
    ],
)
def test_a_name_declaring_no_real_node_declares_nothing(branch: str) -> None:
    """No candidate, or a candidate no node carries: silence, not a degradation.

    Most branches are not lane work. `lane/d99` is the sharper half -- a
    node-SHAPED name for a node this document does not carry projects nothing,
    because the ids it resolves against are the document's own.
    """
    assert lane_node(branch, DOC_IDS) == (None, ())


def test_the_sub_slice_suffix_returns_as_the_document_spells_it() -> None:
    """`D03b`, not `D03B`: a case-normalised near-miss would match no row.

    The join folds case to look an id up, because the gate's shared extractor
    uppercases; what comes back has to be the string the state table actually
    keys on, or the override silently addresses a node that is not there.
    """
    node, _ = lane_node("lane/d03b-anything", DOC_IDS)

    assert node == "D03b"
    assert node in DOC_IDS
