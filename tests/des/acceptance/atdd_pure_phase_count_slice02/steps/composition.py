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
import os
import subprocess
import tempfile
from dataclasses import dataclass
from pathlib import Path

from des.adapters.drivers.hooks.hook_router import main as _hook_router_main
from des.cli.phases import main as _phases_main
from tests.common.in_process_cli import run_cli_in_process, run_hook_in_process

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


@dataclass(frozen=True)
class CommitGateOutcome:
    """Typed projection of a real SubagentStop hook return on a commit step.

    * ``blocked`` is True when the hook returned a ``{"decision":"block"}`` body
      naming the commit exit-gate (the gate fired and stopped the agent from
      closing the slice). False when the hook fell through to a generic
      ``{"decision":"allow"}`` (the marker word did NOT route to the gate).
    * ``decision_found`` is True when SOME JSON line in stdout carried a
      "decision" key -- i.e. a verdict was actually observed, whether or not
      it was a block. False means no such line was parseable at all, which is
      a DIFFERENT failure than "the gate declined to block": it means the
      composition never got a verdict to read in the first place (a parse
      accident, a crash, an unexpected stdout shape). The Then-step must not
      collapse these two into the same accusation -- see the fix-commit-gate
      false-cause-message finding (raw stdout is kept for that branch only).
    """

    word: str
    blocked: bool
    decision: str
    event: str
    decision_found: bool
    raw_stdout: str


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
            self._activate_project(repo)
            return self._drive_hook(word, repo)

    def _activate_project(self, repo: Path) -> None:
        """ACTIVATE the tmp project so the ADR-AG-001 activation gate dispatches
        the SubagentStop handler (an INACTIVE project short-circuits with
        sys.exit(0) before the C3 commit-word dispatch ever runs -- a state
        production never produces, so the routing seam must be exercised on an
        active root). Writes the global-config marker the gate reads at
        ``$HOME/.nwave/global-config.json``; ``_drive_hook`` sandboxes HOME to
        ``repo`` so this marker is the one the gate resolves."""
        gc = repo / ".nwave" / "global-config.json"
        gc.parent.mkdir(parents=True, exist_ok=True)
        gc.write_text(json.dumps({"activation": {"mode": "all"}}), encoding="utf-8")

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
        stdin_payload = json.dumps(
            {
                "agent_transcript_path": str(transcript),
                "cwd": str(workspace),
                "agent_type": "software-crafter",
            }
        )
        # In-process analogue of `python -m des...claude_code_hook_adapter
        # subagent_stop` with JSON on stdin: drive the REAL `hook_router.main`
        # over argv `[prog, "subagent_stop"]`. This PRESERVES the ADR-AG-001
        # activation gate (`apply_gate`) the routing seam depends on, while
        # bypassing the facade's decision-irrelevant import-time freshness notice
        # (stderr-only). HOME is sandboxed to the workspace (the activation gate
        # reads `$HOME/.nwave/global-config.json`); set + restored in finally,
        # shared-process safe. Result wrapped in CompletedProcess so the typed
        # gate-outcome parser stays byte-identical.
        prior_home = os.environ.get("HOME")
        os.environ["HOME"] = str(workspace)
        try:
            exit_code, stdout, stderr = run_hook_in_process(
                _hook_router_main,
                stdin_text=stdin_payload,
                cwd=str(workspace),
                argv=["claude_code_hook_adapter", "subagent_stop"],
            )
        finally:
            if prior_home is None:
                os.environ.pop("HOME", None)
            else:
                os.environ["HOME"] = prior_home
        proc = subprocess.CompletedProcess(
            args=[], returncode=exit_code, stdout=stdout, stderr=stderr
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
        payload = self._find_decision_line(proc.stdout)
        decision = str(payload.get("decision", ""))
        event = str(payload.get("event", ""))
        blocked = decision == "block" and event == "SliceCommitBlocked"
        return CommitGateOutcome(
            word=word.value,
            blocked=blocked,
            decision=decision,
            event=event,
            decision_found=bool(payload),
            raw_stdout=proc.stdout,
        )

    def _find_decision_line(self, raw: str) -> dict:
        # Every atdd_pure SubagentStop exit emits its OWN causal-envelope JSON
        # line first (`_emit_causal_envelope`, subagent_stop_handler.py:313),
        # THEN the gate's decision JSON line -- two newline-separated JSON
        # documents, not one. A blind ``json.loads(raw)`` over the whole blob
        # raises "Extra data" and silently degrades to ``{}``, misreporting a
        # correctly-blocking gate as an unrouted word. The sibling
        # ``causal_dispatch_envelope`` composition parses the same two-line
        # shape line-by-line (test_dispatch_intent_causality.py:92-97); mirror
        # it here, picking the line that carries the gate's own "decision" key.
        for line in raw.splitlines():
            candidate = self._safe_json(line)
            if "decision" in candidate:
                return candidate
        return {}

    def _safe_json(self, raw: str) -> dict:
        try:
            parsed = json.loads(raw)
        except json.JSONDecodeError:
            return {}
        return parsed if isinstance(parsed, dict) else {}
