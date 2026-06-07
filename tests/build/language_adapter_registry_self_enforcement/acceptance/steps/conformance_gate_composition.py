"""Composition-root service for the live-registry conformance gate (slice-03).

Provenance: feature ``language-adapter-registry-self-enforcement``, slice-03 (DISTILL,
per-slice JIT; DDD-D4a). The LIVE-registry end-to-end vertical: the conformance gate CLI
mode resolve-and-probes the ACTUAL registered ``nwave.lang.adapter`` plugins (C2) and
cross-checks each plugin's realized surface against the registered-capability obligation
set (C1), running as part of the gate surface (C5).

Driving port (Mandate-13 driving-port-only boundary): the gate is reached EXCLUSIVELY
through a composition-root driving surface at ONE of two layers --

  * LAYER 3 SUBPROCESS (scenario 1) -- the REAL CLI
    ``python -m scripts.cli.validate_language_adapter_catalog --check-conformance`` invoked
    as a subprocess over the REAL ``importlib.metadata`` registry. The exit code IS the
    port-exposed observable. This is the live-registry end-to-end witness.
  * LAYER 3 COMPOSITION (scenarios 2+3) -- the gate-runner
    ``scripts.cli.validate_language_adapter_catalog.run_conformance_gate(source)`` invoked
    in-process with an INJECTED discovery source (the unresolvable / clean corpus). The
    gate-runner is the CLI's driving-port core (``main`` dispatches ``--check-conformance``
    straight into it); driving it directly with an injected source is the composition-root
    seam DDD-D6 mandates (the live ``entry_points`` read is a PARAMETER, not a hard-read).

NOT a direct-domain test (Mandate-13): the ATs never import C1 (``registry_conformance``)
or C2 (``discovery``) and call them directly -- they drive ``run_conformance_gate`` (the
gate driving port), which internally consumes C2 + C1. The injected source is plain
``EntryPoint`` data / a frozen realized-map result, not a domain-function invocation.

Three corpora (DDD-D4a, the recall/precision golden-fixture shape generalized to the live
registry):

  * RECALL / GAP (scenario 1) -- the REAL live registry. At HEAD the only registered
    plugin is the inert ``_conformance_fixture`` (realizes 0/9), a GENUINE registered-but-
    unrealized gap -> exit 1. Falsifiable WITHOUT slice-05a (the inert fixture is a real
    gap NOW). GREEN when A_GREEN implements C2 resolve-and-probe + C3 gate-runner.
  * LOUD INDETERMINATE (scenario 2) -- an injected unresolvable ``entry_points`` source.
    The gate's resolve-and-probe really attempts ``.load()`` and really fails -> exit 3
    loud (DDD-D5), never silent green.
  * PRECISION-CLEAN / CONFORMANT (scenario 3) -- a frozen all-realized discovery RESULT
    (every plugin realizes every required capability) -> exit 0. Pins the exit-0 lane
    WITHOUT claiming the LIVE registry is conformant (precision-live-CONFORMANT deferred to
    slice-05a).

Honest tagging (Mandate 9 v2): scenario 1 spawns the real CLI over the real registry ->
@real-io @subprocess; scenario 2 does a real ``.load()`` that genuinely raises ->
@real-io; scenario 3 injects plain-data result -> @in-memory. All example-based, never PBT.

RED scaffold (Mandate-7 / ADR-025): the driven ``run_conformance_gate`` raises
``AssertionError`` (the RED token -- NOT NotImplementedError, NOT ImportError) until
A_GREEN implements it. The subprocess path RED-fails the same way (the CLI mode dispatches
straight into the scaffold). The C2 ``resolve_and_probe_realized_surface`` is also a RED
scaffold; the gate-runner consumes it.
"""

from __future__ import annotations

import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

from scripts.cli.validate_language_adapter_catalog import run_conformance_gate
from tests.build.language_adapter_registry_self_enforcement.acceptance.fixtures.conformance_gate.all_realized_registry_result import (
    clean_realized_by_plugin,
)
from tests.build.language_adapter_registry_self_enforcement.acceptance.fixtures.conformance_gate.unresolvable_registry import (
    unresolvable_entry_points,
)
from tests.build.language_adapter_registry_self_enforcement.acceptance.steps.conformance_gate_domain_types import (
    ConformanceGateLane,
)


_REPO_ROOT = Path(__file__).resolve().parents[5]


@dataclass(frozen=True)
class GateResult:
    """The port-exposed result of a conformance-gate run: the exit code + captured stderr.

    ``exit_code`` -- the gate's process exit code (the exit-code contract observable).
    ``stderr`` -- the gate's stderr text (the loud-message-prefix discriminator within the
                  shared lane-1 gap lane / the lane-3 loud lane).
    """

    exit_code: int
    stderr: str


class ConformanceGateService:
    """Drives the live-registry conformance gate over the three corpora.

    Recall corpus = the REAL live registry (via the real CLI subprocess); loud corpus =
    an injected unresolvable ``entry_points`` source (in-process gate-runner); clean corpus
    = a frozen all-realized discovery result (in-process gate-runner).
    """

    # --- RECALL / GAP (the REAL live registry, via the real CLI subprocess) -----

    def gate_over_live_registry(self) -> GateResult:
        """Run the real CLI ``--check-conformance`` over the real registry (subprocess)."""
        completed = subprocess.run(
            [
                sys.executable,
                "-m",
                "scripts.cli.validate_language_adapter_catalog",
                "--check-conformance",
            ],
            cwd=_REPO_ROOT,
            capture_output=True,
            text=True,
            check=False,
        )
        return GateResult(exit_code=completed.returncode, stderr=completed.stderr)

    # --- LOUD INDETERMINATE (injected unresolvable source, in-process gate-runner) -

    def gate_over_unresolvable_registry(self) -> GateResult:
        """Run the gate-runner over an injected unresolvable ``entry_points`` source.

        The gate-runner really attempts ``.load()`` on the ghost entry point and really
        fails -> exit 3 loud (DDD-D5). The gate-runner is driven directly (Layer 3
        composition) with the injected source as the DDD-D6 parameter.
        """
        exit_code = run_conformance_gate(unresolvable_entry_points())
        return GateResult(exit_code=exit_code, stderr="")

    # --- PRECISION-CLEAN / CONFORMANT (frozen all-realized result, in-process) ---

    def gate_over_clean_registry_result(self) -> GateResult:
        """Run the gate-runner over a frozen all-realized discovery result.

        Every discovered plugin realizes every required capability -> exit 0. Pins the
        exit-0 lane WITHOUT claiming the LIVE registry is conformant (slice-05a deferral).
        """
        exit_code = run_conformance_gate(_resolved_source(clean_realized_by_plugin()))
        return GateResult(exit_code=exit_code, stderr="")

    # --- exit-code -> lane projection -------------------------------------------

    @staticmethod
    def lane_of(result: GateResult) -> ConformanceGateLane:
        """Project the gate result's exit code onto the port-exposed lane enum."""
        return ConformanceGateLane(result.exit_code)


def _resolved_source(realized_by_plugin: dict[str, frozenset[str]]):
    """Wrap a frozen realized-map result as a pre-resolved discovery source.

    The clean corpus is a discovery RESULT (already resolved-and-probed), not raw entry
    points -- so the gate-runner receives it as a pre-resolved source marker the GREEN
    impl recognises (a frozen ``{plugin_id: realized}`` mapping). The composition root owns
    this distinction (DDD-D6); the test supplies plain data, no domain call.
    """
    return realized_by_plugin


def build_service() -> ConformanceGateService:
    """Composition-root entry -- the production object graph for the slice-03 AT."""
    return ConformanceGateService()
