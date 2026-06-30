"""Floor-arming fixture helper for wave-gateout slice-01 (NOT the composition root).

Mandate-13 import-boundary discipline: the composition root
(``composition_wave_gateout.py``, the SUT-driving surface) must stay free of
``des.domain.*`` imports. Arming the DESIGN wave floor is a *precondition-state*
operation -- it needs the ``WaveActiveRecord`` domain VO to construct the record
the REAL ``WaveActiveFilesystemStore().arm(...)`` adapter writes. This helper
isolates that single domain dependency here, OUTSIDE the composition root, so the
composition root imports only this fixture's plain-Python entry point.

The arming still goes through the REAL adapter (no mock); only the IMPORT boundary
moves: the domain VO is constructed here, the adapter is the production one.
"""

from __future__ import annotations

import json
from pathlib import Path


def activate_des_governance(project_root: Path) -> None:
    """Opt the synthetic project into DES governance (precondition, NOT the SUT).

    ADR-AG-001 added an activation gate at the single hook dispatch point
    (``hook_router.main`` -> ``activation_gate.apply_gate``): a hook invocation in
    a project the gate resolves as INACTIVE exits 0 (silent allow) BEFORE
    ``handle_subagent_stop`` -- and therefore before the wave review-verdict
    gate-out -- ever runs. The synthetic tmp work-tree these ATs build is a bare
    ``git init`` with no activation marker, so under the opt-in default
    (``activation_policy._FRESH_INSTALL_DEFAULT_MODE == "opt-in"``) the gate
    silences the hook and the gate-out is never reached.

    Writing ``.nwave/local-config.json`` with ``enabled_for_repo: true`` is the
    REAL per-project opt-in the production resolver reads
    (``DESConfig.enabled_for_repo`` -> ``resolve_activation(True, ...) is True``):
    the project is positively active, so the hook DISPATCHES into the production
    handler. This is INPUT precondition state (the project opted into governance),
    NOT the expected block/allow OUTPUT -- the wave-closure decision is still
    produced by the REAL gate-out, never authored by this fixture (No Fixture
    Theater).
    """
    marker = project_root / ".nwave" / "local-config.json"
    marker.parent.mkdir(parents=True, exist_ok=True)
    marker.write_text(json.dumps({"enabled_for_repo": True}), encoding="utf-8")


def arm_design_floor(project_root: Path, wave: str) -> None:
    """Arm an INFERRED wave floor at ``project_root`` via the REAL adapter.

    The active-wave discriminant the gate-out keys on (read from
    ``.nwave/wave-active`` at the return's cwd, never self-reported). Constructs the
    ``WaveActiveRecord`` domain VO HERE (the fixture edge), feeds it to the
    production ``WaveActiveFilesystemStore`` adapter -- the composition root never
    sees ``des.domain.*``.
    """
    from des.adapters.driven.filesystem.wave_active_filesystem_store import (
        WaveActiveFilesystemStore,
    )
    from des.domain.wave_active import WaveActiveRecord, WaveProvenance

    WaveActiveFilesystemStore().arm(
        project_root,
        WaveActiveRecord(wave=wave, provenance=WaveProvenance.INFERRED),
    )
