"""Regression: `des commit-slice` must NEVER orphan/rewrite a commit that is
already present on the upstream remote-tracking ref.

Incident (observed 2026-07-11 ~16:00, exact): HEAD (`9a80cc27d`, the
rust-hardening slice) was ALREADY PUSHED to `origin`. An attestation-run step
staged a charter file and re-ran `des commit-slice` -- but the local branch's
HEAD pointer had, at that moment, REGRESSED behind the pushed tip (a
`git reset --soft` fold-in-a-forgotten-file pattern: the external step
un-committed the pushed slice to add the missed charter, keeping its diff
staged). `commit-slice`'s own stage->commit->amend flow then happily
committed on top of the REGRESSED HEAD, producing a new commit (`2db68552d`)
sharing the SAME PARENT as the pushed commit -- a sibling, not a descendant.
The pushed commit became unreachable from the local branch tip -> local
history diverged from origin -> non-fast-forward push rejection, resolved
only via `--force-with-lease`.

EMPIRICAL FINDING (ground-first, before authoring): the naive two-invocation
scenario ("push a slice commit, then run commit-slice again staging a new
file with NO intervening HEAD regression") does NOT reproduce the defect --
`_commit_with_placeholder` (``src/des/cli/commit_slice.py:657``) always
performs a plain `git commit` (never `--amend`), so it creates a genuine
CHILD of the current HEAD; `_amend_trailer` (``src/des/cli/commit_slice.py
:679``) then amends ONLY that freshly-created child, never a commit that
pre-dates the invocation. Verified empirically (real bare-origin fixture,
two straight `commit-slice` calls): the pushed SHA stays an ancestor and the
push stays fast-forward. The genuine reproduction requires the local branch
to be BEHIND the remote-tracking ref BEFORE `commit-slice` runs (as the
incident's "attestation run" produced via its own git surface) -- that is
the precondition every AT below stages.

The amend locus (unconditional, no remote-awareness):
  * ``_commit_with_placeholder`` -- ``src/des/cli/commit_slice.py:657-676``
    (plain ``git commit`` from whatever HEAD happens to be, no check).
  * ``_amend_trailer`` -- ``src/des/cli/commit_slice.py:679-708`` (``git
    commit --amend --no-edit`` on the resulting HEAD, no remote check).
  * ``main()`` never queries a remote-tracking ref anywhere in its flow.

The fix direction (this AT's contract, NOT implemented here -- test-authoring
only, zero ``src/`` edits): before staging/committing, ``commit-slice`` must
resolve the current branch's upstream tracking ref (or fall back to scanning
``refs/remotes/*``, degrade-honest when no remote is configured) and REFUSE
LOUD (what/why/how, a new ``HeadBehindRemoteRefused`` event) when that
remote ref is NOT an ancestor of local HEAD -- i.e. local has regressed
relative to what is already pushed. A no-remote / local-only repo (the
overwhelmingly common case, and every pre-existing commit-slice test) must
stay byte-identically unaffected.

Driving surface (Mandate-13 driving-port-only, Layer 3 in-process default +
real git subprocess I/O, Mandate-6 real-IO): the REAL
``des.cli.commit_slice.main()`` CLI driver, captured via ``capsys``, against
a REAL bare "origin" git repository + a REAL clone-shaped work-tree with a
REAL ``git push`` -- the only way to observe the actual non-fast-forward
outcome the incident produced.

Fixture reuse (per dispatch instruction -- do NOT hand-roll a new harness):
``_init_repo`` mirrors ``tests/des/integration/test_commit_slice.py``'s
``_init_repo`` verbatim (pytest.ini + conftest.py + ``tests/unit/
test_base.py`` + pinned ``core.hooksPath``) -- the exact shape that already
makes ``des commit-slice``'s whole-tree committed-scope digest + the
build-tier/examine-gate checks pass cleanly today. Extended (additively)
with a bare "origin" repository + ``git remote add`` + ``git push`` -- no
prior sibling test in this repo exercises a remote, so this is a new,
narrowly-scoped extension of the proven idiom, not a parallel harness.
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

from des.cli.commit_slice import main as commit_slice_main


def _git(root: Path, *args: str) -> str:
    return subprocess.run(
        ["git", *args],
        cwd=root,
        check=True,
        capture_output=True,
        text=True,
    ).stdout


def _init_repo(root: Path) -> None:
    """Init a real pytest-collectible git work-tree (mirrors
    ``tests/des/integration/test_commit_slice.py``'s ``_init_repo`` verbatim).
    """
    root.mkdir(parents=True, exist_ok=True)
    _git(root, "init", "-q")
    _git(root, "config", "user.email", "t@t")
    _git(root, "config", "user.name", "t")
    # Pin the hooks dir to the repo's own .git/hooks so a global/user-level
    # core.hooksPath in the environment cannot leak into hook-count behavior.
    _git(root, "config", "--local", "core.hooksPath", ".git/hooks")
    tests_dir = root / "tests" / "unit"
    tests_dir.mkdir(parents=True)
    (root / "tests" / "__init__.py").write_text("", encoding="utf-8")
    (tests_dir / "__init__.py").write_text("", encoding="utf-8")
    (root / "conftest.py").write_text(
        "import pytest\n\n\n"
        "def pytest_collection_modifyitems(items):\n"
        "    for item in items:\n"
        "        item.add_marker(pytest.mark.unit)\n",
        encoding="utf-8",
    )
    (root / "pytest.ini").write_text(
        "[pytest]\nmarkers =\n"
        "    unit: unit tests\n"
        "    integration: integration tests\n"
        "    acceptance: acceptance tests\n",
        encoding="utf-8",
    )
    (tests_dir / "test_base.py").write_text(
        "def test_base():\n    assert True\n", encoding="utf-8"
    )
    _git(root, "add", "-A")
    _git(root, "commit", "-q", "-m", "base: walking skeleton")


def _init_repo_with_pushed_origin(tmp_path: Path) -> tuple[Path, Path]:
    """A repo + a real bare "origin", with the base commit already pushed.

    Returns ``(repo, origin)``. The bare repo is a real git object store on
    disk (not a mock) -- ``git push`` against it exercises the SAME
    non-fast-forward rejection path a real GitHub/GitLab remote would.
    """
    origin = tmp_path / "origin.git"
    repo = tmp_path / "repo"
    subprocess.run(
        ["git", "init", "--bare", "-q", str(origin)], check=True, capture_output=True
    )
    _init_repo(repo)
    _git(repo, "remote", "add", "origin", str(origin))
    _git(repo, "push", "-q", "-u", "origin", "HEAD:refs/heads/main")
    return repo, origin


def _last_json_event(stdout: str) -> dict:
    json_lines = [line for line in stdout.splitlines() if line.strip().startswith("{")]
    assert json_lines, f"expected a JSON payload line on stdout, got: {stdout!r}"
    return json.loads(json_lines[-1])


# ---------------------------------------------------------------------------
# POSITIVE AT -- active-RED today
# ---------------------------------------------------------------------------


def test_commit_slice_preserves_pushed_commit_when_head_regresses(
    tmp_path: Path, capsys
) -> None:
    """Reproduces the EXACT incident shape: a slice commit is pushed, then the
    local branch is regressed behind that pushed tip (the attestation-run's
    own git surface, mirroring a fold-in-a-forgotten-file `git reset --soft`),
    and `commit-slice` runs again to fold in the missed content.

    Expected (the contract): the previously-pushed commit's SHA MUST remain
    reachable from the resulting HEAD (an ancestor) -- `commit-slice` must
    either build the new commit ON TOP of the pushed tip (never on top of the
    regressed base) or refuse LOUD rather than silently producing a diverging
    sibling.

    RED today for the right reason: `_commit_with_placeholder` commits
    blindly from whatever HEAD is at invocation time (no remote-awareness),
    so the pushed commit becomes an unreachable sibling -- a semantic
    `AssertionError` on the ancestry check, not a crash or collection error.
    """
    repo, _origin = _init_repo_with_pushed_origin(tmp_path)

    # Land + push the slice-like commit (the "rust-hardening slice" analogue).
    (repo / "tests" / "unit" / "test_slice_01.py").write_text(
        "def test_slice_01():\n    assert 1 + 1 == 2\n", encoding="utf-8"
    )
    exit_1 = commit_slice_main(
        [
            "--repo",
            str(repo),
            "--feature-id",
            "fix-commit-slice-never-amends-pushed",
            "--all",
            "--message",
            "feat(slice): slice-01 behaviour\n\nSlice-Id: slice-01",
            # This hermetic repo carries no `.feature` files (this AT's real
            # subject is the remote-ancestry guard, orthogonal to any Gherkin
            # scenario), so the default gherkin E2 leg would refuse `no
            # .feature file resolves ... vacuously` (ADR-DES-001 pre-flight).
            # Point E2 at the REAL committed pytest file staged above so the
            # pre-flight gets genuine observed evidence instead of a vacuous
            # pass.
            "--at-kind",
            "pytest-regression",
            "--regression-test-file",
            "tests/unit/test_slice_01.py",
        ]
    )
    capsys.readouterr()  # drain
    assert exit_1 == 0, "the first (setup) slice commit must land cleanly"
    pushed_sha = _git(repo, "rev-parse", "HEAD").strip()
    _git(repo, "push", "-q", "origin", "HEAD:refs/heads/main")

    # THE INCIDENT PRECONDITION: the attestation run's own git surface
    # regresses HEAD behind the pushed tip to fold in a forgotten file,
    # leaving the ORIGINAL diff still staged (this is NOT commit-slice's own
    # action -- it is the external step the real incident's "attestation
    # run" performed; commit-slice must be robust to inheriting this state).
    _git(repo, "reset", "--soft", "HEAD^")
    charter_dir = repo / "docs" / "product" / "expectations" / "some-feature"
    charter_dir.mkdir(parents=True)
    (charter_dir / "intent.md").write_text("# forgotten charter\n", encoding="utf-8")

    exit_2 = commit_slice_main(
        [
            "--repo",
            str(repo),
            "--feature-id",
            "fix-commit-slice-never-amends-pushed",
            "--all",
            "--message",
            "feat(slice): slice-01 behaviour (with charter)\n\nSlice-Id: slice-01",
            # Same evidence source as the setup call above -- the file is
            # still on disk (a `git reset --soft` never touches the working
            # tree), so this remains a real, currently-passing pytest file.
            "--at-kind",
            "pytest-regression",
            "--regression-test-file",
            "tests/unit/test_slice_01.py",
        ]
    )
    event = _last_json_event(capsys.readouterr().out)
    assert exit_2 == 0, f"the fold-in commit must still land -- event={event!r}"

    new_head = _git(repo, "rev-parse", "HEAD").strip()
    assert new_head != pushed_sha, "a new commit must have been produced"

    ancestry_check = subprocess.run(
        ["git", "merge-base", "--is-ancestor", pushed_sha, "HEAD"],
        cwd=repo,
        capture_output=True,
        text=True,
    )
    assert ancestry_check.returncode == 0, (
        f"the pushed commit {pushed_sha} must remain an ancestor of the "
        f"resulting HEAD ({new_head}) -- `git log` on the branch must still "
        "contain it. Instead `commit-slice` committed on top of a REGRESSED "
        "HEAD (mirroring `git reset --soft HEAD^`), producing a sibling that "
        "orphans the pushed commit -- exactly the 2026-07-11 incident "
        "(9a80cc27d -> 2db68552d, resolved only via --force-with-lease)."
    )


# ---------------------------------------------------------------------------
# GUARD AT -- stays green (the pre-existing no-remote flow is untouched)
# ---------------------------------------------------------------------------


def test_commit_slice_single_commit_flow_unaffected_without_remote(
    tmp_path: Path, capsys
) -> None:
    """No remote configured (the overwhelmingly common local-dev case) -> the
    pre-existing single-commit placeholder+amend flow is completely
    unaffected: exactly ONE new commit lands, carrying the Gate-Scope
    trailer and the staged content. This is the byte-identical-behavior
    guard the fix must never break.
    """
    repo = tmp_path / "repo"
    _init_repo(repo)  # no `git remote add` at all

    (repo / "tests" / "unit" / "test_slice_new.py").write_text(
        "def test_slice_new():\n    assert 2 + 2 == 4\n", encoding="utf-8"
    )

    exit_code = commit_slice_main(
        [
            "--repo",
            str(repo),
            "--feature-id",
            "fix-commit-slice-never-amends-pushed",
            "--all",
            "--message",
            "feat(slice): add the new slice behaviour\n\nSlice-Id: slice-01",
            # This hermetic repo carries no `.feature` files (this AT's real
            # subject is the byte-identical no-remote flow, orthogonal to any
            # Gherkin scenario), so the default gherkin E2 leg would refuse
            # `no .feature file resolves ... vacuously` (ADR-DES-001
            # pre-flight). Point E2 at the REAL committed pytest file staged
            # above so the pre-flight gets genuine observed evidence instead
            # of a vacuous pass.
            "--at-kind",
            "pytest-regression",
            "--regression-test-file",
            "tests/unit/test_slice_new.py",
        ]
    )
    event = _last_json_event(capsys.readouterr().out)

    assert exit_code == 0
    assert event["event"] == "SliceCommitted"
    assert event["verified"] is True

    log = _git(repo, "log", "--oneline").strip().splitlines()
    assert len(log) == 2, f"expected exactly base+new commits, got: {log!r}"

    message = _git(repo, "log", "-1", "--format=%B", "HEAD")
    assert f"Gate-Scope: {event['gate_scope_digest']}" in message
    assert "Slice-Id: slice-01" in message

    tracked = _git(repo, "ls-tree", "-r", "--name-only", "HEAD")
    assert "tests/unit/test_slice_new.py" in tracked


# ---------------------------------------------------------------------------
# NEGATIVE-named AT -- the `_never_` invariant, active-RED today
# ---------------------------------------------------------------------------


def test_commit_slice_never_rewrites_a_sha_present_on_origin(
    tmp_path: Path, capsys
) -> None:
    """The strongest, most observable proof of the invariant: after
    `commit-slice` runs against a locally-regressed-behind-origin HEAD, a
    plain `git push` (NO `--force`, NO `--force-with-lease`) to the SAME
    branch on origin must succeed -- i.e. the local branch stayed a
    fast-forward descendant of whatever SHA is present on origin. A SHA
    present on origin is NEVER rewritten by `commit-slice`, observed the
    way an operator observes it: the push either fast-forwards or it
    doesn't.

    RED today for the right reason: origin already holds the pushed slice
    commit; `commit-slice`'s fold-in (on the regressed HEAD) produces a
    diverging sibling, so the plain push is REJECTED (non-fast-forward) --
    a semantic `AssertionError` on the push's exit code/stderr, not a crash.
    """
    repo, _origin = _init_repo_with_pushed_origin(tmp_path)

    (repo / "tests" / "unit" / "test_slice_01.py").write_text(
        "def test_slice_01():\n    assert 3 + 3 == 6\n", encoding="utf-8"
    )
    exit_1 = commit_slice_main(
        [
            "--repo",
            str(repo),
            "--feature-id",
            "fix-commit-slice-never-amends-pushed",
            "--all",
            "--message",
            "feat(slice): slice-01 behaviour\n\nSlice-Id: slice-01",
            # This hermetic repo carries no `.feature` files (this AT's real
            # subject is the remote-ancestry guard, orthogonal to any Gherkin
            # scenario), so the default gherkin E2 leg would refuse `no
            # .feature file resolves ... vacuously` (ADR-DES-001 pre-flight).
            # Point E2 at the REAL committed pytest file staged above so the
            # pre-flight gets genuine observed evidence instead of a vacuous
            # pass.
            "--at-kind",
            "pytest-regression",
            "--regression-test-file",
            "tests/unit/test_slice_01.py",
        ]
    )
    capsys.readouterr()
    assert exit_1 == 0
    _git(repo, "push", "-q", "origin", "HEAD:refs/heads/main")
    on_origin_sha = _git(repo, "rev-parse", "origin/main").strip()

    # Same incident precondition as the POSITIVE AT: regress HEAD, fold in
    # forgotten content via a fresh `commit-slice` run.
    _git(repo, "reset", "--soft", "HEAD^")
    (repo / "docs" / "product" / "expectations" / "some-feature").mkdir(parents=True)
    (
        repo / "docs" / "product" / "expectations" / "some-feature" / "intent.md"
    ).write_text("# forgotten charter\n", encoding="utf-8")

    exit_2 = commit_slice_main(
        [
            "--repo",
            str(repo),
            "--feature-id",
            "fix-commit-slice-never-amends-pushed",
            "--all",
            "--message",
            "feat(slice): slice-01 behaviour (with charter)\n\nSlice-Id: slice-01",
            # Same evidence source as the setup call above -- the file is
            # still on disk (a `git reset --soft` never touches the working
            # tree), so this remains a real, currently-passing pytest file.
            "--at-kind",
            "pytest-regression",
            "--regression-test-file",
            "tests/unit/test_slice_01.py",
        ]
    )
    capsys.readouterr()
    assert exit_2 == 0

    push_result = subprocess.run(
        ["git", "push", "origin", "HEAD:refs/heads/main"],
        cwd=repo,
        capture_output=True,
        text=True,
    )
    assert push_result.returncode == 0, (
        f"a plain `git push` (no --force) must succeed -- the SHA already on "
        f"origin ({on_origin_sha}) must never have been rewritten by "
        f"`commit-slice`. Observed rejection:\n{push_result.stderr}\n"
        "This is the exact 2026-07-11 incident symptom: a non-fast-forward "
        "push, resolved in production only via --force-with-lease."
    )
