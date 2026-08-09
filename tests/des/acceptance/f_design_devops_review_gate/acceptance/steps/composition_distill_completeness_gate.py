"""Composition root for f-design-devops-review-gate slice-03 (DISTILL Phase-2.5).

The AT-completeness auto-fire wiring: ``check-slice-at-completeness`` (the
EXISTING completeness CLI, ZERO new gate logic -- already registered in the des
dispatcher at src/des/cli/__main__.py:74) is referenced from the DISTILL wave
gate-out stack. slice-03 carries NO new verdict core -- it is a pure WIRING
slice: a DATA-row reference resolved through a REAL shipped surface.

RECONCILIATION FLAG (brief slice-06 registry MOVE): the feature-delta text says
"wave_gate_stacks.distill.gate-out (flavor)", but that wording PREDATES the
slice-06 registry move. ``wave_gate_stack_dispatch.resolve_stack`` reads the
canonical registry ``nWave/waves/<wave>.yaml`` as the SOLE gate-stack source
(ADR-FLOW-006 D6) -- the flavor-private ``distill`` co-tenant block in
atdd_pure.yaml (owned by f-coherence-and-attestation) is NOT the surface the spine
resolves. AT-10 therefore targets the REGISTRY HOME ``nWave/waves/distill.yaml``,
consistent with the slice-01/02 ``design.yaml`` + ``devops.yaml``.

DRIVING SURFACE (Mandate-13 driving-port-only -- the REAL wired seam, no
direct-domain import for business logic):

  * Layer 3 composition (AT-10) -- the REAL spine
    ``wave_gate_stack_dispatch.resolve_stack("distill", "gate-out")`` reading the
    SHIPPED canonical registry ``nWave/waves/distill.yaml`` (the SAME spine entry
    the live SubagentStop gate-out caller uses, subagent_stop_service.py:344). The
    observable is the ordered gate-id sequence the resolution returns. REUSES the
    slice-01 stdlib registry scanner over the SAME registry shape
    (``_scan_boundary_gate_ids``) for the independent read #1.

DORMANT-SEAM RECONCILIATION (Mandate-15 / S3): the DISTILL driving-surface
declares the load-bearing net-new seam reached from the spine's real entry
point:

  (seam-1) the canonical registry file ``nWave/waves/distill.yaml`` carrying
           ``gate_stack.gate-out`` with the ``check-slice-at-completeness`` row
           (brief §6 / DDD-5: the registry HOME, mirroring design.yaml +
           devops.yaml) -- resolved through the WIRED spine ``resolve_stack``.

AT-10 NAMES this seam, drives it through the REAL entry point, and asserts an
observable effect (the resolved gate-id sequence).

RED contract (fail-for-right-reason, atdd_pure active-RED -- NOT @skip):
  * AT-10: ``nWave/waves/distill.yaml`` does not exist at HEAD -> the spine
    resolves an EMPTY DISTILL gate-out stack -> a semantic AssertionError naming
    the missing registry file / check-slice-at-completeness row.

  Every dependency (pytest-bdd, the REAL spine resolver, the SHIPPED repo
  files) resolves cleanly -- the RED is a deliberate missing-wiring signal, not
  a test bug.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING

# REUSE the slice-01 driving-surface primitives VERBATIM (SSOT, no duplication):
# the shipped repo-root anchor + the stdlib registry scanner. The DISTILL wave
# rides the SAME registry-resolution machinery as DESIGN / DEVOPS.
from .composition_design_review_gate import REPO_ROOT, _scan_boundary_gate_ids


if TYPE_CHECKING:
    # The typed domain vocabulary is consumed only as method-parameter
    # annotations here (the runtime enum VALUES are passed in by the test
    # binding) -- so the import is a typing-only import (ruff TC001).
    from .domain_types_distill import WaveBoundary


# The SHIPPED canonical wave-contract registry file (ADR-FLOW-006 D1) for DISTILL.
_WAVES_DIR = REPO_ROOT / "nWave" / "waves"
_DISTILL_REGISTRY_FILE = _WAVES_DIR / "distill.yaml"

# The DISTILL wave whose gate-out stack is migrated to the canonical registry.
_DISTILL_WAVE = "distill"

# The EXISTING completeness CLI gate-id this slice wires into the gate-out
# stack (brief DDD-5: zero new gate logic -- the gate-id is the 1:1 dispatcher
# name, already registered at src/des/cli/__main__.py:74).
_AT_COMPLETENESS_GATE_ID = "check-slice-at-completeness"


def _distill_sequence_declared_in_registry_file(
    boundary: WaveBoundary,
) -> tuple[str, ...]:
    """Read the DISTILL gate-id sequence DIRECTLY from the registry FILE.

    Independent read #1 of the AT-10 two-reads cross-check: a direct stdlib parse
    of the SHIPPED ``nWave/waves/distill.yaml`` (the REUSED slice-01 scanner over
    the SAME registry shape), WITHOUT going through the spine. At HEAD the file is
    absent -> returns the empty tuple (the RED for AT-10).
    """
    try:
        text = _DISTILL_REGISTRY_FILE.read_text(encoding="utf-8")
    except (FileNotFoundError, IsADirectoryError, UnicodeDecodeError, OSError):
        return ()
    return _scan_boundary_gate_ids(text, boundary.value)


def _distill_sequence_resolved_by_spine(boundary: WaveBoundary) -> tuple[str, ...]:
    """Resolve the DISTILL gate-id sequence through the WIRED spine entry.

    Independent read #2 of the AT-10 two-reads cross-check: drives the REAL
    ``wave_gate_stack_dispatch.resolve_stack("distill", boundary)`` -- the SAME
    spine entry the live SubagentStop gate-out caller uses
    (subagent_stop_service.py:344). The spine reads the canonical registry as the
    SOLE gate-stack source (ADR-FLOW-006 D6). At HEAD ``nWave/waves/distill.yaml``
    is absent -> the spine resolves the empty stack (the RED for AT-10).
    """
    from des.application import wave_gate_stack_dispatch

    resolved = wave_gate_stack_dispatch.resolve_stack(_DISTILL_WAVE, boundary.value)
    return tuple(
        str(row["gate_id"])
        for row in resolved.rows
        if isinstance(row, dict) and "gate_id" in row
    )


@dataclass
class DistillCompletenessGateComposition:
    """Drives the DISTILL AT-completeness wiring through its REAL wired seam.

    AT-10 reads the SHIPPED repo registry (the spine resolution seam) -- no tmp
    work-tree, no fixture authoring of the expected stack (the shipped
    artifact, or its absence, IS the contract).
    """

    repo_dir: Path
    _resolved_boundary: WaveBoundary | None = field(default=None)

    # ---- AT-10 given/when/then: DISTILL registry -> spine seam ---------------

    def given_distill_registry_file_is_shipped(self) -> None:
        """Arm the SUT to read the SHIPPED canonical distill registry from the repo.

        No fixture authoring of the expected output -- the registry FILE is the
        shipped artifact the SUT reads (Mandate-13 protocol-driver). At HEAD the
        file is absent; the absence is the RED.
        """
        # Nothing to set up beyond pointing at the shipped path -- the file itself
        # (or its absence) is the contract under test.

    def when_dispatcher_resolves_distill_gate_out_from_registry(
        self, boundary: WaveBoundary
    ) -> None:
        """Bind WHICH boundary the Then must cross-check (the reads happen in Then)."""
        self._resolved_boundary = boundary

    def then_resolved_sequence_equals_registry_declared(
        self, boundary: WaveBoundary
    ) -> None:
        """The spine-resolved DISTILL sequence equals the registry-FILE-declared one.

        AT-completeness auto-fire wiring proof (Mandate-15 seam-1): two
        INDEPENDENT reads of the DISTILL gate-out gate-id sequence must agree --
        read #1 the registry FILE (stdlib parse, NOT the spine), read #2 the WIRED
        spine entry ``resolve_stack``. Agreement proves resolve_stack ACTUALLY
        reads the distill registry (NOT registry==registry). Non-empty so a
        both-empty trivial pass cannot satisfy it.

        RED at HEAD: ``nWave/waves/distill.yaml`` is absent -> read #1 empty ->
        semantic AssertionError naming the missing registry file.
        """
        self._assert_boundary_matches_when(boundary)
        declared = _distill_sequence_declared_in_registry_file(boundary)
        resolved = _distill_sequence_resolved_by_spine(boundary)
        assert declared, (
            "the DISTILL gate-out gate stack must be DECLARED (non-empty) in the "
            f"canonical registry file {_DISTILL_REGISTRY_FILE} (brief slice-06 "
            "reconciliation: the registry HOME, mirroring nWave/waves/design.yaml "
            "+ devops.yaml; ADR-FLOW-006 D6 -- resolve_stack reads the registry as "
            "the SOLE gate-stack source, NOT the flavor-private distill block) -- "
            "read #1 resolved EMPTY (the distill registry file does not exist yet). "
            f"{self._observed()}"
        )
        assert resolved == declared, (
            "the WIRED spine entry wave_gate_stack_dispatch.resolve_stack must "
            f"resolve the DISTILL {boundary.value} stack to the SAME gate-id "
            "sequence the registry FILE declares (the AT-completeness auto-fire "
            "wiring, AT-10) -- two independent reads (registry-FILE-declared vs "
            "spine-resolved) must agree, proving resolve_stack reads the distill "
            f"registry, not registry==registry; declared {declared!r}, spine-resolved "
            f"{resolved!r}. {self._observed()}"
        )

    def then_resolved_stack_includes_check_slice_at_completeness(
        self, boundary: WaveBoundary
    ) -> None:
        """The resolved DISTILL gate-out stack carries the AT-completeness gate.

        Seam-named oracle (Mandate-15 seam-1): the gate-out stack the spine
        resolves must include the ``check-slice-at-completeness`` gate-id (brief
        DDD-5: the EXISTING completeness CLI auto-fired from the gate-stack, so an
        incomplete slice is refused on the DISTILL return -- NOT by /nw-distill
        orchestration prose, closing KPI-3). RED at HEAD: the registry file is
        absent -> the resolved stack is empty -> semantic AssertionError naming
        the missing row.
        """
        self._assert_boundary_matches_when(boundary)
        resolved = _distill_sequence_resolved_by_spine(boundary)
        assert _AT_COMPLETENESS_GATE_ID in resolved, (
            f"the DISTILL {boundary.value} stack the spine resolves must include "
            f"the {_AT_COMPLETENESS_GATE_ID!r} gate (brief DDD-5: the EXISTING "
            "completeness CLI -- zero new gate logic -- auto-fired from the DISTILL "
            "gate-out so AT-completeness is checked mechanically, not by "
            f"orchestration prose) -- the resolved sequence {resolved!r} does not "
            f"carry it. {self._observed()}"
        )

    # ---- when/then guards ----------------------------------------------------

    def _assert_boundary_matches_when(self, boundary: WaveBoundary) -> None:
        assert self._resolved_boundary is not None, (
            "the dispatcher resolution must run (When) before asserting (Then)"
        )
        assert self._resolved_boundary is boundary, (
            f"Then boundary {boundary.value!r} must match the boundary resolved in "
            f"When ({self._resolved_boundary.value!r}) -- scenario wiring drift"
        )

    # ---- diagnostics ---------------------------------------------------------

    def _observed(self) -> str:
        return (
            f"distill_registry_file_exists={_DISTILL_REGISTRY_FILE.is_file()}; "
            f"waves_dir={_WAVES_DIR}; resolved_boundary={self._resolved_boundary!r}"
        )
