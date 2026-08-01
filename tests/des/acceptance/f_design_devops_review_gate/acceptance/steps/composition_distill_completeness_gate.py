"""Composition root for f-design-devops-review-gate slice-03 (DISTILL Phase-2.5).

The AT-completeness auto-fire wiring: ``check-slice-at-completeness`` (the
EXISTING completeness CLI, ZERO new gate logic -- already registered in the des
dispatcher at src/des/cli/__main__.py:74) is referenced from the DISTILL wave
gate-out stack (PRIMARY) AND added to the DELIVER-entry dispatch.pre carpaccio
stack (BACKSTOP). slice-03 carries NO new verdict core -- it is a pure WIRING
slice: two DATA-row references resolved through two REAL shipped surfaces.

RECONCILIATION FLAG (brief slice-06 registry MOVE): the feature-delta text says
"wave_gate_stacks.distill.gate-out (flavor)", but that wording PREDATES the
slice-06 registry move. ``wave_gate_stack_dispatch.resolve_stack`` reads the
canonical registry ``nWave/waves/<wave>.yaml`` as the SOLE gate-stack source
(ADR-FLOW-006 D6) -- the flavor-private ``distill`` co-tenant block in
atdd_pure.yaml (owned by f-coherence-and-attestation) is NOT the surface the spine
resolves. AT-10 therefore targets the REGISTRY HOME ``nWave/waves/distill.yaml``,
consistent with the slice-01/02 ``design.yaml`` + ``devops.yaml``.

DRIVING SURFACE (Mandate-13 driving-port-only -- TWO real wired seams, no
direct-domain import for business logic):

  * Layer 3 composition (AT-10) -- the REAL spine
    ``wave_gate_stack_dispatch.resolve_stack("distill", "gate-out")`` reading the
    SHIPPED canonical registry ``nWave/waves/distill.yaml`` (the SAME spine entry
    the live SubagentStop gate-out caller uses, subagent_stop_service.py:344). The
    observable is the ordered gate-id sequence the resolution returns. REUSES the
    slice-01 stdlib registry scanner over the SAME registry shape
    (``_scan_boundary_gate_ids``) for the independent read #1.

  * Layer 3 composition (AT-11) -- the REAL production flavor dispatcher SSOT
    parser ``flavor_dispatcher._parse_flavor_file`` reading the SHIPPED
    ``nWave/flavors/atdd_pure.yaml`` and projecting ``lifecycle_events["dispatch.pre"]``
    -- the SAME artifact + the SAME stdlib-only parser the live
    ``carpaccio_intercept.evaluate_atdd_pure_dispatch`` consumes on every DELIVER
    Agent/Task dispatch. The observable is the ordered dispatch.pre gate-id
    sequence.

DORMANT-SEAM RECONCILIATION (Mandate-15 / S3): the DISTILL driving-surface
declares the load-bearing net-new seams reached from the spine's + the flavor
dispatcher's real entry points:

  (seam-1) the canonical registry file ``nWave/waves/distill.yaml`` carrying
           ``gate_stack.gate-out`` with the ``check-slice-at-completeness`` row
           (brief §6 / DDD-5: the registry HOME, mirroring design.yaml +
           devops.yaml) -- resolved through the WIRED spine ``resolve_stack``.
  (seam-2) the ``check-slice-at-completeness`` reference in the atdd_pure
           ``lifecycle_events["dispatch.pre"]`` carpaccio stack (the DELIVER-entry
           BACKSTOP, CT-9) -- resolved through the WIRED production flavor parser.

Each slice-03 AT NAMES one of these seams, drives it through the REAL entry
point, and asserts an observable effect (the resolved gate-id sequence).

RED contract (fail-for-right-reason, atdd_pure active-RED -- NOT @skip):
  * AT-10: ``nWave/waves/distill.yaml`` does not exist at HEAD -> the spine
    resolves an EMPTY DISTILL gate-out stack -> a semantic AssertionError naming
    the missing registry file / check-slice-at-completeness row.
  * AT-11: the atdd_pure ``dispatch.pre`` stack at HEAD is
    ``[verify-wave-dispatch, verify-readiness-pre-dispatch, carpaccio-slice-gate]``
    -- it does NOT yet reference ``check-slice-at-completeness`` -> a semantic
    AssertionError naming the missing backstop row. (The CLI itself is ALREADY
    registered in the des dispatcher; slice-03 wires the REFERENCE, not the CLI --
    so the RED is the missing DATA row, never an import/collection error.)

  Every dependency (pytest-bdd, the REAL spine resolver, the REAL flavor parser,
  the SHIPPED repo files) resolves cleanly -- the REDs are deliberate
  missing-wiring signals, not test bugs.
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
    from .domain_types_distill import DispatchLifecycle, WaveBoundary


# The SHIPPED canonical wave-contract registry file (ADR-FLOW-006 D1) for DISTILL.
_WAVES_DIR = REPO_ROOT / "nWave" / "waves"
_DISTILL_REGISTRY_FILE = _WAVES_DIR / "distill.yaml"

# The DISTILL wave whose gate-out stack is migrated to the canonical registry.
_DISTILL_WAVE = "distill"

# The SHIPPED atdd_pure flavor file carrying the DELIVER-entry dispatch.pre stack.
_ATDD_PURE_FLAVOR_FILE = REPO_ROOT / "nWave" / "flavors" / "atdd_pure.yaml"
_ACTIVE_FLAVOR_ID = "atdd_pure"

# The EXISTING completeness CLI gate-id this slice wires into BOTH stacks
# (brief DDD-5: zero new gate logic -- the gate-id is the 1:1 dispatcher name,
# already registered at src/des/cli/__main__.py:74).
_AT_COMPLETENESS_GATE_ID = "check-slice-at-completeness"

# The carpaccio gate-id that MUST remain in dispatch.pre after the backstop is
# added (AT-11 regression pin: the backstop is ADDED, the existing carpaccio gate
# is NOT displaced).
_CARPACCIO_GATE_ID = "carpaccio-slice-gate"


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


def _dispatch_pre_sequence_resolved_by_flavor_parser(
    lifecycle: DispatchLifecycle,
) -> tuple[str, ...]:
    """Resolve the dispatch.pre gate-id sequence through the WIRED flavor parser.

    Drives the REAL production ``flavor_dispatcher._parse_flavor_file`` over the
    SHIPPED ``nWave/flavors/atdd_pure.yaml`` and projects
    ``lifecycle_events[lifecycle]`` -- the SAME artifact + the SAME stdlib-only
    SSOT parser the live ``carpaccio_intercept.evaluate_atdd_pure_dispatch``
    consumes on every DELIVER Agent/Task dispatch. The observable is the ordered
    gate-id sequence the dispatcher would iterate.

    At HEAD the dispatch.pre stack does NOT reference
    ``check-slice-at-completeness`` (the RED for AT-11). An unreadable flavor /
    absent event -> the empty tuple (degrade-LOUD: an empty sequence cannot
    satisfy the membership oracle).
    """
    from des.application import flavor_dispatcher

    try:
        flavor_doc = flavor_dispatcher._parse_flavor_file(_ATDD_PURE_FLAVOR_FILE)
    except (FileNotFoundError, IsADirectoryError, UnicodeDecodeError, OSError):
        return ()
    lifecycle_events = flavor_doc.get("lifecycle_events")
    if not isinstance(lifecycle_events, dict):
        return ()
    composition = lifecycle_events.get(lifecycle.value)
    if not isinstance(composition, list):
        return ()
    return tuple(
        str(row["gate_id"])
        for row in composition
        if isinstance(row, dict) and "gate_id" in row
    )


@dataclass
class DistillCompletenessGateComposition:
    """Drives the DISTILL AT-completeness wiring through its TWO real wired seams.

    AT-10 reads the SHIPPED repo registry (the spine resolution seam). AT-11
    reads the SHIPPED atdd_pure flavor (the dispatch.pre backstop seam). Both
    read shipped artifacts -- no tmp work-tree, no fixture authoring of the
    expected stack (the shipped artifact, or its absence, IS the contract).
    """

    repo_dir: Path
    _resolved_boundary: WaveBoundary | None = field(default=None)
    _resolved_lifecycle: DispatchLifecycle | None = field(default=None)

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

    # ---- AT-11 given/when/then: DELIVER-entry dispatch.pre backstop seam ------

    def given_atdd_pure_flavor_declares_dispatch_pre(self) -> None:
        """Arm the SUT to read the SHIPPED atdd_pure flavor's dispatch.pre stack.

        No fixture authoring -- the SHIPPED flavor file is the artifact the
        production dispatcher reads (Mandate-13). The dispatch.pre stack (or its
        missing backstop row) IS the contract under test.
        """
        # Nothing to set up beyond pointing at the shipped flavor -- the file's
        # dispatch.pre composition is the contract under test.

    def when_dispatcher_resolves_dispatch_pre_stack(
        self, lifecycle: DispatchLifecycle
    ) -> None:
        """Bind WHICH lifecycle event the Then must cross-check (read in Then)."""
        self._resolved_lifecycle = lifecycle

    def then_dispatch_pre_includes_check_slice_at_completeness(
        self, lifecycle: DispatchLifecycle
    ) -> None:
        """The resolved dispatch.pre stack carries the AT-completeness backstop gate.

        Seam-named oracle (Mandate-15 seam-2, CT-9): the DELIVER-entry carpaccio
        stack the production flavor dispatcher resolves must reference
        ``check-slice-at-completeness`` -- so an incomplete slice cannot ENTER
        DELIVER even if the DISTILL gate-out was bypassed (the complementary
        backstop, Alt 2 ADR-NB-002). RED at HEAD: the dispatch.pre stack is
        ``[verify-wave-dispatch, verify-readiness-pre-dispatch,
        carpaccio-slice-gate]`` -- it does NOT yet reference the gate -> semantic
        AssertionError naming the missing backstop row.
        """
        self._assert_lifecycle_matches_when(lifecycle)
        resolved = _dispatch_pre_sequence_resolved_by_flavor_parser(lifecycle)
        assert _AT_COMPLETENESS_GATE_ID in resolved, (
            f"the atdd_pure {lifecycle.value} stack the production flavor "
            f"dispatcher resolves must include the {_AT_COMPLETENESS_GATE_ID!r} "
            "gate (brief CT-9 / DDD-5: the DELIVER-entry BACKSTOP -- an incomplete "
            "slice cannot enter DELIVER even if the DISTILL gate-out was bypassed) "
            f"-- the resolved dispatch.pre sequence {resolved!r} does not carry it "
            f"yet. {self._dispatch_observed()}"
        )

    def then_dispatch_pre_still_includes_carpaccio_gate(
        self, lifecycle: DispatchLifecycle
    ) -> None:
        """The dispatch.pre backstop is ADDED -- the carpaccio gate is NOT displaced.

        Regression pin (AT-11): adding the AT-completeness backstop row must not
        drop the existing ``carpaccio-slice-gate`` row from the dispatch.pre
        stack. This guards against a clobbering edit. At HEAD the carpaccio gate
        is present -> this leg is GREEN-at-HEAD; the SCENARIO is RED only on the
        first leg (the missing backstop row) -- the fail-for-right-reason is the
        missing AT-completeness reference, NOT a missing carpaccio gate.
        """
        self._assert_lifecycle_matches_when(lifecycle)
        resolved = _dispatch_pre_sequence_resolved_by_flavor_parser(lifecycle)
        assert _CARPACCIO_GATE_ID in resolved, (
            f"the atdd_pure {lifecycle.value} stack must STILL include the "
            f"{_CARPACCIO_GATE_ID!r} gate after the AT-completeness backstop is "
            "added (the backstop is ADDED, the existing carpaccio gate is NOT "
            f"displaced) -- the resolved sequence {resolved!r} dropped it. "
            f"{self._dispatch_observed()}"
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

    def _assert_lifecycle_matches_when(self, lifecycle: DispatchLifecycle) -> None:
        assert self._resolved_lifecycle is not None, (
            "the dispatch.pre resolution must run (When) before asserting (Then)"
        )
        assert self._resolved_lifecycle is lifecycle, (
            f"Then lifecycle {lifecycle.value!r} must match the one resolved in "
            f"When ({self._resolved_lifecycle.value!r}) -- scenario wiring drift"
        )

    # ---- diagnostics ---------------------------------------------------------

    def _observed(self) -> str:
        return (
            f"distill_registry_file_exists={_DISTILL_REGISTRY_FILE.is_file()}; "
            f"waves_dir={_WAVES_DIR}; resolved_boundary={self._resolved_boundary!r}"
        )

    def _dispatch_observed(self) -> str:
        return (
            f"flavor_file_exists={_ATDD_PURE_FLAVOR_FILE.is_file()}; "
            f"flavor_id={_ACTIVE_FLAVOR_ID!r}; "
            f"resolved_lifecycle={self._resolved_lifecycle!r}"
        )
