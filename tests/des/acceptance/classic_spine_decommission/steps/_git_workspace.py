"""Shared git-workspace harness for the classic-spine-decommission suite.

TD-8 (`F-TESTDEBT-CLASSIC-GIT-WORKSPACE-DRY`): the four production-wired
composition roots in `composition.py` each duplicated the same git-workspace
plumbing -- a `git -C <workspace>` subprocess runner, the `parents[5]` repo-root
walk, the `git init` + identity-config bootstrap, and the `PYTHONPATH`-augmented
subprocess environment. This module single-sources that plumbing.

Feature-local by design: the cross-feature CLI-subprocess SSOT is owned
separately by AD-56. Nothing here changes behaviour -- it is a byte-equivalent
extraction of the duplicated helpers.
"""

from __future__ import annotations

import os
import subprocess
from pathlib import Path


# The repository root, four `steps/` levels plus the feature/acceptance/des/tests
# stack up from this file -- the value every composition root previously
# re-derived via `Path(__file__).resolve().parents[5]`.
_REPO_ROOT: Path = Path(__file__).resolve().parents[5]


def repo_root() -> Path:
    """The nWave-dev repository root (the `parents[5]` walk, single-sourced)."""
    return _REPO_ROOT


def subprocess_env(*, include_repo_on_path: bool = False) -> dict[str, str]:
    """A subprocess environment with `src/` (and optionally the repo root) on PYTHONPATH.

    Mirrors the `env = dict(os.environ); env["PYTHONPATH"] = ...` pattern the
    composition roots repeated for every real-CLI subprocess. When
    `include_repo_on_path` is True the repo root is appended after `src/`
    (the F-13 `at_review_verdict` invocation needs both on the path).
    """
    env = dict(os.environ)
    src = str(_REPO_ROOT / "src")
    if include_repo_on_path:
        env["PYTHONPATH"] = os.pathsep.join((src, str(_REPO_ROOT)))
    else:
        env["PYTHONPATH"] = src
    return env


def run_git(workspace: Path, *args: str) -> subprocess.CompletedProcess[str]:
    """Run a `git -C <workspace>` subprocess, checked (the de-duplicated `_git`)."""
    return subprocess.run(
        ["git", "-C", str(workspace), *args],
        capture_output=True,
        text=True,
        check=True,
    )


def git_init_with_identity(workspace: Path) -> None:
    """Init `workspace` as a git repo and set the fixture commit identity.

    The shared half of every composition root's repo bootstrap: `git init -q`
    plus the `fixture@nwave.test` / `Fixture` user identity. Callers stage and
    commit the fixture tree themselves (the commit message differs per root).
    """
    run_git(workspace, "init", "-q")
    run_git(workspace, "config", "user.email", "fixture@nwave.test")
    run_git(workspace, "config", "user.name", "Fixture")
