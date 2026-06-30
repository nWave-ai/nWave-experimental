"""Composition root for the atdd_pure 3-phase-count reduction ATs.

Mandate-13 (Driving-Port-Only Boundary): the SUT — the atdd_pure runtime phase
model (`ATDDPurePhase` + `LEGAL_TRANSITIONS`) — is exercised EXCLUSIVELY through
a real operator-facing driving port: the phase-report CLI
`python -m des.cli.phases --format json` (Layer-3 subprocess). NO direct domain
import of `ATDDPurePhase` (that is the SUT). The CLI's JSON output is derived
from the production enum + transition matrix, so it cannot drift from what the
spine runs.

This module exposes ONE composition service method, `report_phase_model`, that
runs the real CLI subprocess and returns the parsed report. Step bodies invoke
it and assert; they hold no recognition/derivation logic.
"""

from __future__ import annotations

import json
from dataclasses import dataclass

from des.cli.phases import main as _phases_main
from tests.common.in_process_cli import run_cli_in_process


@dataclass(frozen=True)
class PhaseReport:
    """The parsed phase-model report — port-exposed observable surface."""

    phases: tuple[str, ...]
    transitions: tuple[tuple[str, str], ...]
    count: int
    exit_code: int

    def has_transition(self, source: str, target: str) -> bool:
        return (source, target) in self.transitions

    def has_any_transition_from(self, source: str) -> bool:
        return any(s == source for s, _ in self.transitions)


@dataclass(frozen=True)
class PhaseModelComposition:
    """Driving-port wrapper over the production phase-report CLI."""

    def report_phase_model(self) -> PhaseReport:
        """Run the real `des.cli.phases --format json` EDGE in-process.

        In-process analogue of `python -m des.cli.phases --format json`: drives
        the production `des.cli.phases.main(argv)` EDGE directly (module-direct,
        NOT a dispatcher subcommand — preserving the catalog/registry parity the
        subprocess form honoured). Returns the parsed `PhaseReport` (phases +
        transitions + count + exit code). On a non-zero exit or unparseable
        stdout (e.g. module absent on master, the RED-for-right-reason path),
        returns an empty report carrying the exit code so the assertion fails
        against the missing/wrong contract rather than crashing the step.
        """
        exit_code, stdout, _stderr = run_cli_in_process(
            ["--format", "json"],
            cwd=".",
            main=_phases_main,
        )
        return _parse_report(stdout, exit_code)


def _parse_report(stdout: str, returncode: int) -> PhaseReport:
    """Parse the CLI's JSON stdout into a typed `PhaseReport`.

    Tolerates the master/RED state (module absent → non-zero exit, empty or
    non-JSON stdout) by returning an empty report with the captured exit code.
    The freshness-autoskip diagnostic the runtime emits on a dev checkout goes
    to stderr, so stdout is the clean JSON channel.
    """
    try:
        payload = json.loads(stdout)
    except (json.JSONDecodeError, ValueError):
        return PhaseReport(phases=(), transitions=(), count=-1, exit_code=returncode)
    phases = tuple(payload.get("phases", []))
    transitions = tuple(tuple(t) for t in payload.get("transitions", []))
    count = payload.get("count", -1)
    return PhaseReport(
        phases=phases,
        transitions=transitions,
        count=count,
        exit_code=returncode,
    )
