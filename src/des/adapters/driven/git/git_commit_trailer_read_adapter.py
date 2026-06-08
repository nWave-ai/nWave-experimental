"""GitCommitTrailerReadAdapter -- git implementation of CommitTrailerReadPort.

slice-01 of gate-trailer-read-git-port-extract (DESIGN Reuse Analysis). The
concrete git side of the commit-trailer read boundary, mirroring the established
``ChangedSymbolPort`` <-> ``GitChangedSymbolAdapter`` pattern: the done-gate logic
depends on the PORT, this adapter implements it with ``git log --format=%B%x1e``.

git enters here ONLY (AD-21 git-free mandate; the gate logic stays git-free). The
EARNED-TRUST invariant this adapter pins: every git failure (binary absent ->
``FileNotFoundError``; ``repo`` not a work-tree -> ``git log`` non-zero ->
``CalledProcessError``, since ``git_text`` runs ``check=True``) returns
``Indeterminate(reason)``, NEVER an empty ``CommitMessages(())``. An empty
``CommitMessages(())`` is ONLY returned on git SUCCESS with a genuinely empty
history -- masking a git failure as an empty stream would fabricate the silent
"nothing shipped" pass the degrade-LOUD mandate forbids.
"""

from __future__ import annotations

import subprocess
from typing import TYPE_CHECKING

from des.adapters.driven.git.git_subprocess import git_text
from des.ports.driven_ports.commit_trailer_read_port import (
    CommitMessage,
    CommitMessages,
    CommitTrailerReadPort,
    Indeterminate,
)


if TYPE_CHECKING:
    from pathlib import Path


# The ASCII record separator git emits after each commit body (``%x1e``), the
# split token the done-gate's trailer scan consumes.
_RECORD_SEPARATOR = "\x1e"


class GitCommitTrailerReadAdapter(CommitTrailerReadPort):
    """Reads a repo's commit-message stream out of git.

    ``commit_messages`` returns the repo's commit-message bodies (``git log
    --format=%B%x1e``, split on the record separator), or an ``Indeterminate``
    when git is absent / ``repo`` is not a work-tree. ``commit_message`` returns
    the body of a single commit (``git show -s --format=%B <sha>``), or an
    ``Indeterminate`` on any git failure. Pure read of the git history -- no
    filesystem mutation.
    """

    def commit_messages(self, repo: Path) -> CommitMessages | Indeterminate:
        """Return the repo's commit-message stream, or Indeterminate.

        ``git log --format=%B%x1e`` (each commit body terminated by the ASCII
        record separator). A missing git binary (``FileNotFoundError``) or a
        non-zero exit (``repo`` not a work-tree -> ``CalledProcessError`` from
        ``git_text``'s ``check=True``) degrades LOUD to ``Indeterminate`` -- never
        an empty ``CommitMessages(())`` that would silently read downstream as
        "nothing shipped".
        """
        try:
            stdout = git_text(repo, "log", f"--format=%B{_RECORD_SEPARATOR}")
        except FileNotFoundError as exc:
            return Indeterminate(f"git binary not found: {exc}")
        except subprocess.CalledProcessError as exc:
            return Indeterminate(
                f"git log failed (exit {exc.returncode}): "
                f"{(exc.stderr or '').strip()[:200]}"
            )
        messages = tuple(stdout.split(_RECORD_SEPARATOR))
        return CommitMessages(messages)

    def commit_message(self, repo: Path, sha: str) -> CommitMessage | Indeterminate:
        """Return the body of a single commit, or Indeterminate.

        ``git show -s --format=%B <sha>``. A missing git binary
        (``FileNotFoundError``) or a non-zero git exit (unresolvable SHA /
        not-a-work-tree -> ``CalledProcessError`` from ``git_text``'s
        ``check=True``) degrades LOUD to ``Indeterminate`` -- never a raw
        exception to the caller (AD-24 uniform-INDETERMINATE mandate). Mirrors
        the ``commit_messages`` exception-translation contract exactly.
        """
        try:
            body = git_text(repo, "show", "-s", "--format=%B", sha)
        except FileNotFoundError as exc:
            return Indeterminate(f"git binary not found: {exc}")
        except subprocess.CalledProcessError as exc:
            return Indeterminate(
                f"git show failed (exit {exc.returncode}): "
                f"{(exc.stderr or '').strip()[:200]}"
            )
        return CommitMessage(body=body)


__all__ = ["GitCommitTrailerReadAdapter"]
