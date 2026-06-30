"""Composition root for slice-02 -- the U2 G_COMMIT SubagentStop exit-gate.

slice-02 of F-DES-ATDD-PURE-HOOK-GATES (U2 / Mikado T-G).

Drives the PRODUCTION SubagentStop hook end-to-end through its real JSON hook
protocol (`handle_subagent_stop` reading stdin, writing a `{"decision":"block"}`
body to stdout). The composition root builds a real git repository with a real
`G_COMMIT` crafter transcript, invokes the hook as a subprocess (`@wiring_e2e`),
and reads back the block decision + the U3 ledger record the intercept emitted.

The only test doubles are the absent ones: there are none. The git repo, the
transcript JSONL, the ledger JSONL, and the hook subprocess are all real I/O --
a layer-5 `@wiring_e2e` walking-skeleton-grade surface (Mandate 9/11: example
only, no PBT machinery).
"""

from __future__ import annotations

import json
import os
import subprocess
from dataclasses import dataclass
from pathlib import Path

from des.adapters.driven.logging.at_completion_ledger import AtCompletionLedger
from des.adapters.drivers.hooks.subagent_stop_handler import handle_subagent_stop
from tests.common.in_process_cli import run_hook_in_process

from .slice02_domain_types import CommitShape, FeatureId, GateOutcome, HandlerFault


_FEATURE_ID = FeatureId("atdd-pure-demo")
# The env var the U2 branch reads to force the M1 try/except fault path.
_FAULT_ENV = "NWAVE_U2_FORCE_HANDLER_FAULT"


@dataclass
class InterceptOutcome:
    """The observable result of a U2 G_COMMIT SubagentStop intercept."""

    outcome: GateOutcome
    decision_event: str | None
    exit_code: int
    ledger_event_for_slice: str | None


def _git(repo: Path, *args: str) -> str:
    completed = subprocess.run(
        ["git", *args], cwd=repo, capture_output=True, text=True, check=True
    )
    return completed.stdout


def _gate_scope_digest(repo: Path) -> str:
    """A fresh contract-gate scope digest for the repo (E2 trailer source)."""
    from des.cli.run_contract_gate import gate_scope_digest

    return gate_scope_digest(repo)


class G_CommitInterceptComposition:
    """Production-wired composition root for the U2 G_COMMIT intercept slice.

    The driving port is the real `handle_subagent_stop` hook invoked over its
    JSON stdin protocol; the observable surface is the hook's stdout decision
    body, its exit code, and the U3 ledger record the intercept emits.
    """

    def __init__(self, repo: Path) -> None:
        self._repo = repo
        self._feature_id = _FEATURE_ID
        self._transcript_path = repo / "agent.jsonl"
        self._slice_id = "slice-02"
        self._fault = HandlerFault.NONE

    # --- repository + commit provisioning -----------------------------------

    def init_repo(self) -> None:
        """Initialise a real git repo with one tracked .feature AT file."""
        _git(self._repo, "init")
        _git(self._repo, "config", "user.email", "t@t.com")
        _git(self._repo, "config", "user.name", "T")
        # A first commit so HEAD~1 always resolves for the completeness gate.
        (self._repo / "README.md").write_text("seed\n", encoding="utf-8")
        _git(self._repo, "add", "README.md")
        _git(self._repo, "commit", "-m", "chore: seed")

    def _write_feature_file(self, slice_id: str, name: str) -> Path:
        feature = self._repo / f"{name}.feature"
        feature.write_text(
            f"@{slice_id}\nFeature: {name}\n  Scenario: s\n    Given x\n",
            encoding="utf-8",
        )
        return feature

    def make_head_commit(self, shape: CommitShape) -> None:
        """Create the HEAD commit the returning G_COMMIT crafter produced."""
        if shape is CommitShape.NO_SLICE_ID:
            (self._repo / "code.py").write_text("x = 1\n", encoding="utf-8")
            _git(self._repo, "add", "code.py")
            _git(self._repo, "commit", "-m", "feat: work with no trailer")
            return

        slice_ids = ["slice-02"]
        if shape is CommitShape.BATCHED:
            slice_ids = ["slice-02", "slice-03"]

        files: list[Path] = []
        if shape is not CommitShape.INCOMPLETE:
            for sid in slice_ids:
                files.append(self._write_feature_file(sid, f"at_{sid}"))
        else:
            # The .feature AT file is authored on disk but kept OUT of the
            # commit -- the RCA Branch-A defect E1 must catch.
            self._write_feature_file("slice-02", "at_slice-02")
            (self._repo / "code.py").write_text("x = 1\n", encoding="utf-8")
            files.append(self._repo / "code.py")

        for path in files:
            _git(self._repo, "add", str(path.relative_to(self._repo)))

        digest = _gate_scope_digest(self._repo)
        trailers = "\n".join(f"Slice-Id: {sid}" for sid in slice_ids)
        message = f"feat: deliver slice work\n\n{trailers}\nGate-Scope: {digest}"
        _git(self._repo, "commit", "-m", message)

    # --- crafter transcript -------------------------------------------------

    def write_g_commit_transcript(self) -> None:
        """Write a transcript whose LAST atdd_pure block is a G_COMMIT return."""
        self._write_transcript(blocks=1)

    def write_two_block_transcript(self) -> None:
        """Write a transcript carrying TWO atdd_pure marker blocks.

        The first block is a stale `A_GREEN_ATS` dispatch; the second (last)
        block is the live `G_COMMIT` return. M6 requires U2 to resolve the
        LAST block -- the probe asserts the second block is the one acted on.
        """
        self._write_transcript(blocks=2)

    def _marker_block(self, phase: str, slice_id: str) -> str:
        return (
            "<!-- DES-VALIDATION : required -->\n"
            "<!-- DES-MODE : atdd_pure -->\n"
            f"<!-- DES-PHASE : {phase} -->\n"
            f"<!-- DES-SLICE : {slice_id} -->\n"
            f"<!-- DES-PROJECT-ID : {self._feature_id} -->\n"
            f"<!-- DES-PROJECT-ROOT : {self._repo} -->\n"
        )

    def _write_transcript(self, *, blocks: int) -> None:
        lines: list[str] = []
        if blocks == 2:
            # Stale earlier dispatch -- a different phase, must NOT be resolved.
            lines.append(
                json.dumps(
                    {
                        "type": "user",
                        "message": {
                            "role": "user",
                            "content": self._marker_block("A_GREEN_ATS", "slice-99"),
                        },
                        "uuid": "stale-block",
                        "timestamp": "2026-05-20T09:00:00Z",
                    }
                )
            )
        # The live G_COMMIT return -- the LAST atdd_pure block.
        lines.append(
            json.dumps(
                {
                    "type": "user",
                    "message": {
                        "role": "user",
                        "content": self._marker_block("G_COMMIT", self._slice_id),
                    },
                    "uuid": "live-block",
                    "timestamp": "2026-05-20T10:00:00Z",
                }
            )
        )
        self._transcript_path.write_text("\n".join(lines) + "\n", encoding="utf-8")

    def inject_handler_fault(self) -> None:
        """Mark the run so the U2 branch raises -- exercises the M1 try/except."""
        self._fault = HandlerFault.RAISES

    # --- driving-port invocation -------------------------------------------

    def run_subagent_stop_hook(self) -> InterceptOutcome:
        """Invoke the REAL `handle_subagent_stop` hook over its JSON protocol."""
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
        env_fault = "1" if self._fault is HandlerFault.RAISES else "0"
        # Faithful in-process analogue of the prior `python -c "... import
        # handle_subagent_stop; sys.exit(handle_subagent_stop())"` fork: drive the
        # REAL no-argv handler over the SAME stdin payload. The handler resolves
        # the work-tree from the JSON `cwd` field, so the process cwd is incidental
        # (kept at Path.cwd(), as the fork ran). The `NWAVE_U2_FORCE_HANDLER_FAULT`
        # env var the U2 branch reads is set around the call and restored in
        # finally (shared-process safe); PYTHONPATH was a subprocess import concern
        # only (a no-op in-process).
        prior_fault = os.environ.get(_FAULT_ENV)
        os.environ[_FAULT_ENV] = env_fault
        try:
            exit_code, stdout, stderr = run_hook_in_process(
                handle_subagent_stop,
                stdin_text=hook_input,
                cwd=str(Path.cwd()),
            )
        finally:
            if prior_fault is None:
                os.environ.pop(_FAULT_ENV, None)
            else:
                os.environ[_FAULT_ENV] = prior_fault
        completed = subprocess.CompletedProcess(
            args=[], returncode=exit_code, stdout=stdout, stderr=stderr
        )
        return self._interpret(completed)

    def _interpret(self, completed: subprocess.CompletedProcess) -> InterceptOutcome:
        decision_event: str | None = None
        outcome = GateOutcome.ALLOWED
        for line in completed.stdout.splitlines():
            line = line.strip()
            if not line.startswith("{"):
                continue
            try:
                payload = json.loads(line)
            except json.JSONDecodeError:
                continue
            if payload.get("decision") == "block":
                outcome = GateOutcome.BLOCKED
                decision_event = payload.get("event")
        return InterceptOutcome(
            outcome=outcome,
            decision_event=decision_event,
            exit_code=completed.returncode,
            ledger_event_for_slice=self._ledger_event_for_slice(),
        )

    def _ledger_event_for_slice(self) -> str | None:
        """The latest gate event the U2 intercept emitted for slice-02."""
        ledger = AtCompletionLedger(self._feature_id, self._repo)
        try:
            records = ledger.read_records()
        except Exception:
            return None
        for record in reversed(records):
            if record.get("slice_id") == self._slice_id and record.get("event") in (
                "SliceCommitVerified",
                "SliceCommitBlocked",
            ):
                return str(record["event"])
        return None
