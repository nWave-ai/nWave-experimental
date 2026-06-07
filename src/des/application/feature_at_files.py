"""SSOT for resolving a feature's ``.feature`` AT files on disk.

The ``@feature-{id}`` resolver: given a repo and a feature id, return every
``.feature`` file authored for that feature, wherever DISTILL placed it.

This is application-layer logic -- it orchestrates a filesystem walk (``rglob``)
and reads file contents -- so it lives above the domain but below the CLI.
``run_contract_gate``, ``carpaccio_slice_gate``, ``carpaccio_precheck`` (CLI
driving ports) and ``slice_at_completeness`` (application) all import it from
here. It previously lived in ``des.cli.carpaccio_format`` and was imported
DOWNWARD by the application layer, inverting the hexagonal layering (AD-05 /
the AD-22 application->CLI cycle). The CLI may depend on the application layer;
the reverse is illegal.

Pure-read, stdlib-only (no ``import yaml``) per the DES-bundle contract: it
reads the filesystem and mutates nothing.
"""

from __future__ import annotations

from typing import TYPE_CHECKING


if TYPE_CHECKING:
    from pathlib import Path


def _legacy_acceptance_dir(repo: Path, feature_id: str) -> Path:
    """The pre-F-04 hardcoded AT directory for ``feature_id``.

    A ``.feature`` file under ``tests/scripts/cli/{feature_id}/acceptance``
    is feature-scoped by its directory name, so it is bound to ``feature_id``
    even when it carries no file-level ``@feature-`` tag.
    """
    return repo / "tests" / "scripts" / "cli" / feature_id / "acceptance"


def feature_tag_files(repo: Path, feature_id: str) -> list[Path]:
    """Resolve every ``.feature`` file authored for ``feature_id``.

    F-04 (atdd-pure-dogfooding-friction-2026-05-20.md): the gate must find a
    feature's ``.feature`` files wherever DISTILL placed them, not only under
    a hardcoded ``tests/scripts/cli/{feature_id}/acceptance`` path. A file is
    bound to the feature when it self-identifies with a file-level
    ``@feature-{feature_id}`` tag preceding its ``Feature:`` header, OR it
    lives under the legacy feature-scoped acceptance directory. The legacy
    path stays a source -- it is no longer the ONLY source.
    """
    tests_dir = repo / "tests"
    if not tests_dir.is_dir():
        return []
    wanted = f"@feature-{feature_id}"
    legacy_dir = _legacy_acceptance_dir(repo, feature_id)
    matched: set[Path] = set()
    for path in tests_dir.rglob("*.feature"):
        if wanted in _file_feature_tags(path) or legacy_dir in path.parents:
            matched.add(path)
    return sorted(matched)


def _file_feature_tags(path: Path) -> tuple[str, ...]:
    """Collect the file-level ``@`` tags appearing before the ``Feature:`` line."""
    tags: list[str] = []
    for raw in path.read_text(encoding="utf-8", errors="replace").splitlines():
        stripped = raw.strip()
        if not stripped:
            continue
        if stripped.startswith("#"):
            # Gherkin comment line -- may precede the file-level tag block.
            continue
        if stripped.startswith("@"):
            tags.extend(stripped.split())
            continue
        if stripped.startswith("Feature:"):
            break
        # Any other non-blank content before Feature: -- stop scanning tags.
        break
    return tuple(tags)
