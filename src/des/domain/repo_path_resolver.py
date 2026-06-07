"""Shared repo-root + feature-delta path resolution (SSOT).

Single source of truth for two path conventions that were hand-copied across
several CLI modules and the subagent-stop hook:

- ``resolve_repo_root`` -- the repo root: ``--repo-root`` flag, then
  ``NWAVE_REPO_ROOT`` env, then ``Path.cwd()``. As shipped ``des.`` modules
  live under ``~/.claude/lib/python`` with no enclosing repo, so a
  ``__file__``-relative ``parents[N]`` fallback is broken-by-design on an
  installed instance. Both authoritative inputs name the root explicitly;
  ``Path.cwd()`` is the layout-independent fallback.
- ``feature_delta_path`` -- the feature-delta markdown file for a feature id
  under a given repo root (a pure path-join convention).

DRY consolidation (behavior-preserving): the bodies were byte-identical across
``des.cli.carpaccio_slice_gate``, ``des.cli.carpaccio_precheck``,
``des.cli.at_review_verdict``, and the subagent-stop hook. Resolved here in the
domain layer (AD-05: no shared logic in ``cli/``) so both CLI and adapter call
sites import the one definition.
"""

from __future__ import annotations

import os
from pathlib import Path


def resolve_repo_root(override: str | None) -> Path:
    """Resolve the repo root: ``--repo-root`` flag, then env, then cwd."""
    if override:
        return Path(override)
    env = os.environ.get("NWAVE_REPO_ROOT")
    if env:
        return Path(env)
    return Path.cwd()


def feature_delta_path(repo: Path, feature_id: str) -> Path:
    """The feature-delta markdown file for ``feature_id`` under ``repo``."""
    return repo / "docs" / "feature" / feature_id / "feature-delta.md"
