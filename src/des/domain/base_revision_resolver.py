"""Observe a repository's HEAD as a schema-shaped ``base-revision`` string.

Shared by ``des prepare-ordinary-request`` (ADR-SSOT-002 Section 4d) and
``des compile-contract`` -- both need the SAME ``git-sha1:<hex>`` /
``git-sha256:<hex>`` projection of the physical repository's observed HEAD,
never guessed or hand-formatted twice. Extracted from
``des.cli.prepare_ordinary_request``'s own private helpers (behavior-
preserving move, not a new algorithm) so a second CLI needing the identical
fact does not re-derive it.
"""

from __future__ import annotations

import subprocess
from typing import TYPE_CHECKING


if TYPE_CHECKING:
    from pathlib import Path


_HEX_LEN_TO_TAG = {40: "git-sha1:", 64: "git-sha256:"}
_HEX_ALPHABET = frozenset("0123456789abcdef")


def git_output(repo_root: Path, *args: str) -> str | None:
    """Run ``git -C repo_root *args``; stripped stdout, or ``None`` on failure."""
    try:
        result = subprocess.run(
            ["git", "-C", str(repo_root), *args],
            capture_output=True,
            text=True,
            check=False,
            stdin=subprocess.DEVNULL,
            timeout=5,
        )
    except (OSError, subprocess.TimeoutExpired):
        return None
    if result.returncode != 0:
        return None
    return result.stdout.strip()


def observed_base_revision(repo_root: Path) -> str | None:
    """The schema-shaped ``git-sha1:<hex>``/``git-sha256:<hex>`` HEAD identity,
    or ``None`` when HEAD cannot be observed or its hex shape is unrecognized."""
    head = git_output(repo_root, "rev-parse", "HEAD")
    if not head:
        return None
    tag = _HEX_LEN_TO_TAG.get(len(head))
    if tag is None or not set(head) <= _HEX_ALPHABET:
        return None
    return f"{tag}{head}"
