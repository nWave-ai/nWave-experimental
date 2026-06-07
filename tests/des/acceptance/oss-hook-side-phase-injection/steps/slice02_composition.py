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
import sys
from dataclasses import dataclass
from pathlib import Path

from des.adapters.driven.logging.at_completion_ledger import AtCompletionLedger

from .slice02_domain_types import (
    DispatchVerdict,
    DistillDispatchShape,
    FeatureId,
    GCommitOutcome,
)


_FEATURE_ID = FeatureId("atdd-pure-demo")
_SUBAGENT_STOP_MODULE = "des.adapters.drivers.hooks.subagent_stop_handler"
_PRE_TOOL_USE_MODULE = "des.adapters.drivers.hooks.pre_tool_use_handler"

# The G_COMMIT slice the DELIVER-exit symmetry record is scoped to (AT-3).
_GCOMMIT_SLICE = "slice-02"

# The DELIVER-exit success terminal slice-02 adds (MAJOR-1): the phase is
# encoded in the event NAME, mirroring slice-01's WorkflowPhaseCompletedDistill.
_PHASE_COMPLETED_GCOMMIT = "WorkflowPhaseCompletedGCommit"


def _git(repo: Path, *args: str) -> str:
    completed = subprocess.run(
        ["git", *args], cwd=repo, capture_output=True, text=True, check=True
    )
    return completed.stdout


def _subprocess_env() -> dict[str, str]:
    import os

    env = dict(os.environ)
    env["PYTHONPATH"] = str(Path("src").resolve())
    return env


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
        runner = (
            "import sys; "
            f"sys.path.insert(0, {str(Path('src').resolve())!r}); "
            f"from {_PRE_TOOL_USE_MODULE} import handle_pre_tool_use; "
            "sys.exit(handle_pre_tool_use())"
        )
        completed = subprocess.run(
            [sys.executable, "-c", runner],
            input=hook_input,
            capture_output=True,
            text=True,
            cwd=str(Path.cwd()),
            env=_subprocess_env(),
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


@dataclass
class GCommitExitOutcome:
    """The observable result of a G-DELIVER-EXIT SubagentStop gate evaluation.

    Universe entries are port-exposed only (Mandate 8): the gate verdict, the
    hook exit code, and the two ledger terminals read back -- the existing
    ``SliceCommitVerified`` and the new symmetric ``WorkflowPhaseCompletedGCommit``
    record (with its ``slice_id``) -- never an internal handler struct field.
    """

    outcome: GCommitOutcome
    exit_code: int
    slice_commit_verified_emitted: bool
    phase_completed_g_commit_emitted: bool
    phase_completed_g_commit_slice_id: str | None


def _gate_scope_digest(repo: Path) -> str:
    """A fresh contract-gate scope digest for the repo (E2 trailer source)."""
    from des.cli.run_contract_gate import gate_scope_digest

    return gate_scope_digest(repo)


class GCommitExitGateComposition:
    """Production-wired composition root for the G-DELIVER-EXIT symmetry (AT-3).

    The driving port is the real ``handle_subagent_stop`` hook invoked over its
    JSON stdin protocol against a real git repo carrying a complete ``G_COMMIT``
    slice commit; the observable surface is the gate verdict, the exit code, and
    the two ledger records the gate emits.
    """

    def __init__(self, repo: Path) -> None:
        self._repo = repo
        self._feature_id = _FEATURE_ID
        self._slice_id = _GCOMMIT_SLICE
        self._transcript_path = repo / "agent.jsonl"

    # --- repository + commit provisioning -----------------------------------

    def init_repo(self) -> None:
        """Initialise a real git repo with a seed commit so HEAD~1 resolves."""
        _git(self._repo, "init")
        _git(self._repo, "config", "user.email", "t@t.com")
        _git(self._repo, "config", "user.name", "T")
        (self._repo / "README.md").write_text("seed\n", encoding="utf-8")
        _git(self._repo, "add", "README.md")
        _git(self._repo, "commit", "-m", "chore: seed")

    def make_complete_slice_commit(self) -> None:
        """Create the HEAD commit a returning G_COMMIT crafter produced.

        A complete slice commit: the ``.feature`` AT file is committed, the
        message carries the ``Slice-Id`` trailer and a fresh ``Gate-Scope``
        digest -- so the completeness gate (E1) and the contract gate (E2) both
        pass and the gate reaches its success path.
        """
        feature = self._repo / f"at_{self._slice_id}.feature"
        feature.write_text(
            f"@{self._slice_id}\nFeature: at\n  Scenario: s\n    Given x\n",
            encoding="utf-8",
        )
        _git(self._repo, "add", str(feature.relative_to(self._repo)))
        digest = _gate_scope_digest(self._repo)
        message = (
            "feat: deliver slice work\n\n"
            f"Slice-Id: {self._slice_id}\nGate-Scope: {digest}"
        )
        _git(self._repo, "commit", "-m", message)

    # --- crafter transcript -------------------------------------------------

    def write_g_commit_return_transcript(self) -> None:
        """Write a transcript whose LAST atdd_pure block is a ``G_COMMIT`` return."""
        block = (
            "<!-- DES-VALIDATION : required -->\n"
            "<!-- DES-MODE : atdd_pure -->\n"
            "<!-- DES-PHASE : G_COMMIT -->\n"
            f"<!-- DES-SLICE : {self._slice_id} -->\n"
            f"<!-- DES-PROJECT-ID : {self._feature_id} -->\n"
            f"<!-- DES-PROJECT-ROOT : {self._repo} -->\n"
        )
        line = json.dumps(
            {
                "type": "user",
                "message": {"role": "user", "content": block},
                "uuid": "g-commit-return",
                "timestamp": "2026-05-29T11:00:00Z",
            }
        )
        self._transcript_path.write_text(line + "\n", encoding="utf-8")

    # --- driving-port invocation --------------------------------------------

    def run_subagent_stop_hook(self) -> GCommitExitOutcome:
        """Invoke the REAL ``handle_subagent_stop`` hook over its JSON protocol."""
        hook_input = json.dumps(
            {
                "session_id": "slice-02-session",
                "hook_event_name": "SubagentStop",
                "agent_id": "crafter-1",
                "agent_type": "software-crafter",
                "agent_transcript_path": str(self._transcript_path),
                "stop_hook_active": False,
                "cwd": str(self._repo),
                "transcript_path": "/tmp/session.jsonl",
                "permission_mode": "default",
            }
        )
        runner = (
            "import sys; "
            f"sys.path.insert(0, {str(Path('src').resolve())!r}); "
            f"from {_SUBAGENT_STOP_MODULE} import handle_subagent_stop; "
            "sys.exit(handle_subagent_stop())"
        )
        completed = subprocess.run(
            [sys.executable, "-c", runner],
            input=hook_input,
            capture_output=True,
            text=True,
            cwd=str(Path.cwd()),
            env=_subprocess_env(),
        )
        return self._interpret(completed)

    def _interpret(self, completed: subprocess.CompletedProcess) -> GCommitExitOutcome:
        blocked = self._blocked(completed)
        verified, phase_record = self._read_ledger_terminals()
        return GCommitExitOutcome(
            outcome=GCommitOutcome.BLOCKED if blocked else GCommitOutcome.VERIFIED,
            exit_code=completed.returncode,
            slice_commit_verified_emitted=verified,
            phase_completed_g_commit_emitted=phase_record is not None,
            phase_completed_g_commit_slice_id=(
                str(phase_record["slice_id"]) if phase_record is not None else None
            ),
        )

    @staticmethod
    def _blocked(completed: subprocess.CompletedProcess) -> bool:
        for line in completed.stdout.splitlines():
            line = line.strip()
            if not line.startswith("{"):
                continue
            try:
                payload = json.loads(line)
            except json.JSONDecodeError:
                continue
            if payload.get("decision") == "block":
                return True
        return False

    def _read_ledger_terminals(self) -> tuple[bool, dict | None]:
        """Read back the two DELIVER-exit terminals for the slice (Mandate 8).

        Returns ``(slice_commit_verified_present, phase_completed_g_commit_record)``
        read through the production ledger reader under the M7 integrity
        contract. A corrupt ledger raises here; the success path means both
        terminals are present.
        """
        ledger = AtCompletionLedger(self._feature_id, self._repo)
        try:
            verified = self._slice_id in ledger.verified_slices()
        except Exception:
            verified = False
        phase_record: dict | None = None
        try:
            records = ledger.read_records(event_type=_PHASE_COMPLETED_GCOMMIT)
        except Exception:
            records = []
        for record in records:
            if record.get("slice_id") == self._slice_id:
                phase_record = record
        return verified, phase_record


__all__ = [
    "DistillDispatchGateComposition",
    "DistillDispatchOutcome",
    "GCommitExitGateComposition",
    "GCommitExitOutcome",
]
