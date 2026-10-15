"""CLI: Commit a step's owned files under an exclusive lock (issue #51, ADR-027).

In parallel multi-agent DELIVER, several sub-agents share one git working tree
and index. Two concurrent ``git commit`` calls race: the second sweeps up files
another agent staged but did not yet commit (cross-staging), and pre-commit
hooks that auto-stage formatter fixes widen the window. The result is
misattributed commits and a corrupted ``Step-Id:`` audit chain.

``des commit`` makes the commit critical section safe:

1. Holds an exclusive ``fcntl.flock(LOCK_EX)`` (same idiom as
   the retired execution-log writer; degrades to no-lock on Windows) so concurrent callers
   serialize and never collide on ``.git/index.lock``.
2. Builds the commit from a **temporary index** seeded with HEAD plus ONLY the
   owned changes outside ``.nwave/des`` (``git read-tree HEAD`` then ordinary
   ``git add -A`` with a runtime exclusion against a private ``GIT_INDEX_FILE``).
   Foreign or hook-staged changes cannot enter this index. ``--no-verify``
   keeps hooks from mutating the commit (the crafter already validated during
   GREEN); ``-A`` records deletions and renames without force-staging ignored files.
3. Resyncs only owned non-runtime paths in the real index to the new HEAD.
   Runtime is excluded from both staging and resync, preserving historical
   runtime in HEAD and foreign staged work in the shared index.

Usage:
    des commit \\
      --repo-root . \\
      --owned-paths src/foo.py tests/test_foo.py \\
      --step-id 02-03 \\
      --message "feat: add foo"

Output is the shared DES terminal block (``des.cli.step_terminal``): a success
names the commit and step; a refusal carries WHAT / WHY / HOW.

Exit codes:
    0 = Success, commit created containing only owned non-runtime changes
    1 = Refusal (nothing to commit, bad repo, git failure)
    2 = Usage error (argparse default for missing/invalid arguments)
"""

from __future__ import annotations

import argparse
import os
import subprocess
import sys
import tempfile
from pathlib import Path

from des.application.commit_message_attribution import attribute_commit_message
from des.application.handover import ensure_runtime_ignored
from des.cli._repo_root_arg import add_repo_root_argument
from des.cli.step_terminal import NOTHING_OWED, StepRefusal, refuse, succeed
from des.domain.commit_trailer_append import append_mechanical_trailer_block


#: The invocation form a refusal names as the move after its HOW.
_AGAIN = (
    "des commit --repo-dir <repo> --owned-paths <path>... --step-id <id> "
    "--message <text> -- after the HOW above"
)

# A bracketed first dot avoids naming an ignored literal directory as an operand.
# Share this subtree exclusion so staging and resync preserve the same runtime.
_RUNTIME_EXCLUSION_PATHSPEC = ":(exclude,top,glob)[.]nwave/des/**"


try:
    import fcntl

    _HAS_FCNTL = True
except ImportError:  # pragma: no cover - Windows has no fcntl
    _HAS_FCNTL = False


def _build_parser() -> argparse.ArgumentParser:
    """Build the argument parser for the commit CLI."""
    parser = argparse.ArgumentParser(
        prog="des.cli.commit",
        description=(
            "Commit a step's owned files under an exclusive lock, scoped so a "
            "parallel agent's staged work is never swept into this commit."
        ),
    )
    add_repo_root_argument(
        parser,
        "--repo-dir",
        default=".",
        help="Path to the git repository (default: current directory)",
    )
    parser.add_argument(
        "--owned-paths",
        required=True,
        nargs="+",
        help="The files this step owns; only these are committed",
    )
    parser.add_argument(
        "--step-id",
        required=True,
        help="Step identifier (e.g., 02-03); recorded as a Step-Id trailer",
    )
    parser.add_argument(
        "--message",
        required=True,
        help="Commit message subject/body (Step-Id trailer appended if absent)",
    )
    return parser


def _git(
    repo: Path, *args: str, env: dict[str, str] | None = None
) -> subprocess.CompletedProcess[str]:
    """Run a git command in *repo*, capturing output (never raises on failure)."""
    return subprocess.run(
        ["git", "-C", str(repo), *args],
        capture_output=True,
        text=True,
        check=False,
        env=env,
    )


def _with_step_id_trailer(message: str, step_id: str) -> str:
    """Append a ``Step-Id:`` trailer unless the message already carries one."""
    if "Step-Id:" in message:
        return message
    return append_mechanical_trailer_block(message, f"Step-Id: {step_id}")


def _commit_owned_locked(
    repo: Path, owned_paths: list[str], message: str
) -> StepRefusal | str:
    """Commit owned non-runtime changes via a temporary index, under a lock.

    Returns the refusal, or the new commit read under the lock. The lock
    (``.nwave/des/commit.lock``) serializes concurrent callers. The commit is
    built from a private index (``GIT_INDEX_FILE``) seeded with HEAD plus owned
    non-runtime changes only, without force-staging ignored files. Runtime under
    ``.nwave/des`` is excluded from staging and shared-index resync; foreign and
    hook-staged changes stay outside the commit, and foreign staged work survives.
    """
    ignored = ensure_runtime_ignored(repo)
    if ignored is not None:
        return StepRefusal(ignored.what, ignored.why, ignored.how)
    lock_path = repo / ".nwave" / "des" / "commit.lock"
    lock_path.parent.mkdir(parents=True, exist_ok=True)

    with open(lock_path, "w", encoding="utf-8") as lock_handle:
        if _HAS_FCNTL:
            fcntl.flock(lock_handle.fileno(), fcntl.LOCK_EX)
        try:
            return _commit_via_scoped_index(repo, owned_paths, message)
        finally:
            if _HAS_FCNTL:
                fcntl.flock(lock_handle.fileno(), fcntl.LOCK_UN)


def _git_refusal(command: str, result: subprocess.CompletedProcess[str]) -> StepRefusal:
    detail = (result.stderr or result.stdout).strip()
    return StepRefusal(
        "CommitFailed",
        f"git {command} exited {result.returncode}: {detail}",
        "repair the repository state Git names, then commit again; the shared "
        "index and working tree were left unchanged",
    )


def _commit_via_scoped_index(
    repo: Path, owned_paths: list[str], message: str
) -> StepRefusal | str:
    """Stage without force and resync owned paths, excluding runtime from both."""
    # A private index file, seeded from HEAD, that only the owned paths are
    # staged into — keeps foreign/hook-staged files out of the commit by
    # construction. mkstemp creates it; unlink so git read-tree writes it fresh.
    fd, tmp_index = tempfile.mkstemp(prefix="des-commit-", suffix=".index")
    os.close(fd)
    Path(tmp_index).unlink()
    env = {**os.environ, "GIT_INDEX_FILE": tmp_index}
    try:
        seed = _git(repo, "read-tree", "HEAD", env=env)
        if seed.returncode != 0:
            return _git_refusal("read-tree", seed)

        # -A stages additions, modifications AND deletions for the owned paths.
        add = _git(
            repo, "add", "-A", "--", *owned_paths, _RUNTIME_EXCLUSION_PATHSPEC, env=env
        )
        if add.returncode != 0:
            return _git_refusal("add", add)

        # Nothing changed in the owned paths relative to HEAD → nothing to commit.
        if _git(repo, "diff", "--cached", "--quiet", env=env).returncode == 0:
            return StepRefusal(
                "NothingToCommit",
                f"the owned paths {' '.join(owned_paths)} hold no change against HEAD",
                "name the paths this step actually changed in --owned-paths, or "
                "skip the commit when the step changed nothing",
            )

        commit = _git(repo, "commit", "--no-verify", "-m", message, env=env)
        if commit.returncode != 0:
            return _git_refusal("commit", commit)
    finally:
        Path(tmp_index).unlink(missing_ok=True)

    # Resync only owned non-runtime paths; preserve foreign staged work, including
    # runtime entries even when the owned set is a broad directory.
    _git(repo, "reset", "-q", "--", *owned_paths, _RUNTIME_EXCLUSION_PATHSPEC)
    return _git(repo, "rev-parse", "HEAD").stdout.strip()


def main(argv: list[str] | None = None) -> int:
    """Entry point for the des-commit CLI tool.

    Args:
        argv: Command-line arguments. Uses sys.argv[1:] if None.

    Returns:
        Exit code: 0=success, 1=refusal, 2=usage error.
    """
    parser = _build_parser()
    args = parser.parse_args(argv)

    repo = Path(args.repo_dir)
    if not (repo / ".git").exists():
        return refuse(
            StepRefusal(
                "RepositoryUnavailable",
                f"{repo} holds no .git, so no commit can be built there",
                "pass --repo-dir naming the repository root",
            ),
            _AGAIN,
        )

    owned_paths: list[str] = list(args.owned_paths)
    message = _with_step_id_trailer(args.message, args.step_id)
    message = attribute_commit_message(repo, message)

    committed = _commit_owned_locked(repo, owned_paths, message)
    if isinstance(committed, StepRefusal):
        return refuse(committed, _AGAIN)
    return succeed([f"COMMIT: {committed}", f"STEP-ID: {args.step_id}"], NOTHING_OWED)


if __name__ == "__main__":
    sys.exit(main())
