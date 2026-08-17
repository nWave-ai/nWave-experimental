"""Shared repo-root + feature path resolution (SSOT).

Single source of truth for the repo-root convention that was hand-copied
across several CLI modules and the subagent-stop hook:

- ``resolve_repo_root`` -- the repo root: ``--repo-root`` flag, then
  ``NWAVE_REPO_ROOT`` env, then ``Path.cwd()``. As shipped ``des.`` modules
  live under ``~/.claude/lib/python`` with no enclosing repo, so a
  ``__file__``-relative ``parents[N]`` fallback is broken-by-design on an
  installed instance. Both authoritative inputs name the root explicitly;
  ``Path.cwd()`` is the layout-independent fallback.

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


#: The repo-relative directory holding one feature's documents.
FEATURE_DOCS_SEGMENTS = ("docs", "feature")


def feature_dir_path(repo: Path, feature_id: str) -> Path:
    """The ``docs/feature/<feature_id>`` directory under ``repo``."""
    return repo.joinpath(*FEATURE_DOCS_SEGMENTS, feature_id)


#: The repo-relative directory holding one feature's expectation charter
#: (the ``atdd_pure`` bugfix lane's OWN evidence artifact -- ``des
#: charter-scaffold`` + a filled ``nw-product-owner`` pass -- never a
#: feature-delta).
EXPECTATION_DOCS_SEGMENTS = ("docs", "product", "expectations")


def expectation_charter_dir_path(repo: Path, feature_id: str) -> Path:
    """The ``docs/product/expectations/<feature_id>`` directory under ``repo``."""
    return repo.joinpath(*EXPECTATION_DOCS_SEGMENTS, feature_id)


def has_expectation_charter(repo: Path, feature_id: str) -> bool:
    """True iff a non-empty expectation charter is authored for ``feature_id``.

    Consolidated here (bugfix fix-at-review-verdict-charter-form, slice-01)
    from the byte-identical predicate previously private to
    ``des.cli.verify_readiness_pre_dispatch`` -- second call site
    (``des.cli.at_review_verdict``) makes this a shared concept, so it moves
    to the domain-layer SSOT (AD-05: no shared logic in ``cli/``) rather than
    being imported cross-module as a private symbol or re-implemented a third
    time.
    """
    charter_dir = expectation_charter_dir_path(repo, feature_id)
    return charter_dir.is_dir() and any(charter_dir.glob("*.md"))
