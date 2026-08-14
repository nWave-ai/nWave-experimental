"""Gitignore repair for explicitly configured nWave projects (ADR-AG-004).

The explicit ``nwave-ai project enable|disable`` command owns project marker
creation.  This service only keeps that marker trackable; hooks never call it
and never create ``.nwave`` in an inactive project.
"""

from __future__ import annotations

from typing import TYPE_CHECKING


if TYPE_CHECKING:
    from pathlib import Path


class ProjectGitignoreService:
    """Repair nWave ignore rules without deciding project activation."""

    def __init__(self, *, read_only: bool = False) -> None:
        self._read_only = read_only

    def fix_gitignore(self, *, project_root: Path) -> None:
        """Apply the dual-layer gitignore fix idempotently (ADR-AG-004)."""
        if self._read_only:
            return
        self._fix_root_gitignore(project_root)
        self._fix_nested_gitignore(project_root)

    def _fix_root_gitignore(self, project_root: Path) -> None:
        from des.domain.root_gitignore_fix import fix_root_gitignore

        path = project_root / ".gitignore"
        try:
            current = path.read_text(encoding="utf-8") if path.exists() else ""
            fixed = fix_root_gitignore(current)
            if fixed != current:
                path.write_text(fixed, encoding="utf-8")
        except OSError:
            return

    def _fix_nested_gitignore(self, project_root: Path) -> None:
        """Repair the nested ignore via the shared canonical helper."""
        from des.domain.nwave_dir_gitignore import ensure_nwave_gitignore

        ensure_nwave_gitignore(project_root / ".nwave")
