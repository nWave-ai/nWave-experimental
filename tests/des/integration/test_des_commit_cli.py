"""Integration tests for the des-commit CLI (issue #51, Issue 2 / ADR-027).

`des-commit` is the locked, fail-closed commit helper that lets parallel
DELIVER sub-agents commit their own files against one shared working tree
without cross-staging each other's work. The contract:

1. A commit contains EXACTLY the caller's owned paths — never another
   agent's still-staged files (``git commit --only`` semantics).
2. Another agent's staged work is left staged (not reset) after the call.
3. Concurrent callers serialize on a file lock, so none hit git's index.lock
   contention and none sweep up a neighbour's files.
4. The commit carries the ``Step-Id:`` trailer DES integrity gates rely on.

These use a real git repo (subprocess), matching
``tests/des/acceptance/test_git_commit_verification.py``.
"""

from __future__ import annotations

import subprocess
import threading
from pathlib import Path


def _git(repo: Path, *args: str) -> str:
    result = subprocess.run(
        ["git", "-C", str(repo), *args],
        capture_output=True,
        check=True,
        text=True,
    )
    return result.stdout


def _init_git_repo(path: Path) -> None:
    """Init a repo with local identity and an initial commit (valid HEAD)."""
    _git(path, "init")
    _git(path, "config", "user.email", "test@example.com")
    _git(path, "config", "user.name", "Test User")
    (path / ".gitkeep").write_text("")
    _git(path, "add", ".gitkeep")
    _git(path, "commit", "-m", "Initial commit")


def _committed_files(repo: Path, ref: str = "HEAD") -> set[str]:
    # core.quotePath=false so non-ASCII paths are read literally, not C-quoted.
    out = _git(
        repo, "-c", "core.quotePath=false", "show", "--name-only", "--format=", ref
    )
    return {line.strip() for line in out.splitlines() if line.strip()}


def _commit_count(repo: Path) -> int:
    return int(_git(repo, "rev-list", "--count", "HEAD").strip())


def _staged_files(repo: Path) -> set[str]:
    out = _git(repo, "-c", "core.quotePath=false", "diff", "--cached", "--name-only")
    return {line.strip() for line in out.splitlines() if line.strip()}


def _install_precommit_hook(repo: Path, body: str) -> None:
    """Install an executable .git/hooks/pre-commit running *body*."""
    hook = repo / ".git" / "hooks" / "pre-commit"
    hook.parent.mkdir(parents=True, exist_ok=True)
    hook.write_text(f"#!/bin/sh\n{body}\n")
    hook.chmod(0o755)


class TestDesCommitScoping:
    """A des-commit commits only owned paths, leaving foreign staged work alone."""

    def test_commits_only_owned_path_ignoring_foreign_staged_file(self, tmp_path):
        from des.cli.commit import main

        _init_git_repo(tmp_path)

        # This agent owns a.py; a *foreign* agent has already staged b.py.
        (tmp_path / "a.py").write_text("owned = 1\n")
        (tmp_path / "b.py").write_text("foreign = 1\n")
        _git(tmp_path, "add", "b.py")  # foreign work, staged before our call

        rc = main(
            [
                "--repo-dir",
                str(tmp_path),
                "--owned-paths",
                "a.py",
                "--step-id",
                "01-01",
                "--message",
                "feat: add a",
            ]
        )

        assert rc == 0
        # The new commit contains ONLY our owned file.
        assert _committed_files(tmp_path) == {"a.py"}
        # The foreign agent's staged work is untouched (still staged).
        staged = {
            line.strip()
            for line in _git(tmp_path, "diff", "--cached", "--name-only").splitlines()
            if line.strip()
        }
        assert "b.py" in staged

    def test_commit_carries_step_id_trailer(self, tmp_path):
        from des.cli.commit import main

        _init_git_repo(tmp_path)
        (tmp_path / "a.py").write_text("owned = 1\n")

        rc = main(
            [
                "--repo-dir",
                str(tmp_path),
                "--owned-paths",
                "a.py",
                "--step-id",
                "02-03",
                "--message",
                "feat: add a",
            ]
        )

        assert rc == 0
        body = _git(tmp_path, "log", "-1", "--format=%B")
        assert "Step-Id: 02-03" in body

    def test_broad_owned_directory_commits_source_and_config_not_tracked_runtime(
        self, tmp_path
    ):
        _init_git_repo(tmp_path)
        source = tmp_path / "a.py"
        config = tmp_path / ".nwave/config.json"
        runtime = tmp_path / ".nwave/des/handover.json"
        runtime.parent.mkdir(parents=True)
        source.write_text("owned = 1\n")
        config.write_text('{"rigor":"standard"}\n')
        historical_runtime = '{"request":"historical","values":[]}\n'
        runtime.write_text(historical_runtime)
        _git(tmp_path, "add", "a.py", ".nwave/config.json", ".nwave/des/handover.json")
        _git(tmp_path, "commit", "-m", "Seed source, config and legacy runtime")
        before = _git(tmp_path, "rev-parse", "HEAD").strip()
        assert ".nwave/des/handover.json" in _git(tmp_path, "ls-files").splitlines()

        source.write_text("owned = 2\n")
        config.write_text('{"rigor":"custom"}\n')
        current_runtime = '{"request":"current","values":[]}\n'
        runtime.write_text(current_runtime)

        assert (
            _run(
                tmp_path, ["."], step_id="runtime-01", message="feat: source and config"
            )
            == 0
        )

        assert _committed_files(tmp_path) == {"a.py", ".nwave/config.json"}
        assert _git(tmp_path, "rev-parse", "HEAD^").strip() == before
        assert _git(tmp_path, "show", "HEAD:a.py") == source.read_text()
        assert _git(tmp_path, "show", "HEAD:.nwave/config.json") == config.read_text()
        # Already-tracked history stays intact; only the new runtime bytes are excluded.
        assert _git(tmp_path, "show", f"{before}:.nwave/des/handover.json") == (
            historical_runtime
        )
        assert _git(tmp_path, "show", "HEAD:.nwave/des/handover.json") == (
            historical_runtime
        )
        assert runtime.read_text() == current_runtime
        assert _staged_files(tmp_path) == set()
        assert _git(tmp_path, "diff", "--name-only").splitlines() == [
            ".nwave/des/handover.json"
        ]
        assert (tmp_path / ".nwave/des/.gitignore").is_file()
        assert _git(tmp_path, "check-ignore", ".nwave/des/commit.lock").strip() == (
            ".nwave/des/commit.lock"
        )
        assert "Step-Id: runtime-01" in _git(tmp_path, "log", "-1", "--format=%B")


class TestDesCommitConcurrentNoCrossStaging:
    """Concurrent des-commit calls each commit exactly their own file."""

    def test_concurrent_commits_do_not_cross_stage(self, tmp_path):
        from des.cli.commit import main

        _init_git_repo(tmp_path)

        num_agents = 8
        files = [f"f{i:02d}.py" for i in range(num_agents)]
        for name in files:
            (tmp_path / name).write_text(f"# {name}\n")

        barrier = threading.Barrier(num_agents)
        errors: list[int] = []

        def worker(idx: int) -> None:
            barrier.wait()  # maximise overlap on the shared index
            rc = main(
                [
                    "--repo-dir",
                    str(tmp_path),
                    "--owned-paths",
                    files[idx],
                    "--step-id",
                    f"{idx:02d}-01",
                    "--message",
                    f"feat: add {files[idx]}",
                ]
            )
            if rc != 0:
                errors.append(rc)

        threads = [
            threading.Thread(target=worker, args=(i,)) for i in range(num_agents)
        ]
        for th in threads:
            th.start()
        for th in threads:
            th.join()

        assert not errors, f"some des-commit calls failed: {errors}"

        # Exactly num_agents new commits landed on top of the initial commit.
        assert _commit_count(tmp_path) == num_agents + 1

        # Every owned file is committed exactly once, in its own commit, with
        # no commit carrying another agent's file.
        hashes = _git(tmp_path, "rev-list", "HEAD", "--not", f"HEAD~{num_agents}")
        committed_sets = [
            _committed_files(tmp_path, h) for h in hashes.split() if h.strip()
        ]
        assert len(committed_sets) == num_agents
        for fileset in committed_sets:
            assert len(fileset) == 1, f"a commit cross-staged files: {fileset}"
        all_committed = set().union(*committed_sets)
        assert all_committed == set(files)


def _run(tmp_path, owned, step_id="01-01", message="feat: change"):
    from des.cli.commit import main

    argv = ["--repo-dir", str(tmp_path)]
    argv += ["--owned-paths", *owned]
    argv += ["--step-id", step_id, "--message", message]
    return main(argv)


class TestDesCommitHookCannotCrossStage:
    """A pre-commit hook that stages a foreign file must not contaminate the commit."""

    def test_hook_staged_foreign_file_never_lands(self, tmp_path):
        _init_git_repo(tmp_path)
        (tmp_path / "a.py").write_text("owned = 1\n")
        (tmp_path / "foreign.py").write_text("foreign = 1\n")
        # A hook that auto-stages a foreign file the moment a commit runs.
        _install_precommit_hook(tmp_path, "git add foreign.py")

        rc = _run(tmp_path, ["a.py"], message="feat: add a")

        assert rc == 0
        # The commit must contain ONLY the owned file — never the hook's foreign one.
        assert _committed_files(tmp_path) == {"a.py"}
        # foreign.py is still uncommitted in the working tree.
        assert "foreign.py" not in _committed_files(tmp_path)
        assert (tmp_path / "foreign.py").exists()


class TestDesCommitPathForms:
    """Path-form variations must commit the right file, never a false invariant error."""

    def test_dot_slash_relative_path(self, tmp_path):
        _init_git_repo(tmp_path)
        (tmp_path / "a.py").write_text("owned = 1\n")
        assert _run(tmp_path, ["./a.py"]) == 0
        assert _committed_files(tmp_path) == {"a.py"}

    def test_absolute_path(self, tmp_path):
        _init_git_repo(tmp_path)
        (tmp_path / "a.py").write_text("owned = 1\n")
        assert _run(tmp_path, [str(tmp_path / "a.py")]) == 0
        assert _committed_files(tmp_path) == {"a.py"}

    def test_directory_owned_path(self, tmp_path):
        _init_git_repo(tmp_path)
        (tmp_path / "pkg").mkdir()
        (tmp_path / "pkg" / "m.py").write_text("m = 1\n")
        (tmp_path / "pkg" / "n.py").write_text("n = 1\n")
        assert _run(tmp_path, ["pkg"]) == 0
        assert _committed_files(tmp_path) == {"pkg/m.py", "pkg/n.py"}

    def test_non_ascii_path(self, tmp_path):
        _init_git_repo(tmp_path)
        (tmp_path / "café.py").write_text("owned = 1\n")
        assert _run(tmp_path, ["café.py"]) == 0
        assert _committed_files(tmp_path) == {"café.py"}


class TestDesCommitDeletions:
    """des-commit must be able to commit a deletion of an owned file."""

    def test_deleted_owned_file_is_committed(self, tmp_path):
        _init_git_repo(tmp_path)
        (tmp_path / "seed.py").write_text("seed = 1\n")
        _git(tmp_path, "add", "seed.py")
        _git(tmp_path, "commit", "-m", "seed")

        (tmp_path / "seed.py").unlink()  # delete the owned file

        assert _run(tmp_path, ["seed.py"], message="refactor: drop seed") == 0
        # The deletion is recorded; seed.py is gone from HEAD's tree.
        tree = _git(tmp_path, "ls-tree", "--name-only", "HEAD")
        assert "seed.py" not in tree.split()


class TestDesCommitIndexHygiene:
    """After des-commit, owned paths are clean and foreign staged work is preserved."""

    def test_foreign_staged_preserved_and_owned_clean(self, tmp_path):
        _init_git_repo(tmp_path)
        (tmp_path / "a.py").write_text("owned = 1\n")
        (tmp_path / "b.py").write_text("foreign = 1\n")
        _git(tmp_path, "add", "b.py")  # foreign staged before our call

        assert _run(tmp_path, ["a.py"], message="feat: add a") == 0

        # Foreign staged work is untouched.
        assert "b.py" in _staged_files(tmp_path)
        # Owned file is committed and clean — not lingering as staged or modified.
        assert "a.py" in _committed_files(tmp_path)
        assert "a.py" not in _staged_files(tmp_path)
        unstaged = {
            line.strip()
            for line in _git(tmp_path, "diff", "--name-only").splitlines()
            if line.strip()
        }
        assert "a.py" not in unstaged


def _terminal(captured: str) -> dict[str, str]:
    return dict(line.split(": ", 1) for line in captured.splitlines() if ": " in line)


class TestDesCommitSpeaksTheStepTerminal:
    """One terminal dialect: the commit it made, or WHAT / WHY / HOW."""

    def test_success_names_the_commit_it_created(self, tmp_path, capsys):
        _init_git_repo(tmp_path)
        (tmp_path / "a.py").write_text("owned = 1\n")

        assert _run(tmp_path, ["a.py"], step_id="02-03") == 0

        rows = _terminal(capsys.readouterr().out)
        assert rows["DELIVERY-OUTCOME"] == "Success"
        assert rows["COMMIT"] == _git(tmp_path, "rev-parse", "HEAD").strip()
        assert rows["STEP-ID"] == "02-03"

    def test_an_unchanged_owned_path_is_a_refusal_with_a_how(self, tmp_path, capsys):
        _init_git_repo(tmp_path)
        before = _commit_count(tmp_path)

        assert _run(tmp_path, [".gitkeep"]) == 1

        rows = _terminal(capsys.readouterr().out)
        assert rows["DELIVERY-OUTCOME"] == "Refusal"
        assert ".gitkeep" in rows["WHY"]
        assert rows["HOW"]
        assert _commit_count(tmp_path) == before
