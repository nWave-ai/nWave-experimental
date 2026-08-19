"""K4 matrix row 10 -- arm workspace has no git commit identity.

Run 10: the root delivered the whole feature (1762 tests OK), staged the
exact file set, and `git commit` failed `fatal: empty ident name` -- under
the arm env there is no `user.name`/`user.email` for git to fall back on
(Claude's own sandbox denies reading `~/`, so even a real operator
`~/.gitconfig` is unreachable regardless of what `HOME` points at). The
crafter correctly refused to set git config itself, then had its own
retry (`git -c user.name=<the operator's real name> ...`) correctly
blocked by Auto-root's own Bash allowlist -- exactly the IP/authorship
leak a repo-LOCAL identity, set once during setup, forecloses at the
source.

`preflight.probe_git_identity` proves a commit is possible -- via `git var
GIT_COMMITTER_IDENT`, the SAME identity check `git commit` itself performs
-- deterministically, with NO model call, before arms.json is written.
"""

from __future__ import annotations

import subprocess

import pytest

from scripts.analysis.k4 import preflight


def _git(*args: str, cwd) -> None:
    subprocess.run(["git", *args], cwd=cwd, check=True, capture_output=True, text=True)


def _make_repo(tmp_path):
    repo = tmp_path / "repo"
    repo.mkdir()
    _git("init", "-q", "-b", "master", cwd=repo)
    (repo / "README.md").write_text("seed\n")
    return repo


def _fake_home_env(tmp_path) -> dict[str, str]:
    """A fresh, empty HOME with no `.gitconfig` at all -- the same
    observable effect Claude's sandbox produces by denying `~/` reads
    regardless of what `HOME` names, reproduced here without needing a
    real sandboxed `claude` process for a fast, portable unit test."""
    home = tmp_path / "fake-home"
    home.mkdir()
    return {"HOME": str(home), "PATH": "/usr/bin:/bin"}


def test_probe_reports_a_problem_under_a_fake_home_with_no_identity(tmp_path):
    repo = _make_repo(tmp_path)
    env = _fake_home_env(tmp_path)

    problems = preflight.probe_git_identity(repo, env)

    assert problems, (
        "a workspace with no resolvable git commit identity must be "
        "reported, not silently treated as commit-able"
    )
    joined = " ".join(problems).lower()
    assert "identity" in joined


def test_probe_succeeds_once_a_repo_local_identity_is_set(tmp_path):
    repo = _make_repo(tmp_path)
    env = _fake_home_env(tmp_path)
    _git("config", "user.name", "K4 test arm", cwd=repo)
    _git("config", "user.email", "k4-test@nwave.invalid", cwd=repo)

    problems = preflight.probe_git_identity(repo, env)

    assert problems == []


def test_probe_never_mutates_the_workspace(tmp_path):
    """Read-only: `git var GIT_COMMITTER_IDENT` proves identity without
    creating a commit, branch, or any other repository-state change --
    unlike an `--allow-empty` commit-then-reset approach, this canary can
    never itself leave the workspace in a different state than it found
    it, on either its success or its failure path."""
    repo = _make_repo(tmp_path)
    env = _fake_home_env(tmp_path)
    _git("config", "user.name", "K4 test arm", cwd=repo)
    _git("config", "user.email", "k4-test@nwave.invalid", cwd=repo)

    before_head = subprocess.run(
        ["git", "symbolic-ref", "HEAD"],
        cwd=repo,
        capture_output=True,
        text=True,
    )
    before_status = subprocess.run(
        ["git", "status", "--porcelain"], cwd=repo, capture_output=True, text=True
    ).stdout

    preflight.probe_git_identity(repo, env)

    after_head = subprocess.run(
        ["git", "symbolic-ref", "HEAD"],
        cwd=repo,
        capture_output=True,
        text=True,
    )
    after_status = subprocess.run(
        ["git", "status", "--porcelain"], cwd=repo, capture_output=True, text=True
    ).stdout

    assert before_head.stdout == after_head.stdout
    assert before_status == after_status


@pytest.mark.parametrize("arm_name", ["control", "nwave"])
def test_git_identity_steps_are_executable_and_prove_the_probe(tmp_path, arm_name):
    """End to end, portable: run the arm's OWN declared `git config` steps
    (`_git_identity_steps`) against a real throwaway repo, then confirm
    `probe_git_identity` proves them sufficient -- proving the two halves
    (setup steps and the canary) agree, not just each in isolation."""
    repo = _make_repo(tmp_path)
    env = _fake_home_env(tmp_path)

    for step in preflight._git_identity_steps(arm_name):
        subprocess.run(step, cwd=repo, check=True, capture_output=True, text=True)

    problems = preflight.probe_git_identity(repo, env)

    assert problems == []
