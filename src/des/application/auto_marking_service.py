"""Silent auto-marking application service (ADR-AG-003).

Reads the per-project marker via ``DESConfig``; if ``enabled_for_repo`` is
explicitly present (true OR false) it is a no-op (sticky in both directions);
else if the trigger's evidence predicate holds it writes
``{"enabled_for_repo": true}`` then fixes both gitignore layers. Bounded-change
mutation set: ``{.nwave/local-config.json, .nwave/.gitignore, <root>/.gitignore}``.
Fail-open: a read-only / unwritable filesystem never raises.

The return value is the production-side ``AdoptionOutcome`` enum. The acceptance
composition adapts it to the test-domain ``AdoptionResult`` at the boundary
(production never imports test types).
"""

from __future__ import annotations

import json
from enum import Enum
from pathlib import Path


class AdoptionTrigger(Enum):
    """Which auto-marking trigger fired (DDD-7)."""

    REAL_FEATURE_USE = "real-feature-use"  # pre-task nw-* dispatch


class AdoptionOutcome(Enum):
    """Outcome of ``adopt_if_warranted`` (ADR-AG-003)."""

    ADOPTED = "adopted"  # marker written
    NOT_WARRANTED = "not-warranted"  # no evidence -> no write
    NO_OP_STICKY = "no-op-sticky"  # marker already present (any value) -> no write


_MARKER_RELATIVE = Path(".nwave") / "local-config.json"


class AutoMarkingService:
    """Writes the marker + fixes gitignore behind a sticky guard."""

    def __init__(self, *, read_only: bool = False) -> None:
        self._read_only = read_only

    def adopt_if_warranted(
        self, *, project_root: Path, trigger: AdoptionTrigger
    ) -> AdoptionOutcome:
        """Adopt the project if the trigger's evidence warrants it.

        Returns ADOPTED / NOT_WARRANTED / NO_OP_STICKY. Never raises on a
        read-only filesystem (fail-open).
        """
        if self._marker_present(project_root):
            return AdoptionOutcome.NO_OP_STICKY
        if not self._evidence_warrants(project_root, trigger):
            return AdoptionOutcome.NOT_WARRANTED
        if not self._write_marker(project_root):
            return AdoptionOutcome.NOT_WARRANTED
        self.fix_gitignore(project_root=project_root)
        return AdoptionOutcome.ADOPTED

    def fix_gitignore(self, *, project_root: Path) -> None:
        """Apply the dual-layer gitignore fix idempotently (ADR-AG-004)."""
        if self._read_only:
            return
        self._fix_root_gitignore(project_root)
        self._fix_nested_gitignore(project_root)

    # ---- guards + evidence ----

    def _marker_present(self, project_root: Path) -> bool:
        """Whether ``enabled_for_repo`` is explicitly present (sticky guard)."""
        from des.adapters.driven.config.des_config import DESConfig

        return DESConfig(cwd=project_root).enabled_for_repo is not None

    def _evidence_warrants(self, project_root: Path, trigger: AdoptionTrigger) -> bool:
        return trigger is AdoptionTrigger.REAL_FEATURE_USE

    # ---- writes (fail-open) ----

    def _write_marker(self, project_root: Path) -> bool:
        """Write the trackable marker; return False on a write failure (fail-open)."""
        if self._read_only:
            return False
        marker = project_root / _MARKER_RELATIVE
        try:
            marker.parent.mkdir(parents=True, exist_ok=True)
            marker.write_text(
                json.dumps({"enabled_for_repo": True}, indent=2) + "\n",
                encoding="utf-8",
            )
        except OSError:
            return False
        return True

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
        """Repair the nested ignore via the shared single-source-of-truth helper.

        Delegates to ``ensure_nwave_gitignore`` (the EXTEND verdict): both nested
        writers now emit identical canonical content (banner + ``*`` +
        ``!local-config.json``), so a later runtime ``ensure_nwave_gitignore`` call can
        never re-ignore the marker. User-customized (non-banner) files are left
        untouched by the shared helper.
        """
        from des.domain.nwave_dir_gitignore import ensure_nwave_gitignore

        nested = project_root / ".nwave"
        ensure_nwave_gitignore(nested)
