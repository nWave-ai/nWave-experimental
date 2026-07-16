"""Regression: `des commit-slice` must never sweep EXTRANEOUS staged content
into a slice commit.

Incident (empirical, 2026-07-11, CRITICAL): commit ``140da7ceb`` shipped a
test-fixture ``pyproject.toml`` (473 real lines replaced) plus
``tests/test_fail.py`` (``assert False``) because they sat staged in the
index when `commit-slice` ran. `commit-slice` stages the DECLARED scope
(``_stage``, ``src/des/cli/commit_slice.py:741-771`` -- ``git add -- <paths>``
or ``git add -A`` under ``--all``) but then commits the ENTIRE index
(``_commit_with_placeholder``, :774-793, a plain ``git commit`` over whatever
the index happens to contain) -- any content staged BEFOREHAND by another
actor (a concurrent agent, a stray ``git add``, a test writing to the live
repo) travels silently inside the slice commit. The poisoned commit was
PUSHED and required a dedicated bonifica commit (``b3c5f4784``).

Charter: ``docs/feature/fix-commit-slice-index-isolation/feature-delta.md``.

The oracle (this AT's contract, NOT implemented here -- test-authoring only,
zero ``src/`` edits): with an EXTRANEOUS file already staged in the index,
``des commit-slice --path <slice-files>`` MUST NOT silently include it. The
honest behavior is a LOUD refusal (GDP-3: what/why/how) that NAMES each
extraneous staged path and both cures -- unstage it
(``git restore --staged <file>``) or include it intentionally
(``--path``/``--all``) -- and exits non-zero WITHOUT committing. A clean
index stays byte-identical to today. ``--all`` is exempt by construction (the
operator explicitly asked for everything). An extraneous entry INSIDE a
directory already covered by a declared ``--path`` is NOT extraneous
(prefix-match on directories, exact match on files -- same normalization git
uses).

The fix locus (design reference, not touched by this AT): the staged-snapshot
check wraps ``_stage`` (``src/des/cli/commit_slice.py:741``) -- snapshot
``git diff --cached --name-only`` BEFORE staging the declared paths; after
staging, any snapshot entry not covered by the declared scope is extraneous
-> emit ``CommitRefusedExtraneousStagedContent`` (what/why/how, an
``extraneous: [...]`` list) and exit non-zero before any commit lands.

Driving surface (Mandate-13 driving-port-only, Layer 3 in-process default +
real git subprocess I/O, Mandate-6 real-IO): the REAL
``des.cli.commit_slice.main()`` CLI driver, captured via ``capsys``, against
a REAL hermetic git repository -- the only way to observe the actual silent-
sweep the incident produced.

Fixture reuse (per dispatch instruction -- do NOT hand-roll a new harness):
``_init_repo`` / ``_git`` / ``_last_json_event`` mirror
``tests/bugs/des/test_commit_slice_never_amends_pushed.py`` verbatim (which
itself mirrors ``tests/des/integration/test_commit_slice.py``) -- the exact
pytest-collectible git work-tree shape that already makes ``des
commit-slice``'s whole-tree committed-scope digest + build-tier/examine-gate
checks pass cleanly today, with a ``--feature-id`` (now MANDATORY -- see
``CommitRefusedMissingFeatureId``, the earliest-possible GDP-1 guard that
fires before any git mutation, including before this file's own
extraneous-staged-content guard) and NO ``--no-verify-commit`` (the harness
installs no git hooks, so there is nothing to skip -- matching every prior
sibling test's precedent).
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
    ``tests/bugs/des/test_commit_slice_never_amends_pushed.py``'s
    ``_init_repo`` verbatim).
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


def _last_json_event(stdout: str) -> dict:
    json_lines = [line for line in stdout.splitlines() if line.strip().startswith("{")]
    assert json_lines, f"expected a JSON payload line on stdout, got: {stdout!r}"
    return json.loads(json_lines[-1])


# ---------------------------------------------------------------------------
# NEGATIVE AT -- the named regression test, active-RED today
# ---------------------------------------------------------------------------


def test_commit_slice_never_sweeps_extraneous_staged_content(
    tmp_path: Path, capsys
) -> None:
    """Reproduces the 140da7ceb incident shape: an EXTRANEOUS file
    (``poison.txt``, standing in for the poisoned ``pyproject.toml`` +
    ``tests/test_fail.py``) is already staged in the index -- by a
    concurrent actor, NOT by this invocation -- when `commit-slice` runs
    declaring a DIFFERENT ``--path`` (the genuine slice content).

    Expected (the contract): a LOUD refusal -- non-zero exit, NO commit
    created (HEAD unchanged), naming ``poison.txt`` and both cures
    (``git restore --staged``, or including it via ``--path``/``--all``).

    RED today for the right reason: `_stage` (:741) stages only the declared
    path via ``git add -- <path>``, but never inspects what was ALREADY
    staged; `_commit_with_placeholder` (:774) then commits WHATEVER the
    index contains -- ``poison.txt`` rides along silently. A semantic
    `AssertionError` on the refusal (exit_code stays 0, event stays
    ``SliceCommitted``), not a crash or collection error.
    """
    repo = tmp_path / "repo"
    _init_repo(repo)

    # An actor OTHER than this commit-slice invocation stages an extraneous
    # file -- the exact incident precondition (a poisoned pyproject.toml sat
    # staged when commit-slice ran).
    poison = repo / "poison.txt"
    poison.write_text("not part of this slice\n", encoding="utf-8")
    _git(repo, "add", "poison.txt")

    # The genuine slice content -- authored but NOT yet staged.
    slice_file = repo / "tests" / "unit" / "test_new_slice_behaviour.py"
    slice_file.write_text(
        "def test_new_slice_behaviour():\n    assert 1 + 1 == 2\n", encoding="utf-8"
    )

    head_before = _git(repo, "rev-parse", "HEAD").strip()

    exit_code = commit_slice_main(
        [
            "--repo",
            str(repo),
            "--feature-id",
            "fix-commit-slice-index-isolation",
            "--path",
            str(slice_file.relative_to(repo)),
            "--message",
            "feat(slice): add new slice behaviour\n\nSlice-Id: slice-01",
        ]
    )
    event = _last_json_event(capsys.readouterr().out)

    assert exit_code != 0, (
        f"expected a LOUD refusal when an extraneous file (poison.txt) is "
        f"already staged outside the declared --path scope -- got "
        f"exit_code=0, event={event!r}. Today `commit-slice` silently "
        "commits the ENTIRE index (poison.txt rides along), reproducing "
        "the 140da7ceb poisoned-pyproject/test_fail incident."
    )

    head_after = _git(repo, "rev-parse", "HEAD").strip()
    assert head_after == head_before, (
        f"a refused commit must NOT create a new commit -- HEAD moved from "
        f"{head_before} to {head_after}, event={event!r}"
    )

    assert event.get("event") == "CommitRefusedExtraneousStagedContent", (
        f"expected the dedicated refusal event, got event={event!r}"
    )
    extraneous = event.get("extraneous") or []
    assert "poison.txt" in extraneous, (
        f"the refusal must NAME the extraneous staged path -- got "
        f"extraneous={extraneous!r}"
    )
    how = str(event.get("how") or "")
    assert "restore --staged" in how, (
        f"the refusal must state the unstage cure (`git restore --staged`) "
        f"-- got how={how!r}"
    )
    assert "--path" in how or "--all" in how, (
        f"the refusal must state the include-intentionally cure "
        f"(--path/--all) -- got how={how!r}"
    )


# ---------------------------------------------------------------------------
# PIN AT -- clean-index invariance, GREEN today AND after the fix
# ---------------------------------------------------------------------------


def test_commit_slice_clean_index_unaffected_by_path(tmp_path: Path, capsys) -> None:
    """PIN: with NOTHING pre-staged, `commit-slice --path <file>` behaves
    exactly as today -- a commit lands carrying only the declared path.
    This is the byte-identical-behavior guard the extraneous-content fix
    must never break. Expected GREEN both before and after the fix.
    """
    repo = tmp_path / "repo"
    _init_repo(repo)

    slice_file = repo / "tests" / "unit" / "test_clean_index_slice.py"
    slice_file.write_text(
        "def test_clean_index_slice():\n    assert 2 + 2 == 4\n", encoding="utf-8"
    )

    exit_code = commit_slice_main(
        [
            "--repo",
            str(repo),
            "--feature-id",
            "fix-commit-slice-index-isolation",
            "--path",
            str(slice_file.relative_to(repo)),
            "--message",
            "feat(slice): add clean-index slice behaviour\n\nSlice-Id: slice-01",
            "--at-kind",
            "pytest-regression",
            "--regression-test-file",
            str(slice_file.relative_to(repo)),
        ]
    )
    event = _last_json_event(capsys.readouterr().out)

    assert exit_code == 0, f"expected the clean-index commit to land -- event={event!r}"
    assert event.get("event") == "SliceCommitted", event

    log = _git(repo, "log", "--oneline").strip().splitlines()
    assert len(log) == 2, f"expected exactly base+new commits, got: {log!r}"

    tracked = _git(repo, "ls-tree", "-r", "--name-only", "HEAD")
    assert "tests/unit/test_clean_index_slice.py" in tracked


# ---------------------------------------------------------------------------
# PIN AT -- --all exemption, GREEN today AND after the fix
# ---------------------------------------------------------------------------


def test_commit_slice_all_flag_exempt_from_extraneous_check(
    tmp_path: Path, capsys
) -> None:
    """PIN: with an extraneous file already staged, `commit-slice --all`
    still succeeds and includes it -- the operator explicitly asked for
    everything, so `--all` is exempt from the extraneous-content refusal by
    construction. Expected GREEN both before and after the fix.
    """
    repo = tmp_path / "repo"
    _init_repo(repo)

    extraneous = repo / "already_staged.txt"
    extraneous.write_text("staged ahead of time\n", encoding="utf-8")
    _git(repo, "add", "already_staged.txt")

    slice_file = repo / "tests" / "unit" / "test_all_flag_slice.py"
    slice_file.write_text(
        "def test_all_flag_slice():\n    assert 3 + 3 == 6\n", encoding="utf-8"
    )

    exit_code = commit_slice_main(
        [
            "--repo",
            str(repo),
            "--feature-id",
            "fix-commit-slice-index-isolation",
            "--all",
            "--message",
            "feat(slice): add all-flag slice behaviour\n\nSlice-Id: slice-01",
            "--at-kind",
            "pytest-regression",
            "--regression-test-file",
            str(slice_file.relative_to(repo)),
        ]
    )
    event = _last_json_event(capsys.readouterr().out)

    assert exit_code == 0, (
        f"expected --all to succeed even with pre-staged content -- event={event!r}"
    )
    assert event.get("event") == "SliceCommitted", event

    tracked = _git(repo, "ls-tree", "-r", "--name-only", "HEAD")
    assert "already_staged.txt" in tracked, (
        "--all is exempt by construction -- the pre-staged file must be "
        f"included, got tracked={tracked!r}"
    )
    assert "tests/unit/test_all_flag_slice.py" in tracked


# ---------------------------------------------------------------------------
# PIN AT -- declared-scope prefix coverage, GREEN today AND after the fix
# ---------------------------------------------------------------------------


def test_commit_slice_extraneous_entry_inside_declared_path_is_not_refused(
    tmp_path: Path, capsys
) -> None:
    """PIN: an entry already staged INSIDE a directory that IS declared via
    ``--path`` is NOT extraneous (prefix-match on directories) -- no
    refusal. Simulates a companion file staged ahead of time by another
    actor, but within the same declared slice directory. Expected GREEN
    both before and after the fix.
    """
    repo = tmp_path / "repo"
    _init_repo(repo)

    slice_dir = repo / "tests" / "unit" / "slice_subdir"
    slice_dir.mkdir(parents=True)

    # Staged ahead of time by another actor -- but INSIDE the declared scope.
    companion = slice_dir / "companion.py"
    companion.write_text("def helper():\n    return True\n", encoding="utf-8")
    _git(repo, "add", str(companion.relative_to(repo)))

    # Not yet staged -- staged by this invocation via --path.
    main_file = slice_dir / "test_subdir_slice.py"
    main_file.write_text(
        "def test_subdir_slice():\n    assert True\n", encoding="utf-8"
    )

    exit_code = commit_slice_main(
        [
            "--repo",
            str(repo),
            "--feature-id",
            "fix-commit-slice-index-isolation",
            "--path",
            str(slice_dir.relative_to(repo)),
            "--message",
            "feat(slice): add subdir slice behaviour\n\nSlice-Id: slice-01",
            "--at-kind",
            "pytest-regression",
            "--regression-test-file",
            str(main_file.relative_to(repo)),
        ]
    )
    event = _last_json_event(capsys.readouterr().out)

    assert exit_code == 0, (
        f"an entry already staged INSIDE the declared --path directory must "
        f"NOT be refused (prefix-match) -- event={event!r}"
    )
    assert event.get("event") == "SliceCommitted", event

    tracked = _git(repo, "ls-tree", "-r", "--name-only", "HEAD")
    assert "tests/unit/slice_subdir/companion.py" in tracked
    assert "tests/unit/slice_subdir/test_subdir_slice.py" in tracked
