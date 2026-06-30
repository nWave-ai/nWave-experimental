"""The OPTIONAL ``runner.json`` override reader (ADR-RTR-001 D7 v3 ⑥ / §V.B).

slice-03 wiring point #3. A convention-following Rust target is ZERO-CONFIG: the
gate DERIVES ``binary(/<snake_feature_id>/)`` from the feature-id and needs no
config file. ``runner.json`` is the OPTIONAL escape hatch a convention-breaking
target opts into -- it ships a ``test_command`` that OVERRIDES the derived
selector.

``read_runner_json(feature_id, repo) -> dict | None`` reads the OPTIONAL file at
``<repo>/docs/feature/<feature_id>/runner.json`` and parses it. Its ABSENCE is the
NORMAL zero-config case (returns ``None``) -- NOT an error, NOT an INDETERMINATE,
NOT a whole-crate fall-back. Only a PRESENT file is parsed (``{feature_id,
test_command, slice}``).

stdlib only (``json`` + ``pathlib``) per the DES-bundle contract (F-D-09): it
reads the filesystem and mutates nothing.
"""

from __future__ import annotations

import json
from typing import TYPE_CHECKING


if TYPE_CHECKING:
    from pathlib import Path


def read_runner_json(feature_id: str, repo: Path) -> dict[str, object] | None:
    """Read the OPTIONAL ``runner.json`` override for ``feature_id`` under ``repo``.

    Looks for ``<repo>/docs/feature/<feature_id>/runner.json``. Returns the parsed
    dict when present, or ``None`` when absent -- the NORMAL zero-config case (the
    convention-derived selector applies), NEVER an error or INDETERMINATE.
    """
    runner_json = repo / "docs" / "feature" / feature_id / "runner.json"
    if not runner_json.is_file():
        return None
    parsed: dict[str, object] = json.loads(runner_json.read_text(encoding="utf-8"))
    return parsed


class RepoRunnerDeclarationMalformed(ValueError):
    """The repo-level ``.nwave/runner.json`` exists but is not valid JSON (D8).

    The typed marker ``read_repo_runner_json`` raises when the whole-tree runner
    declaration is present but unparseable. The resolution seam CATCHES it and
    degrades LOUD to INDETERMINATE naming the malformed declaration -- never an
    uncaught ``JSONDecodeError`` traceback on the operator's terminal.
    """


def read_repo_runner_json(repo: Path) -> dict[str, object] | None:
    """Read the OPTIONAL repo-level ``.nwave/runner.json`` whole-tree declaration (D8).

    The repo-level sibling of ``read_runner_json``: looks for
    ``<repo>/.nwave/runner.json`` -- the operator's whole-tree runner declaration,
    consulted by ``resolve`` ONLY when there is no feature context. Returns the
    parsed dict when present, or ``None`` when absent -- the NORMAL no-declaration
    case (the lockfile-scan applies), NEVER an error or INDETERMINATE. A PRESENT
    but unparseable file raises ``RepoRunnerDeclarationMalformed`` (the caller maps
    it to a LOUD INDETERMINATE, never a crash).
    """
    runner_json = repo / ".nwave" / "runner.json"
    if not runner_json.is_file():
        return None
    try:
        parsed: dict[str, object] = json.loads(runner_json.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise RepoRunnerDeclarationMalformed(str(exc)) from exc
    return parsed


__all__ = [
    "RepoRunnerDeclarationMalformed",
    "read_repo_runner_json",
    "read_runner_json",
]
