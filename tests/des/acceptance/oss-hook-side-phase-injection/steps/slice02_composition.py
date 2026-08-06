"""Composition root for slice-02 -- DISTILL dispatch marker enforcement +
DELIVER-exit symmetry.

slice-02 of oss-hook-side-phase-injection (the DISTILL-wave hook keystone, D1).

Mandate-13 (driving-port-only) + Pillar 3: every SUT is exercised through a
PRODUCTION hook invoked end-to-end over its JSON stdin protocol as a subprocess
(Layer 3/4 wiring_e2e, the direct mirror of the shipped slice-01
``g-distill-exit-gate`` ATs + the U2 ``g-commit-exit-gate`` ATs):

  * AT-1 / AT-2 drive the real ``handle_pre_tool_use`` PreToolUse hook over its
    Claude Code JSON envelope. The observable surface is the hook's stdout
    decision body (block event name) and its exit code. The G-DISTILL-PRE gate
    validates a ``D_DISTILL`` dispatch's marker set BEFORE it runs.
  * AT-3 drives the real ``handle_subagent_stop`` SubagentStop hook over its
    JSON envelope against a real git repo carrying a complete ``G_COMMIT`` slice
    commit + transcript. The observable surface is the gate verdict, the exit
    code, and the two ledger records the gate emits -- the existing
    ``SliceCommitVerified`` AND the new ``WorkflowPhaseCompletedGCommit``
    DELIVER-exit success terminal (SF ADR-016 symmetry with slice-01's
    DISTILL-exit ``WorkflowPhaseCompletedDistill``).

The composition NEVER imports a hook's gate logic and calls it at the step
boundary; the only entry is the real hook subprocess. The production
``AtCompletionLedger`` reader is used ONLY to read back the observable terminal
the gate emits (the audit SUBSTRATE the hook writes, not the SUT) -- the
adjudicated-legitimate carve-out, exactly as in slice-01.

The only test doubles are the absent ones: there are none. The git repo, the
feature-delta, the transcript JSONL, the ledger JSONL, and the hook subprocess
are all real I/O -- a layer-3/4 ``@real-io`` / ``@wiring_e2e`` surface
(Mandate 9/11: example only, no PBT machinery).

HARD INVARIANT (hook-can't-spawn-agent): both gates only ALLOW / BLOCK / EMIT.
No assertion claims a hook dispatched an agent -- it cannot.
"""

from __future__ import annotations

import json
import subprocess
from dataclasses import dataclass
from pathlib import Path

# The REAL `handle_pre_tool_use` (PreToolUse) + `handle_subagent_stop`
# (SubagentStop) hook handlers, driven IN-PROCESS over their JSON stdin protocol
# (node-C enabler `run_hook_in_process`) — behaviour-identical to the prior
# `python -c "... handle()"` subprocess forks, no fresh interpreter. Both are
# no-argv handlers that read their JSON event from sys.stdin.
from des.adapters.drivers.hooks.pre_tool_use_handler import handle_pre_tool_use
from tests.common.in_process_cli import run_hook_in_process

from .slice02_domain_types import (
    DispatchVerdict,
    DistillDispatchShape,
    FeatureId,
)


_FEATURE_ID = FeatureId("atdd-pure-demo")
_PRE_TOOL_USE_MODULE = "des.adapters.drivers.hooks.pre_tool_use_handler"

# The G_COMMIT slice the DELIVER-exit symmetry record is scoped to (AT-3).
# The DELIVER-exit success terminal slice-02 adds (MAJOR-1): the phase is
# encoded in the event NAME, mirroring slice-01's WorkflowPhaseCompletedDistill.
# ---------------------------------------------------------------------------
# G-DISTILL-PRE -- the PreToolUse marker-enforcement gate (AT-1 / AT-2)
# ---------------------------------------------------------------------------


@dataclass
class DistillDispatchOutcome:
    """The observable result of a G-DISTILL-PRE PreToolUse gate evaluation.

    Universe entries are port-exposed only (Mandate 8): the dispatch verdict
    (allowed/blocked), the block event name, and the hook exit code -- never an
    internal handler struct field.
    """

    verdict: DispatchVerdict
    block_event: str | None
    exit_code: int


class DistillDispatchGateComposition:
    """Production-wired composition root for the G-DISTILL-PRE gate (AT-1/AT-2).

    The driving port is the real ``handle_pre_tool_use`` hook invoked over its
    Claude Code JSON stdin protocol as a subprocess; the observable surface is
    the hook's stdout decision body and exit code.
    """

    def __init__(self, repo: Path) -> None:
        self._repo = repo
        self._feature_id = _FEATURE_ID
        self._shape = DistillDispatchShape.COMPLETE

    def use_dispatch(self, shape: DistillDispatchShape) -> None:
        """The PreToolUse dispatch under test carries the markers for ``shape``."""
        self._shape = shape

    def _dispatch_prompt(self) -> str:
        """Render the ``D_DISTILL`` acceptance-designer dispatch prompt.

        COMPLETE            -- mode + phase + feature-end scope + project-id.
        PROJECT_ID_MISSING  -- the ``DES-PROJECT-ID`` marker is omitted.
        SLICE_SCOPED        -- the scope is a ``slice-N`` value, not feature-end
                               (incoherent for a feature-end phase -- XOR fails).
        """
        scope = (
            "slice-01"
            if self._shape is DistillDispatchShape.SLICE_SCOPED
            else "feature-end"
        )
        lines = [
            "<!-- DES-VALIDATION : required -->",
            "<!-- DES-MODE : atdd_pure -->",
            "<!-- DES-PHASE : D_DISTILL -->",
            f"<!-- DES-SLICE : {scope} -->",
        ]
        if self._shape is not DistillDispatchShape.PROJECT_ID_MISSING:
            lines.append(f"<!-- DES-PROJECT-ID : {self._feature_id} -->")
        lines.append(f"<!-- DES-PROJECT-ROOT : {self._repo} -->")
        return "\n".join(lines) + "\n\nDISTILL acceptance-designer dispatch body.\n"

    def run_pre_tool_use_hook(self) -> DistillDispatchOutcome:
        """Invoke the REAL ``handle_pre_tool_use`` hook over its JSON protocol."""
        hook_input = json.dumps(
            {
                "tool_name": "Agent",
                "tool_input": {
                    "subagent_type": "nw-acceptance-designer",
                    "prompt": self._dispatch_prompt(),
                    "description": "Dispatch acceptance-designer into DISTILL",
                },
            }
        )
        exit_code, stdout, stderr = run_hook_in_process(
            handle_pre_tool_use,
            stdin_text=hook_input,
            cwd=str(Path.cwd()),
        )
        completed = subprocess.CompletedProcess(
            args=[_PRE_TOOL_USE_MODULE],
            returncode=exit_code,
            stdout=stdout,
            stderr=stderr,
        )
        return self._interpret(completed)

    def _interpret(
        self, completed: subprocess.CompletedProcess
    ) -> DistillDispatchOutcome:
        block_event: str | None = None
        verdict = DispatchVerdict.ALLOWED
        for line in completed.stdout.splitlines():
            line = line.strip()
            if not line.startswith("{"):
                continue
            try:
                payload = json.loads(line)
            except json.JSONDecodeError:
                continue
            if payload.get("decision") == "block":
                verdict = DispatchVerdict.BLOCKED
                block_event = payload.get("event")
        return DistillDispatchOutcome(
            verdict=verdict,
            block_event=block_event,
            exit_code=completed.returncode,
        )


# ---------------------------------------------------------------------------
# G-DELIVER-EXIT -- the SubagentStop G_COMMIT symmetry gate (AT-3)
# ---------------------------------------------------------------------------
