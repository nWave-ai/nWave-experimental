"""Acceptance supports for `config follows the repository`.

Everything here drives ONLY the declared public port: the real `des` process
(`python -m des blast-radius --repo . --paths alpha.txt beta.txt`), whose
stdout grammar is documented at src/des/cli/blast_radius.py:13-31.

No git binary is used anywhere -- the worktree checkouts are hand-built with
plain `pathlib` writes, byte-for-byte in the shape `git worktree add`
produces (a `.git` FILE bearing a `gitdir:` line, a per-worktree
administrative directory, and git's own `commondir` marker inside it). The
project `.nwave/config.json` is likewise only ever written, never git-added,
so the fixture cannot depend on that file being tracked.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path


# The discriminator token emitted by the S/M reason builder when the effective
# `blast_radius.small_max_files` threshold is the repository-rooted 1 rather
# than the canonical default 2, for the two scope files the fixture names.
DISCRIMINATOR_REASON = "files=2 > small_max_files=1"

REPO_ROOTED_THRESHOLD = {"blast_radius": {"small_max_files": 1}}


@dataclass(frozen=True)
class PortOutcome:
    """The observable terminal of one real `des blast-radius` invocation."""

    exit_code: int
    stdout: str
    stderr: str

    @property
    def verdict(self) -> dict:
        """The single-line JSON verdict token on stdout."""
        lines = [line for line in self.stdout.splitlines() if line.strip()]
        assert lines, f"no stdout token at all; stderr was:\n{self.stderr}"
        return json.loads(lines[-1])

    @property
    def event(self) -> str:
        return self.verdict["event"]

    @property
    def reasons(self) -> list[str]:
        return list(self.verdict["reasons"])


def write_config(root: Path, payload: dict) -> None:
    """Write a project `.nwave/config.json` under `root` (never git-added)."""
    config_dir = root / ".nwave"
    config_dir.mkdir(parents=True, exist_ok=True)
    (config_dir / "config.json").write_text(json.dumps(payload), encoding="utf-8")


def make_scope_files(checkout: Path) -> None:
    """Create the two NON-python scope entries the port is asked to measure.

    Non-python on purpose: the measurement's consumer-count and boundary-file
    analyses skip non-`.py` scope entries outright, so neither can contribute
    a competing reason and starve the `files=` discriminator.
    """
    checkout.mkdir(parents=True, exist_ok=True)
    (checkout / "alpha.txt").write_text("alpha\n", encoding="utf-8")
    (checkout / "beta.txt").write_text("beta\n", encoding="utf-8")


def make_plain_checkout(root: Path) -> Path:
    """An ordinary, NON-worktree checkout: a `.git` DIRECTORY marker.

    The `.git/HEAD` file is part of the shape a real checkout always has, and
    the fixture must carry it for the same reason it carries the `commondir`
    marker: fidelity to what `git init` / `git worktree add` really produce.
    """
    git_dir = root / ".git"
    git_dir.mkdir(parents=True, exist_ok=True)
    (git_dir / "HEAD").write_text("ref: refs/heads/main\n", encoding="utf-8")
    make_scope_files(root)
    return root


def make_worktree_checkout(
    common_root: Path,
    checkout: Path,
    *,
    name: str = "lane",
    commondir_contents: str | None = None,
) -> Path:
    """Hand-build a `git worktree add`-shaped checkout of `common_root`.

    `commondir_contents` defaults to git's own relative `../..` marker;
    passing something else (e.g. a dangling path) deliberately breaks the
    common-root ascent so the unresolvable branch can be observed.
    """
    common_git = common_root / ".git"
    admin = common_git / "worktrees" / name
    admin.mkdir(parents=True, exist_ok=True)
    # Real checkouts carry a `HEAD` at the common git dir and at every
    # per-worktree administrative dir; only the `commondir` CONTENT is ever
    # deliberately broken by this fixture, never the admin dir itself.
    (common_git / "HEAD").write_text("ref: refs/heads/main\n", encoding="utf-8")
    (admin / "HEAD").write_text("ref: refs/heads/lane\n", encoding="utf-8")
    (admin / "commondir").write_text(
        "../..\n" if commondir_contents is None else commondir_contents,
        encoding="utf-8",
    )
    (admin / "gitdir").write_text(f"{checkout / '.git'}\n", encoding="utf-8")

    checkout.mkdir(parents=True, exist_ok=True)
    (checkout / ".git").write_text(f"gitdir: {admin}\n", encoding="utf-8")
    make_scope_files(checkout)
    return checkout


def measure_blast_radius(checkout: Path, home: Path, *, path_dir: Path) -> PortOutcome:
    """Run the real `des` process in `checkout` and return its terminal.

    The child environment is pinned so the observation is
    operator-independent and provably git-free:

    * `HOME` **and** `NWAVE_AGENTS_HOME` point at `home`, an empty fixture
      directory, so the operator's real `~/.nwave/config.json` global rung
      cannot forge (or suppress) the observation. `NWAVE_AGENTS_HOME` takes
      precedence over `HOME`, so pinning `HOME` alone is not enough.
    * `CLAUDE_CONFIG_DIR`, `CODEX_HOME` and `DES_PROJECT_DIR` are REMOVED --
      each is an alternative channel to the same two rungs.
    * `PATH` is pinned to `path_dir`, an empty directory containing no `git`
      binary, so any attempt to resolve the repository root by shelling out
      to `git` cannot succeed.
    """
    home.mkdir(parents=True, exist_ok=True)
    path_dir.mkdir(parents=True, exist_ok=True)

    env = dict(os.environ)
    for leak in ("CLAUDE_CONFIG_DIR", "CODEX_HOME", "DES_PROJECT_DIR"):
        env.pop(leak, None)
    env["HOME"] = str(home)
    env["NWAVE_AGENTS_HOME"] = str(home)
    env["PATH"] = str(path_dir)

    completed = subprocess.run(
        [
            sys.executable,
            "-m",
            "des",
            "blast-radius",
            "--repo",
            ".",
            "--paths",
            "alpha.txt",
            "beta.txt",
        ],
        cwd=str(checkout),
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )
    return PortOutcome(
        exit_code=completed.returncode,
        stdout=completed.stdout,
        stderr=completed.stderr,
    )
