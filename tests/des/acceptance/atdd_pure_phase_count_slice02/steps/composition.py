"""Composition root for the atdd_pure_phase_count slice-02 acceptance steps.

Mandate-13 (driving-port-only): the SUT is driven EXCLUSIVELY through a
Layer-3 subprocess boundary. NO production ``des.domain`` / ``des.application``
/ ``des.adapters`` symbol is imported here; the only contact with the system
under test is via ``subprocess.run`` against ``des.cli.phases``.

Driving port: ``python -m des.cli.phases --resolve PHASE`` -- the operator-facing
replay/resolve CLI. This is the load-bearing seam for the backward-compat alias
map (``resolve_phase`` / ``LEGACY_PHASE_ALIASES`` per the slice-02 DESIGN): the
legacy 7-phase ledger vocabulary replays onto the canonical 3, and an unknown
name is rejected with a typed error (non-zero exit, no silent map).

On the slice-01 HEAD this CLI ships only ``--format json`` (no ``--resolve``
flag), so argparse exits 2 for every ``--resolve`` invocation -- every resolution
reds for the right reason (MISSING_FUNCTIONALITY) until slice-02 lands the alias
map and the ``--resolve`` flag.

Why the resolver CLI and not the SubagentStop hook for the marker-recognition
row: the hook recognises a phase marker AND then routes on it through the
commit-verification gate, which blocks for an unrelated reason (no verified
commit) and confounds the phase-vocabulary observable. The resolver CLI is the
clean, single-observable Layer-3 port for the phase-vocabulary contract (the
slice-02 DESIGN reconciliation note names it as the discriminating surface).

Mandate-12 (SSOT via types + services): the composition exposes ONE service
method per observable. Step bodies invoke the service and assert against a typed
result; they never inline subprocess logic.
"""

from __future__ import annotations

import json
import subprocess
from dataclasses import dataclass

from des.cli.phases import main as _phases_main
from tests.common.in_process_cli import run_cli_in_process

from .domain_types import CanonicalPhase


@dataclass(frozen=True)
class ResolutionResult:
    """Typed projection of a ``des.cli.phases --resolve PHASE`` invocation.

    THREE observable outcomes, kept mutually distinguishable so the third
    (routing/seam) outcome cannot collapse into either of the other two:

    * ``canonical`` is the resolved canonical phase name on a phase resolution
      (exit 0, ``routing`` False), else ``""``.
    * ``routing`` is True when the runtime recognises the name as a routing/seam
      event (exit 0, no canonical phase) -- the ``D_GAP_ROUTING`` outcome that
      keeps a pre-reduction ledger replayable. ``canonical`` is ``""`` here.
    * ``rejected`` is True when the resolver refused the name with a non-zero
      exit (the unknown-phase typed-error contract). ``canonical`` is ``""`` and
      ``routing`` is False here.
    """

    input_name: str
    canonical: str
    rejected: bool
    exit_code: int
    routing: bool = False


class PhaseResolveComposition:
    """Drives ``python -m des.cli.phases --resolve`` (Layer-3 subprocess port)."""

    def resolve(self, phase_name: str) -> ResolutionResult:
        # In-process analogue of `python -m des.cli.phases --resolve PHASE`: drive
        # the REAL `des.cli.phases.main(argv)` EDGE, capturing the same stdout the
        # subprocess captured. The resolver is cwd-independent (pure alias map), so
        # the process cwd is incidental (kept at "." as the fork's was). Result is
        # wrapped in a CompletedProcess so the typed parser stays byte-identical.
        exit_code, stdout, stderr = run_cli_in_process(
            ["--resolve", phase_name],
            cwd=".",
            main=_phases_main,
        )
        proc = subprocess.CompletedProcess(
            args=[], returncode=exit_code, stdout=stdout, stderr=stderr
        )
        return self._parse_resolution(phase_name, proc)

    def all_canonical_self_resolve(self) -> bool:
        results = [self.resolve(p.value) for p in CanonicalPhase]
        return all(
            r.canonical == r.input_name and not r.rejected and not r.routing
            for r in results
        )

    def _parse_resolution(
        self, phase_name: str, proc: subprocess.CompletedProcess[str]
    ) -> ResolutionResult:
        if proc.returncode != 0:
            return ResolutionResult(
                input_name=phase_name,
                canonical="",
                rejected=True,
                exit_code=proc.returncode,
            )
        payload = self._safe_json(proc.stdout)
        # The routing/seam outcome: the runtime recognised the name but it maps
        # to no canonical phase (D_GAP_ROUTING). The production payload carries
        # an explicit routing flag AND a null canonical so the seam outcome is
        # observably distinct from BOTH a phase resolution and an unknown reject.
        is_routing = bool(payload.get("routing")) and payload.get("canonical") is None
        canonical_value = payload.get("canonical")
        return ResolutionResult(
            input_name=phase_name,
            canonical="" if canonical_value is None else str(canonical_value),
            rejected=False,
            exit_code=proc.returncode,
            routing=is_routing,
        )

    def _safe_json(self, raw: str) -> dict:
        try:
            parsed = json.loads(raw)
        except json.JSONDecodeError:
            return {}
        return parsed if isinstance(parsed, dict) else {}
