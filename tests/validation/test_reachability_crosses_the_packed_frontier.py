"""``LooseObjectReachability`` must decide across the packed frontier, not stop at it.

WHY THIS TEST EXISTS. ``LooseObjectReachability.reachable_from`` (in
``git_commit_reachability.py``) walks the ref tip outward through
``_read_loose_commit`` -- LOOSE objects only. The moment the walk touches a
commit that lives only in a packfile, it cannot read the object, sets
``frontier_packed = True``, and if the *target* is also packed, hands back
INDETERMINATE with a message that says the walk "stopped at the frontier of
packed commits". That refusal is honest today, but it is no longer necessary:
``git_packed_objects.PackedObjectStore`` already decodes packed commits in
pure Python, is proven byte-for-byte correct against ``git cat-file`` in
``test_packed_object_reader.py``, and is already wired into the sibling reader
``git_commit_contents.LooseObjectContents`` (loose first, then
``self._packed.read(sha)``). It is simply not wired into this walk yet -- so
every ``validate_mikado_tree_coherence.py`` run over a Mikado document that
cites a commit ``git gc`` has since packed degrades to
``[unverifiable] closure-sha-unverifiable``, even for a real ancestor.

``git`` is used here strictly as a SETUP ORACLE (building the fixture repo and
proving it is genuinely packed) -- exactly the discipline
``test_packed_object_reader.py`` follows for the same reason: the test may
depend on the tool, the gate under test never may.

THE MOST IMPORTANT CASE IS THE NEGATIVE ONE. A fix that starts reading packed
commits must still refuse to answer when the pack itself cannot be trusted.
Turning today's honest INDETERMINATE into a wrong REACHABLE (or a silent
NOT_REACHABLE) would be strictly worse than the bug it replaces -- so the
corruption case below mutates the target object's own bytes, at its own
offset inside the pack, the same precision discipline
``test_packed_object_reader.py`` uses (a corruption anywhere else in the pack
proves nothing).
"""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest


SCRIPT_DIR = Path(__file__).resolve().parents[2] / "scripts" / "validation"
sys.path.insert(0, str(SCRIPT_DIR))

from git_commit_reachability import LooseObjectReachability, Reachability
from git_packed_objects import PackedObjectStore


# ---------------------------------------------------------------------------
# fixture: a real git repo, real branches, forced into a single packfile
# ---------------------------------------------------------------------------


def _git(repo: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", "-C", str(repo), *args],
        capture_output=True,
        text=True,
        env={
            **os.environ,
            "GIT_AUTHOR_NAME": "T",
            "GIT_AUTHOR_EMAIL": "t@example.com",
            "GIT_COMMITTER_NAME": "T",
            "GIT_COMMITTER_EMAIL": "t@example.com",
        },
    )


def _commit(repo: Path, message: str) -> str:
    result = _git(
        repo, "-c", "commit.gpgsign=false", "commit", "--allow-empty", "-m", message
    )
    assert result.returncode == 0, result.stderr
    return _git(repo, "rev-parse", "HEAD").stdout.strip()


@pytest.fixture(scope="module")
def packed_repo(tmp_path_factory: pytest.TempPathFactory) -> dict:
    """A 4-commit repo (main: c1-c2-c3, sibling: c1-sibling_tip) fully packed.

    ``git repack -a -d -f`` writes one pack holding every object reachable
    from any ref and deletes the loose copies it makes redundant -- so
    afterwards every commit here is readable through ``git`` but NOT through
    ``_read_loose_commit``. Both facts are verified below before any test
    trusts the fixture.
    """
    repo = tmp_path_factory.mktemp("packed_repo")
    init = _git(repo, "init", "-q", "-b", "main")
    assert init.returncode == 0, init.stderr

    c1 = _commit(repo, "c1")
    c2 = _commit(repo, "c2")
    c3 = _commit(repo, "c3")

    branch = _git(repo, "checkout", "-q", "-b", "sibling", c1)
    assert branch.returncode == 0, branch.stderr
    sibling_tip = _commit(repo, "sibling-only")
    back = _git(repo, "checkout", "-q", "main")
    assert back.returncode == 0, back.stderr

    repack = _git(repo, "repack", "-a", "-d", "-f")
    assert repack.returncode == 0, repack.stderr

    objects = repo / ".git" / "objects"
    for sha in (c1, c2, c3, sibling_tip):
        loose = objects / sha[:2] / sha[2:]
        assert not loose.exists(), (
            f"{sha[:9]} is still loose after repack: fixture would prove nothing"
        )
        cat = _git(repo, "cat-file", "-t", sha)
        assert cat.stdout.strip() == "commit", (
            f"{sha[:9]} unreadable even via git itself: {cat.stderr}"
        )
    assert list((objects / "pack").glob("*.pack")), "repack produced no packfile"

    return {
        "path": repo,
        "c1": c1,
        "c2": c2,
        "c3": c3,
        "sibling_tip": sibling_tip,
    }


@pytest.fixture(scope="module")
def corrupted_pack_repo(
    packed_repo: dict, tmp_path_factory: pytest.TempPathFactory
) -> dict:
    """A COPY of ``packed_repo`` whose pack is corrupted AT c2's own offset.

    Corrupting a copy (never the shared fixture) keeps this destructive case
    isolated from every other test in the module.
    """
    dest = tmp_path_factory.mktemp("corrupted_repo")
    shutil.copytree(packed_repo["path"] / ".git", dest / ".git")

    pack_dir = dest / ".git" / "objects" / "pack"
    target = packed_repo["c2"]
    owning_idx, offsets = None, None
    for idx in sorted(pack_dir.glob("*.idx")):
        table = PackedObjectStore._parse_idx(idx)
        if table and target in table:
            owning_idx, offsets = idx, table
            break
    assert owning_idx is not None, (
        f"{target[:9]} not found in any pack index of the copy"
    )

    pack_path = owning_idx.with_suffix(".pack")
    pack_path.chmod(0o644)  # git ships packs read-only
    at = offsets[target]

    control = PackedObjectStore(dest / ".git" / "objects").read(target)
    assert control is not None, (
        "control read failed before any corruption: fixture is broken"
    )

    body = bytearray(pack_path.read_bytes())
    # Destroy the zlib stream a few bytes past the type+size header, AT the
    # object's own offset -- a mutation anywhere else could land past the end
    # of this (small, empty-tree) commit and prove nothing.
    body[at + 3 : at + 40] = b"\xff" * 37
    pack_path.write_bytes(bytes(body))

    broken = PackedObjectStore(dest / ".git" / "objects").read(target)
    assert broken is None, (
        "corruption did not actually break the packed read: test is vacuous"
    )

    return {"path": dest, "target": target}


# ---------------------------------------------------------------------------
# positive: a packed ancestor is REACHABLE
# ---------------------------------------------------------------------------


def test_a_packed_ancestor_commit_is_reachable_from_the_branch_tip(
    packed_repo: dict,
) -> None:
    """c2 is a real ancestor of main's tip and lives only in the pack.

    Currently RED: the loose-only walk cannot read main's tip (also packed),
    sets ``frontier_packed``, and returns INDETERMINATE instead of REACHABLE.
    """
    reachability = LooseObjectReachability(packed_repo["path"])

    answer = reachability.reachable_from(packed_repo["c2"], "main")

    assert answer.outcome is Reachability.REACHABLE, answer.detail


# ---------------------------------------------------------------------------
# positive: a packed commit that is NOT an ancestor is NOT_REACHABLE
# ---------------------------------------------------------------------------


def test_a_packed_commit_outside_the_branch_is_not_reachable(packed_repo: dict) -> None:
    """sibling_tip exists (packed) but never merged into main.

    Also currently RED for the same frontier reason: today's walk cannot
    distinguish "not an ancestor" from "could not finish the walk" once the
    target is packed, so both collapse to INDETERMINATE.
    """
    reachability = LooseObjectReachability(packed_repo["path"])

    answer = reachability.reachable_from(packed_repo["sibling_tip"], "main")

    assert answer.outcome is Reachability.NOT_REACHABLE, answer.detail


# ---------------------------------------------------------------------------
# negative: an object that exists nowhere -- pin the existing correct answer
# ---------------------------------------------------------------------------


def test_a_sha_that_exists_nowhere_is_not_reachable_by_construction(
    packed_repo: dict,
) -> None:
    """No loose file, no pack entry: this must stay NOT_REACHABLE, unaffected by the fix.

    ``resolve_object`` short-circuits before the walk even starts, so this
    path is untouched by whether packed commits are read -- pinned so the fix
    cannot regress it.
    """
    reachability = LooseObjectReachability(packed_repo["path"])
    absent_sha = "f" * 40

    answer = reachability.reachable_from(absent_sha, "main")

    assert answer.outcome is Reachability.NOT_REACHABLE
    assert "no object" in answer.detail


# ---------------------------------------------------------------------------
# negative: unreadable even via the packed path -- the honesty contract
# ---------------------------------------------------------------------------


def test_a_commit_unreadable_even_from_the_pack_stays_indeterminate(
    corrupted_pack_repo: dict,
) -> None:
    """The single most important case: never let a corrupt read masquerade as an answer.

    c2's pack entry is corrupted at its own offset in a dedicated copy of the
    repo (no loose copy exists anywhere in that copy, by construction of
    ``packed_repo``). Whatever mechanism the fix uses to decode packed
    commits, it must refuse this object -- and the walk must report
    INDETERMINATE, never REACHABLE and never a silent NOT_REACHABLE.
    """
    reachability = LooseObjectReachability(corrupted_pack_repo["path"])

    answer = reachability.reachable_from(corrupted_pack_repo["target"], "main")

    assert answer.outcome is Reachability.INDETERMINATE, answer.detail
