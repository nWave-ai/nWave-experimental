"""Composition root for the slice-04 wiring ATs (AT-A1-now / CT-8 / CT-9).

Mandate-13 driving-port-only. slice-04 witnesses gate-G WIRED across the shipped
surfaces through REAL wired seams (no fixture authoring of the expected stack --
the shipped artifact, or its absence, IS the contract):

  * Layer 3 subprocess (CT-8) -- the REAL ``des gate-design-at-coherence`` dispatch
    (``python -m des.cli.__main__ gate-design-at-coherence ...``). The observable is
    whether the production argparse dispatcher RECOGNIZES the subcommand (routes it
    to ``des.cli.gate_g:main``) or REJECTS it as an unknown choice. A recognized
    subcommand witnesses the ``_REGISTRY`` SubcommandRow is shipped.
  * Layer 3 composition (CT-9) -- the REAL spine
    ``wave_gate_stack_dispatch.resolve_stack("distill", "gate-out")`` reading the
    SHIPPED canonical registry ``nWave/waves/distill.yaml`` (the SOLE gate-stack
    source, ADR-FLOW-006 D6 -- the SAME spine entry the live SubagentStop gate-out
    caller uses). The observable is the ordered gate-id sequence the resolution
    returns: gate-G is LIVE-WIRED only if ``gate-design-at-coherence`` appears in it.
  * Layer 3 composition (catalog parity) -- the shipped ``nWave/gates/_catalog.yaml``
    mirror entry; the membership is DATA the SUT ships (the CI arch test enforces
    ``_REGISTRY`` <-> ``_catalog.yaml`` parity, so the catalog row is part of the
    wiring contract).

GROUND-TRUTH RECONCILIATION (the feature-delta text is STALE on TWO points; the
prior scaffold inherited the staleness -- corrected here):

  1. The feature-delta DDD-5 / AT-A1 say "wire into the ``atdd_pure.yaml``
     ``wave_gate_stacks.distill.gate-out`` (flavor)" stack. That wording PREDATES
     f-wave slice-06's registry MOVE. ``resolve_stack`` reads ONLY the canonical
     registry ``nWave/waves/<wave>.yaml`` as the SOLE gate-stack source
     (ADR-FLOW-006 D6); the flavor-private ``distill`` co-tenant block in
     atdd_pure.yaml (owned by f-coherence-and-attestation) is DORMANT -- the spine
     never resolves it. A gate placed ONLY in the dormant flavor block would be
     authored-but-unwired-LIVE. So CT-9 targets the REGISTRY HOME
     ``nWave/waves/distill.yaml`` resolved through the WIRED spine
     ``resolve_stack`` (mirroring the sibling f-design-devops-review-gate slice-03
     witness), NOT the flavor block. (Verified live at HEAD:
     ``resolve_stack("distill","gate-out") == ["check-slice-at-completeness"]`` --
     gate-G ABSENT, the active-RED for CT-9.)
  2. The live subcommand at HEAD is ``des gate-g``; the design (DDD-5 / DDD-NAME)
     pins the DESCRIPTIVE id ``des gate-design-at-coherence`` (gate-G is a GENERAL
     coherence gate after slice-03, not a feature-specific probe). slice-04 RENAMES
     ``gate-g`` -> ``gate-design-at-coherence`` in ``_REGISTRY`` + ``_catalog.yaml``
     + the gate-stack row (same module ``des.cli.gate_g``). At HEAD
     ``gate-design-at-coherence`` is an INVALID dispatcher choice (verified live) --
     the active-RED for CT-8.

DON'T-BREAK-SPINE (CT-9 degrade): wiring gate-G onto the distill gate-out means it
fires on EVERY DISTILL return. gate-G requires a manifest or a prose
``[REF] Code-Design`` block; a feature with NEITHER -> gate-G NOT_APPLICABLE
(existing ``_not_applicable``). The wiring MUST be non-blocking for the
neither-contract path so the dogfood spine is not broken. This composition drives
the REAL ``des gate-design-at-coherence`` over a neither-contract feature-root and
observes the §17 verdict is NOT_APPLICABLE (a NA never vetoes -- §22.0).

active-RED at HEAD: ``gate-design-at-coherence`` is absent from ``_REGISTRY``,
``_catalog.yaml``, and the ``nWave/waves/distill.yaml`` gate-out stack; the ``des``
dispatcher rejects the unknown subcommand. Each Then reads the absence as an
observable and fires a NAMED semantic ``AssertionError`` -- never a collection /
import error.

DESIGN-CONTRACT ASSUMPTIONS (the SEAM, never a line number):
  A4 (subcommand id): the wired id is ``gate-design-at-coherence`` (DDD-5),
     ``module: des.cli.gate_g``, ``entry_function: main``.
  A5 (registry-resolved gate-stack): the canonical registry ``nWave/waves/distill.yaml``
     ``gate_stack.gate-out`` carries a ``gate_id: gate-design-at-coherence`` row;
     ``resolve_stack("distill","gate-out")`` returns it LIVE (the SOLE resolved
     surface, ADR-FLOW-006 D6). ``on_failure: block`` on the row -- but a NA verdict
     never vetoes (the §22.0 / don't-break-spine guarantee).
  A6 (dispatch): ``python -m des.cli.__main__ gate-design-at-coherence ...`` is a
     real subcommand (exit code / argparse rejection distinguishes a real run from
     the dispatcher's unknown-subcommand rejection).
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path

import yaml

from tests.common.in_process_cli import run_cli_in_process

from .domain_types import (
    GATE_SUBCOMMAND_ID,
    LOCKED_GATE_VERDICTS,
    GateVerdict,
    WiringSurface,
)


_REPO_ROOT = Path(__file__).resolve().parents[5]
_REGISTRY_PATH = _REPO_ROOT / "src" / "des" / "cli" / "__main__.py"
_CATALOG_PATH = _REPO_ROOT / "nWave" / "gates" / "_catalog.yaml"

# The DISTILL wave + boundary whose REGISTRY-resolved gate-out stack must carry
# gate-G LIVE (ADR-FLOW-006 D6 -- the registry is the SOLE gate-stack source).
_DISTILL_WAVE = "distill"
_GATE_OUT_BOUNDARY = "gate-out"


@dataclass
class WiringComposition:
    """Witnesses gate-G's wiring across the shipped surfaces through REAL seams.

    CT-8: the registry SubcommandRow (witnessed via the REAL dispatcher recognition)
    + the catalog mirror. CT-9: the LIVE registry-resolved distill gate-out stack
    carries gate-G (witnessed via the REAL ``resolve_stack`` spine entry). The
    don't-break-spine leg drives the REAL subcommand over a neither-contract
    feature-root and observes NOT_APPLICABLE (a NA never vetoes the spine).
    """

    _surface: WiringSurface | None = field(default=None)
    _present: bool | None = field(default=None)
    _dispatch_recognized: bool | None = field(default=None)
    _na_verdict: str | None = field(default=None)
    _na_seam_absent: bool = field(default=False)

    # =====================================================================
    # Given -- name the wiring surface under witness
    # =====================================================================

    def given_wiring_surface(self, surface: WiringSurface) -> None:
        """Arm which shipped wiring surface this scenario witnesses."""
        self._surface = surface

    def given_a_feature_with_no_design_contract(self) -> None:
        """Arm the don't-break-spine case: a feature with NEITHER manifest NOR prose."""
        # No state to set beyond marking the intent -- the neither-contract
        # feature-root is written in the When (it needs tmp_path).

    # =====================================================================
    # When -- read the shipped wiring artifact / drive the REAL subcommand
    # =====================================================================

    def when_the_wiring_surface_is_inspected(self) -> None:
        """Read the membership of ``gate-design-at-coherence`` in the armed surface.

        REGISTRY -> the REAL dispatcher recognizes the subcommand (CT-8). CATALOG ->
        the shipped catalog mirror carries the gate_id. GATE_STACK -> the LIVE
        spine ``resolve_stack`` carries gate-G in the distill gate-out sequence
        (CT-9, the registry-resolved surface, NOT the dormant flavor block).
        """
        assert self._surface is not None, (
            "a wiring scenario must arm an explicit WiringSurface "
            "(REGISTRY / CATALOG / GATE_STACK)."
        )
        if self._surface is WiringSurface.REGISTRY:
            self._dispatch_recognized = self._dispatcher_recognizes_subcommand()
            self._present = self._dispatch_recognized
        elif self._surface is WiringSurface.CATALOG:
            self._present = self._catalog_has_gate()
        else:  # GATE_STACK -- the LIVE registry-resolved distill gate-out
            self._present = self._live_gate_out_stack_has_gate()

    def when_the_subcommand_fires_on_a_feature_with_no_design_contract(
        self, tmp_path: Path
    ) -> None:
        """Drive the REAL ``des gate-design-at-coherence`` over a neither-contract root.

        Writes a feature-root with NEITHER a ``code-design.manifest.yaml`` NOR a
        prose ``[REF] Code-Design`` block, then dispatches the REAL subcommand and
        captures the §17 verdict from stdout. The don't-break-spine observable: a
        neither-contract feature must yield NOT_APPLICABLE so the gate-out wiring
        never blocks a real DISTILL return that ships no design contract.
        """
        feature_root = self._write_neither_contract_root(tmp_path)
        self._na_verdict = self._dispatch_and_read_verdict(feature_root)

    # =====================================================================
    # Then -- observable readers
    # =====================================================================

    def then_gate_is_present_in_surface(self) -> None:
        """``gate-design-at-coherence`` is a member of the armed wiring surface."""
        assert self._present, (
            f"gate-G must be WIRED into the {self._surface.value!r} surface "
            f"({GATE_SUBCOMMAND_ID!r} must appear in it). At HEAD it is ABSENT "
            f"(active-RED; DELIVER slice-04 RENAMES gate-g -> gate-design-at-coherence "
            f"in _REGISTRY + _catalog.yaml + the nWave/waves/distill.yaml gate-out "
            f"stack). {self._observed()}"
        )

    def then_the_subcommand_is_recognized(self) -> None:
        """The ``des`` dispatcher recognizes ``gate-design-at-coherence`` (CT-8)."""
        assert self._dispatch_recognized, (
            f"`des {GATE_SUBCOMMAND_ID}` must be a recognized subcommand (registered "
            f"in _REGISTRY -> the dispatcher routes it to des.cli.gate_g:main) -- the "
            f"dispatcher rejected it as an unknown choice at HEAD (active-RED; the "
            f"live subcommand is still `des gate-g`, DELIVER slice-04 renames the "
            f"SubcommandRow). {self._observed()}"
        )

    def then_catalog_mirror_carries_gate(self) -> None:
        """The shipped catalog mirror carries ``gate-design-at-coherence`` (CT-8).

        Independent of the armed REGISTRY surface: the CI arch test enforces
        ``_REGISTRY`` <-> ``_catalog.yaml`` 1:1 parity, so the catalog mirror is part
        of the wiring contract. RED at HEAD: the catalog has a ``gate-g`` entry, not
        ``gate-design-at-coherence`` (slice-04 renames it).
        """
        assert self._catalog_has_gate(), (
            f"the gate catalog ``nWave/gates/_catalog.yaml`` must mirror the "
            f"{GATE_SUBCOMMAND_ID!r} gate (1:1 with the _REGISTRY SubcommandRow -- "
            f"the CI arch test enforces parity). At HEAD the catalog carries `gate-g`, "
            f"not the renamed id (active-RED). {self._observed()}"
        )

    def then_gate_is_live_resolved_in_distill_gate_out(self) -> None:
        """gate-G is LIVE-resolved in the distill gate-out stack (CT-9).

        Seam-named oracle (Mandate-15): the gate-out stack the SPINE resolves
        through ``resolve_stack("distill","gate-out")`` -- the SOLE gate-stack
        source (ADR-FLOW-006 D6), the SAME spine entry the live SubagentStop caller
        uses -- must include ``gate-design-at-coherence``. This is the registry
        HOME, NOT the dormant flavor block (which resolve_stack never reads). RED at
        HEAD: the live stack is ``[check-slice-at-completeness]`` -- gate-G absent.
        """
        assert self._present, (
            f"gate-G must be LIVE-WIRED into the DISTILL gate-out stack the spine "
            f"resolves: `resolve_stack({_DISTILL_WAVE!r},{_GATE_OUT_BOUNDARY!r})` "
            f"must include {GATE_SUBCOMMAND_ID!r} (ADR-FLOW-006 D6 -- the canonical "
            f"registry nWave/waves/distill.yaml is the SOLE gate-stack source; a gate "
            f"placed only in the DORMANT atdd_pure flavor block would never fire "
            f"LIVE). At HEAD the resolved stack is [check-slice-at-completeness] -- "
            f"gate-G ABSENT (active-RED). {self._observed()}"
        )

    def then_the_verdict_is_not_applicable_and_does_not_block(self) -> None:
        """A neither-contract feature yields NOT_APPLICABLE -- the spine is not broken.

        Don't-break-spine guarantee (CT-9 / §22.0): gate-G fires on EVERY DISTILL
        return once wired; a feature shipping NEITHER a manifest NOR prose must
        degrade to NOT_APPLICABLE (a NA never vetoes), so a real DISTILL return with
        no design contract is not blocked. RED at HEAD: the subcommand is
        unrecognized -> no verdict is produced.
        """
        assert not self._na_seam_absent and self._na_verdict is not None, (
            f"the REAL `des {GATE_SUBCOMMAND_ID}` subcommand must run over a "
            f"neither-contract feature and emit a §17 verdict on stdout -- the "
            f"subcommand was UNRECOGNIZED at HEAD (active-RED; DELIVER wires + renames "
            f"the SubcommandRow). {self._observed()}"
        )
        assert self._na_verdict in LOCKED_GATE_VERDICTS, (
            f"gate-G must emit one of the §17 LOCKED FIVE verdicts -- got "
            f"{self._na_verdict!r}. {self._observed()}"
        )
        assert self._na_verdict == GateVerdict.NOT_APPLICABLE.value, (
            f"a feature shipping NEITHER a manifest NOR a prose `[REF] Code-Design` "
            f"block must yield {GateVerdict.NOT_APPLICABLE.value!r} (the existing "
            f"_not_applicable path) so the distill gate-out wiring NEVER blocks a "
            f"real DISTILL return with no design contract (don't-break-spine, §22.0 "
            f"-- a NA never vetoes) -- got {self._na_verdict!r}. {self._observed()}"
        )

    # =====================================================================
    # wiring-artifact readers (the membership data the SUT ships)
    # =====================================================================

    @staticmethod
    def _dispatcher_recognizes_subcommand() -> bool:
        """Drive the REAL ``des`` dispatcher; True iff the subcommand is recognized.

        argparse rejects an unregistered subcommand with
        "argument subcommand: invalid choice: 'gate-design-at-coherence'". A
        recognized subcommand routes to des.cli.gate_g:main (any exit), never the
        invalid-choice rejection. The GATE_SUBCOMMAND_ID appearing inside the
        argparse choices-list ("choose from ...") is NOT recognition -- only the
        ABSENCE of the invalid-choice rejection naming it is.
        """
        _exit, stdout, stderr = run_cli_in_process(
            [GATE_SUBCOMMAND_ID, "--help"],
            cwd=str(_REPO_ROOT),
        )
        blob = f"{stdout}\n{stderr}".lower()
        rejected = "invalid choice" in blob and GATE_SUBCOMMAND_ID in blob
        return not rejected

    @staticmethod
    def _catalog_has_gate() -> bool:
        document = _load_yaml(_CATALOG_PATH)
        gates = document.get("gates", []) if isinstance(document, dict) else []
        return any(
            isinstance(g, dict) and g.get("gate_id") == GATE_SUBCOMMAND_ID
            for g in gates
        )

    @staticmethod
    def _live_gate_out_stack_has_gate() -> bool:
        """True iff the LIVE spine-resolved distill gate-out stack carries gate-G.

        Drives the REAL ``wave_gate_stack_dispatch.resolve_stack`` -- the SOLE
        gate-stack source the spine reads (ADR-FLOW-006 D6). NOT the dormant
        atdd_pure flavor block.
        """
        from des.application import wave_gate_stack_dispatch

        stack = wave_gate_stack_dispatch.resolve_stack(
            _DISTILL_WAVE, _GATE_OUT_BOUNDARY
        )
        return any(
            isinstance(row, dict) and row.get("gate_id") == GATE_SUBCOMMAND_ID
            for row in stack
        )

    def _dispatch_and_read_verdict(self, feature_root: Path) -> str | None:
        """Dispatch the REAL subcommand over a feature-root; read the §17 verdict.

        Returns the verdict token from the subcommand's stdout JSON line, or None
        (and sets ``_na_seam_absent``) when the dispatcher rejects the subcommand as
        unknown (the HEAD active-RED).
        """
        at_module = feature_root / "tests" / "acceptance"
        design = feature_root / "feature-delta.md"
        _exit, stdout, stderr = run_cli_in_process(
            [
                GATE_SUBCOMMAND_ID,
                "--design-contract",
                str(design),
                "--at-module",
                str(at_module),
            ],
            cwd=str(_REPO_ROOT),
        )
        blob = f"{stdout}\n{stderr}".lower()
        if "invalid choice" in blob and GATE_SUBCOMMAND_ID in blob:
            self._na_seam_absent = True
            return None
        return _verdict_from_stdout(stdout)

    @staticmethod
    def _write_neither_contract_root(tmp_path: Path) -> Path:
        """Write a feature-root with NEITHER a manifest NOR a prose contract.

        The design side is a feature-delta with no `[REF] Code-Design` block and no
        manifest beside it -> gate-G must return NOT_APPLICABLE (the neither-contract
        path), the don't-break-spine guarantee.
        """
        root = tmp_path / "feature_no_contract"
        (root / "tests" / "acceptance").mkdir(parents=True, exist_ok=True)
        (root / "feature-delta.md").write_text(
            "# feature-delta with no Code-Design contract\n", encoding="utf-8"
        )
        (root / "tests" / "acceptance" / "any.feature").write_text(
            "Feature: anything\n  Scenario: a\n    Given x\n", encoding="utf-8"
        )
        return root

    def _observed(self) -> str:
        return (
            f"surface={self._surface!r}; present={self._present!r}; "
            f"dispatch_recognized={self._dispatch_recognized!r}; "
            f"na_verdict={self._na_verdict!r}; na_seam_absent={self._na_seam_absent!r}"
        )


def _verdict_from_stdout(stdout: str) -> str | None:
    """Parse the §17 verdict token from the subcommand's stdout JSON line."""
    for line in reversed(stdout.splitlines()):
        line = line.strip()
        if not line.startswith("{"):
            continue
        try:
            payload = json.loads(line)
        except json.JSONDecodeError:
            continue
        verdict = payload.get("verdict")
        if isinstance(verdict, str):
            return verdict
    return None


def _read(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8")
    except (FileNotFoundError, UnicodeDecodeError, OSError):
        return ""


def _load_yaml(path: Path) -> dict:
    try:
        loaded = yaml.safe_load(_read(path))
    except yaml.YAMLError:
        return {}
    return loaded if isinstance(loaded, dict) else {}
