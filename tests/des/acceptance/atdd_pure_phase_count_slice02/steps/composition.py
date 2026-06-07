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
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path

from .domain_types import CanonicalPhase, CommitStepWord


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
        proc = subprocess.run(
            [sys.executable, "-m", "des.cli.phases", "--resolve", phase_name],
            capture_output=True,
            text=True,
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


@dataclass(frozen=True)
class CommitGateOutcome:
    """Typed projection of a real SubagentStop hook return on a commit step.

    * ``blocked`` is True when the hook returned a ``{"decision":"block"}`` body
      naming the commit exit-gate (the gate fired and stopped the agent from
      closing the slice). False when the hook fell through to a generic
      ``{"decision":"allow"}`` (the marker word did NOT route to the gate).
    """

    word: str
    blocked: bool
    decision: str
    event: str


class CommitStepGateComposition:
    """Drives the REAL SubagentStop hook via its stdin protocol (Layer-4).

    Mandate-13 (driving-port-only): the SUT is the installed hook entry
    ``claude_code_hook_adapter subagent_stop`` fed a JSON hook payload on stdin
    -- the exact surface Claude Code invokes. NO production
    ``des.domain``/``des.application``/``des.adapters`` symbol is imported; the
    only contact is via ``subprocess.run``.

    The load-bearing seam this exercises is the C3 string-literal phase dispatch
    (``subagent_stop_handler.py:1214``): today only the literal ``"G_COMMIT"``
    routes a returning atdd_pure agent to the commit exit-gate. slice-02 re-keys
    that dispatch so the canonical ``"D_REFACTOR_COMMIT"`` word routes to the SAME
    gate AND the legacy ``"G_COMMIT"`` word still routes there (alias replay).

    Confound isolation: the workspace is a fresh empty temp dir with NO verified
    slice commit, so the exit-gate's commit-completeness check ALWAYS fails ->
    the gate emits ``{"decision":"block","event":"SliceCommitBlocked"}``. That
    block is the forcing function that makes the ROUTING observable: a word that
    routes to the gate -> a block; a word that does NOT route -> a clean generic
    ``{"decision":"allow"}``. The two outcomes are unambiguously distinguishable,
    so the observable is the gate FIRING (routing), never the unrelated
    commit-verification verdict.
    """

    def report_finished_commit_step(self, word: CommitStepWord) -> CommitGateOutcome:
        with tempfile.TemporaryDirectory() as workspace:
            repo = Path(workspace)
            self._init_repo(repo)
            return self._drive_hook(word, repo)

    def _init_repo(self, repo: Path) -> None:
        # The exit-gate runs git-dependent completeness checks; a bare temp dir
        # is part of the harness defect. A real git repo with one empty commit
        # makes HEAD resolve while the absent VERIFIED slice commit keeps the
        # gate blocking on routing (confound isolation preserved).
        self._git(repo, "init")
        self._git(repo, "config", "user.email", "t@t.com")
        self._git(repo, "config", "user.name", "T")
        (repo / "README.md").write_text("seed\n", encoding="utf-8")
        self._git(repo, "add", "README.md")
        self._git(repo, "commit", "-m", "chore: seed")

    def _git(self, repo: Path, *args: str) -> None:
        subprocess.run(
            ["git", *args], cwd=str(repo), capture_output=True, text=True, check=True
        )

    def _drive_hook(self, word: CommitStepWord, workspace: Path) -> CommitGateOutcome:
        transcript = self._write_marker_transcript(word, workspace)
        proc = subprocess.run(
            [
                sys.executable,
                "-m",
                "des.adapters.drivers.hooks.claude_code_hook_adapter",
                "subagent_stop",
            ],
            input=json.dumps(
                {
                    "agent_transcript_path": str(transcript),
                    "cwd": str(workspace),
                    "agent_type": "software-crafter",
                }
            ),
            capture_output=True,
            text=True,
            cwd=str(workspace),
        )
        return self._parse_gate_outcome(word, proc)

    def _write_marker_transcript(self, word: CommitStepWord, workspace: Path) -> Path:
        # HTML-comment marker block (DesMarkerParser requires this form; plain
        # text parses to None). Mirrors the WORKING spine_hardening reference
        # ``_marker_block`` -- DES-SLICE (not DES-SLICE-ID), and DES-PROJECT-ROOT
        # carrying the absolute workspace path.
        marker = (
            "<!-- DES-VALIDATION : required -->\n"
            "<!-- DES-MODE : atdd_pure -->\n"
            f"<!-- DES-PHASE : {word.value} -->\n"
            "<!-- DES-SLICE : slice-02 -->\n"
            "<!-- DES-PROJECT-ID : demo-feature -->\n"
            f"<!-- DES-PROJECT-ROOT : {workspace} -->\n"
        )
        transcript = workspace / "transcript.jsonl"
        transcript.write_text(
            json.dumps({"type": "user", "message": {"role": "user", "content": marker}})
            + "\n",
            encoding="utf-8",
        )
        return transcript

    def _parse_gate_outcome(
        self, word: CommitStepWord, proc: subprocess.CompletedProcess[str]
    ) -> CommitGateOutcome:
        payload = self._safe_json(proc.stdout)
        decision = str(payload.get("decision", ""))
        event = str(payload.get("event", ""))
        blocked = decision == "block" and event == "SliceCommitBlocked"
        return CommitGateOutcome(
            word=word.value, blocked=blocked, decision=decision, event=event
        )

    def _safe_json(self, raw: str) -> dict:
        try:
            parsed = json.loads(raw)
        except json.JSONDecodeError:
            return {}
        return parsed if isinstance(parsed, dict) else {}
