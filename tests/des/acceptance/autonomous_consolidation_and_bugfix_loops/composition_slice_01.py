"""Composition root + shared fixtures for autonomous-consolidation-and-bugfix-loops
slice-01 (the walking skeleton — charter
`a-stale-closed-agent-recovers-its-own-verdict.md`, feature-delta Slice Plan
row slice-01, Locked Decision D-1).

Pillar 3 (App as in production): the SUT is the REAL SubagentStop hook's
stale-agent terminal-state check — `handle_subagent_stop`, invoked over its
JSON stdin protocol via the SAME faithful in-process driving-port pattern the
shipped `oss-spine-watchdog` slice-03 sibling uses (`composition_slice_03.py`,
`run_hook_in_process` — the sanctioned, behaviour-identical replacement for a
forked `python -c "... handle_subagent_stop()"` subprocess, per the
`corpus-migration-in-process` Mikado graph both features now share). This
module NEVER imports `_maybe_emit_stale_agent_closed` (or any other
direct-domain symbol) to invoke the SUT — only the real hook entry point is
driven. `AtCompletionLedger` is imported ONLY to SEED precondition state
(the closed agent's last-progress timestamp) and to OBSERVE the resulting
records (the S2 tolerable-variant, same as the `oss-spine-watchdog` siblings)
— it is substrate + observation, NOT the SUT.

── D-5 REUSE, not rebuild ──
`StaleAgentClosed` detection/closure is SHIPPED (`oss-spine-watchdog`,
`_maybe_emit_stale_agent_closed`) and is NOT re-implemented here. This slice
EXTENDS that trigger: on every `StaleAgentClosed` emission the spine must
ALSO parse the closed agent's own transcript for its last-stated verdict and
write a PAIRED recovery record to the ledger in the SAME hook invocation
(D-1, D-8). The `closed=True` half of every outcome below is expected to be
GREEN already (the shipped mechanism); the `paired_recovery` / `recovered` /
`distinguishable` / `durable_on_reread` halves are the slice-01 feature debt
this AT specifies (RED today — no such recovery emission exists yet).

── THE CONTROLLABLE CLOCK (deterministic stale gap, NO real sleep) ──
Mirrors `oss-spine-watchdog` slice-03: the agent's last-progress ledger
record is seeded with an EXPLICIT timestamp 25 minutes in the past (> the
20-minute default threshold), honoured verbatim by the F-13 producer-
timestamp writer contract, so `StaleAgentClosed` fires deterministically
without a real wall-clock sleep.

── THE DISTILL-INTERIM PARSING CONTRACT (feature-delta Open Question 1) ──
No DESIGN wave ran for this feature; the parsing contract is resolved HERE,
concretely, as the acceptance criteria DELIVER must satisfy — see
`steps.domain_types_slice_01` module docstring for the full contract. In
short: an ASSISTANT-role transcript message containing a line matching
``VERDICT:\\s*(PASS|FAIL|BLOCKED)`` (case-insensitive) is a stated verdict;
the recovery keeps the LAST (most recent) such marker found scanning every
assistant message, never only the final one (a verdict "buried under noise"
must still resolve). No matching marker anywhere / zero assistant messages /
unparseable assistant-turn content => UNRECOVERABLE, honestly recorded,
never a fabricated guess.

── Mechanical assertion (Mandate-13 invariant 5) ──
Python + git + filesystem only (the hook resolves a real repo + reads a real
ledger JSONL, as in production), cross-OS. The terminal is exit 0 with NO
`{decision:block}` body — unchanged from the shipped stale-close contract.

Universe (Mandate 8): {outcome.closed, outcome.paired_recovery,
outcome.recovered, outcome.recovered_verdict, outcome.unrecoverable_reason,
outcome.distinguishable, outcome.durable_on_reread, outcome.new_record_count}.
Internal fields (Popen handle, env dict, raw transcript bytes, raw ledger
path) NEVER appear.

Layer 3/4 (real git repo + real ledger JSONL + real hook invocation against
tmp_path): example-only (Mandate 9 v2 — the driven set includes a real
filesystem adapter + a real git subprocess + a real hook invocation =>
@real-io => example-based, NOT PBT). Sad paths explicit (Mandate 11). No PBT
machinery imported.
"""

from __future__ import annotations

import json
import subprocess
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

# Precondition-substrate writer + observation reader (NOT the SUT). Seeds the
# agent's last-progress record and reads back the appended records — the S2
# tolerable-variant, same as the oss-spine-watchdog siblings.
from des.adapters.driven.logging.at_completion_ledger import AtCompletionLedger

# The REAL `handle_subagent_stop` SubagentStop hook, driven IN-PROCESS over
# its stdin protocol (node-C enabler `run_hook_in_process`) — the same
# faithful driving-port pattern `oss-spine-watchdog` slice-03 uses.
from des.adapters.drivers.hooks.subagent_stop_handler import handle_subagent_stop
from tests.common.in_process_cli import run_hook_in_process

from .steps.domain_types_slice_01 import (
    FeatureId,
    RecoveryOutcome,
    SliceId,
    TranscriptVerdictCase,
)


_HANDLER_MODULE = "des.adapters.drivers.hooks.subagent_stop_handler"

# The feature + synthetic returning-agent slice this suite builds a stale
# agent for. Distinct from the carpaccio `@slice-01` tag on the .feature
# scenarios themselves (that tag names THIS AT's own carpaccio slice; this
# constant is an arbitrary fixture key inside the fake ledger namespace,
# mirroring the oss-spine-watchdog slice-03 `slice-09` disambiguation).
_FEATURE_ID = FeatureId("autonomous-consolidation-and-bugfix-loops-demo")
_SLICE_ID = SliceId("slice-21")

# The DESIGN OQ-4 default stale threshold (shipped, D-5 reuse) = 20 minutes.
_STALE_GAP_MINUTES = 25  # > threshold -> the shipped StaleAgentClosed fires

# A non-gate atdd_pure phase: a re-fired-without-progress A_GREEN return
# routes to the generic `_handle_atdd_pure_return`, where the stale check
# (and this slice's recovery graft) live.
_RETURN_PHASE = "A_GREEN"

# The two recovery-record event names this slice's AT specifies (the
# DISTILL-interim wire contract; not yet defined in production). Named here
# with the SAME naming discipline the shipped ledger events use
# (`StaleAgentClosed`, `SliceCommitVerified`, ...).
_EVENT_RECOVERED = "StaleAgentVerdictRecovered"
_EVENT_UNRECOVERABLE = "StaleAgentVerdictUnrecoverable"
_SOURCE_TRANSCRIPT_RECOVERED = "transcript-recovered"

# The agent-reported "completed" terminal event names a recovery record must
# be distinguishable FROM (charter Positive-2 — "distinguishable from a
# normal completed terminal").
_AGENT_REPORTED_TERMINALS = frozenset(
    {"SliceCommitVerified", "WorkflowPhaseCompletedGCommit"}
)


def _git(repo: Path, *args: str) -> str:
    """Run a git command inside the repo and return its stdout."""
    completed = subprocess.run(
        ["git", *args], cwd=repo, capture_output=True, text=True, check=True
    )
    return completed.stdout


def _explicit_timestamp(minutes_ago: int) -> str:
    """An ISO-8601 ledger timestamp `minutes_ago` minutes before NOW.

    Mirrors the ledger writer's own format (UTC ISO, `+00:00` rendered as
    `Z`) so the seeded record is byte-identical in shape to a real producer
    record. Pure function — the controllable clock, no real sleep.
    """
    moment = datetime.now(timezone.utc) - timedelta(minutes=minutes_ago)
    return moment.isoformat().replace("+00:00", "Z")


def _assistant_entry(text: str) -> str:
    """One JSONL line for an ASSISTANT-role transcript message. Pure function."""
    return json.dumps(
        {
            "type": "assistant",
            "message": {"role": "assistant", "content": text},
            "uuid": f"assistant-{abs(hash(text))}",
            "timestamp": "2026-06-04T09:00:00Z",
        }
    )


class RecoveryFixture:
    """Composition-root service for autonomous-consolidation-and-bugfix-loops
    slice-01 ATs.

    Pillar 3: builds a real git repo under tmp_path, seeds the agent's
    last-progress ledger record with a STALE timestamp (the controllable
    clock -- the shipped D-5 close mechanism always fires), writes a
    transcript shaped by the `TranscriptVerdictCase`, fires the SAME
    `handle_subagent_stop` hook the live spine fires, and observes both the
    (shipped) close AND the (slice-01, RED-today) paired recovery record.

    Mandate-12 criterion 3: every public method is the SSOT for one piece of
    business logic. Step bodies do a typed lookup + one method call; nothing
    more.
    """

    def __init__(self, tmp_path: Path) -> None:
        self._repo = tmp_path / "deliver-repo"
        self._transcript_path = self._repo / "agent.jsonl"

    # --- repo provisioning ----------------------------------------------

    def build_returning_agent_repo(self) -> None:
        """Lay out a real git repo a returning atdd_pure agent committed work in."""
        self._repo.mkdir(parents=True, exist_ok=True)
        _git(self._repo, "init", "--quiet")
        _git(self._repo, "config", "user.email", "loops-slice01@example.test")
        _git(self._repo, "config", "user.name", "Loops Slice 01 AT")
        (self._repo / "README.md").write_text("seed\n", encoding="utf-8")
        _git(self._repo, "add", "README.md")
        _git(self._repo, "commit", "--quiet", "-m", "chore: seed")
        (self._repo / "code.py").write_text("x = 1\n", encoding="utf-8")
        _git(self._repo, "add", "code.py")
        _git(
            self._repo,
            "commit",
            "--quiet",
            "-m",
            f"feat: deliver slice work\n\nSlice-Id: {_SLICE_ID}",
        )

    # --- precondition substrate: the last-progress record ----------------

    def seed_last_progress(self) -> None:
        """Seed the closed agent's LAST PROGRESS record, 25 minutes stale.

        Always past the shipped 20-minute threshold — this slice's AT is
        about the RECOVERY that pairs with a close, not the close-vs-leave-
        alone discrimination (already specified by oss-spine-watchdog
        slice-03). Precondition state, NOT the SUT.
        """
        ledger = AtCompletionLedger(_FEATURE_ID, self._repo)
        ledger._append_record(
            {
                "event": "AtGreenSliceProgress",
                "slice_id": str(_SLICE_ID),
                "timestamp": _explicit_timestamp(_STALE_GAP_MINUTES),
            }
        )

    # --- the closed agent's OWN transcript (the recovery's input) --------

    def _write_transcript(self, case: TranscriptVerdictCase) -> None:
        """Write the closed agent's transcript per the DISTILL-interim contract.

        Every case ends with the returning DES-marker return block (routes
        the hook into the generic `_handle_atdd_pure_return` -- the path the
        stale check and this slice's recovery graft live on), preceded by
        whatever assistant content the case models. See the module docstring
        + `domain_types_slice_01.TranscriptVerdictCase` for the exact recipe
        per case.
        """
        lines: list[str] = []
        if case is TranscriptVerdictCase.CLEAR_PASS:
            lines.append(
                _assistant_entry(
                    "Working through the refactor.\nVERDICT: PASS\nAll green, "
                    "3 of 3 files stabilized."
                )
            )
        elif case is TranscriptVerdictCase.CLEAR_FAIL:
            lines.append(
                _assistant_entry(
                    "Hit a wall on the last file.\nVERDICT: FAIL\nCould not "
                    "stabilize the contract test."
                )
            )
        elif case is TranscriptVerdictCase.BURIED_UNDER_NOISE:
            lines.append(
                _assistant_entry(
                    "Finishing up the slice.\nVERDICT: PASS\nDone, all tests green."
                )
            )
            lines.append(
                _assistant_entry("Let me double-check the test output once more.")
            )
            lines.append(
                _assistant_entry("Running one more tool call just to be safe.")
            )
        elif case is TranscriptVerdictCase.AMBIGUOUS:
            lines.append(
                _assistant_entry("Still investigating the failure, not sure yet.")
            )
            lines.append(_assistant_entry("Trying a different approach now."))
        elif case is TranscriptVerdictCase.EMPTY:
            pass  # zero assistant messages -- the agent never produced content
        elif case is TranscriptVerdictCase.CORRUPTED:
            # Unparseable JSON on the assistant-turn lines (a truncated /
            # mangled write) -- the recovery must degrade honestly, never
            # crash, never guess. The closing marker line (appended below)
            # stays a VALID JSON entry so the hook still routes correctly.
            lines.append("{this is not valid json at all")
            lines.append('{"type": "assistant", "message": {"role": "assistant"')
        else:  # pragma: no cover — exhaustive enum, defensive default
            raise ValueError(f"unhandled TranscriptVerdictCase: {case!r}")

        lines.append(self._marker_line())
        self._transcript_path.write_text("\n".join(lines) + "\n", encoding="utf-8")

    def _marker_line(self) -> str:
        """The returning DES-marker block (mirrors oss-spine-watchdog slice-03)."""
        block = (
            "<!-- DES-VALIDATION : required -->\n"
            "<!-- DES-MODE : atdd_pure -->\n"
            f"<!-- DES-PHASE : {_RETURN_PHASE} -->\n"
            f"<!-- DES-SLICE : {_SLICE_ID} -->\n"
            f"<!-- DES-PROJECT-ID : {_FEATURE_ID} -->\n"
            f"<!-- DES-PROJECT-ROOT : {self._repo} -->\n"
        )
        return json.dumps(
            {
                "type": "user",
                "message": {"role": "user", "content": block},
                "uuid": "a-green-return",
                "timestamp": "2026-06-04T10:00:00Z",
            }
        )

    # --- driving-port invocation (the REAL hook) --------------------------

    def run_recovery_check(self, *, case: TranscriptVerdictCase) -> RecoveryOutcome:
        """Seed a stale, no-terminal agent with `case`'s transcript, fire the
        REAL hook once, and observe the paired-recovery outcome.
        """
        self.seed_last_progress()
        self._write_transcript(case)
        before = self._read_all()
        self._fire_hook()
        after = self._read_all()
        return self._interpret(before, after)

    def refire_after_recovery(self) -> RecoveryOutcome:
        """Re-fire the SAME hook a second time against the now-closed agent.

        No new seeding, no transcript rewrite -- models the operator's
        background loop simply re-firing (or Claude Code re-invoking the
        stop hook) on an agent that already reached its terminal + recovery.
        Charter "What to explore": "does a second stale-close attempt
        double-write or correctly no-op?"
        """
        before = self._read_all()
        self._fire_hook()
        after = self._read_all()
        return self._interpret(before, after)

    def _fire_hook(self) -> subprocess.CompletedProcess[str]:
        """Invoke the REAL `handle_subagent_stop` hook over its JSON protocol."""
        hook_input = json.dumps(
            {
                "session_id": "loops-slice01-session",
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
        exit_code, stdout, stderr = run_hook_in_process(
            handle_subagent_stop,
            stdin_text=hook_input,
            cwd=str(self._repo),
        )
        return subprocess.CompletedProcess(
            args=[_HANDLER_MODULE],
            returncode=exit_code,
            stdout=stdout,
            stderr=stderr,
        )

    # --- ledger observation ------------------------------------------------

    def _read_all(self) -> list[dict]:
        """Read every record for this fixture's ledger (port read, port-exposed)."""
        ledger = AtCompletionLedger(_FEATURE_ID, self._repo)
        try:
            return ledger.read_records()
        except Exception:
            return []

    def _reread_sees(self, record: dict) -> bool:
        """A FRESH ledger reader instance still sees `record` (durability check)."""
        fresh_ledger = AtCompletionLedger(_FEATURE_ID, self._repo)
        try:
            records = fresh_ledger.read_records()
        except Exception:
            return False
        return any(
            r.get("seq") == record.get("seq") and r.get("event") == record.get("event")
            for r in records
        )

    def _interpret(self, before: list[dict], after: list[dict]) -> RecoveryOutcome:
        """Build the port-exposed observable outcome from a before/after ledger diff."""
        new_records = after[len(before) :]
        closed = any(r.get("event") == "StaleAgentClosed" for r in new_records)
        recovery_records = [
            r
            for r in new_records
            if r.get("event") in (_EVENT_RECOVERED, _EVENT_UNRECOVERABLE)
        ]
        paired = closed and len(recovery_records) == 1

        recovered = False
        recovered_verdict: str | None = None
        unrecoverable_reason: str | None = None
        distinguishable = False
        durable = False
        if paired:
            record = recovery_records[0]
            recovered = record.get("event") == _EVENT_RECOVERED
            recovered_verdict = record.get("recovered_verdict") if recovered else None
            unrecoverable_reason = record.get("reason") if not recovered else None
            distinguishable = (
                record.get("source") == _SOURCE_TRANSCRIPT_RECOVERED
                and record.get("event") not in _AGENT_REPORTED_TERMINALS
            )
            durable = self._reread_sees(record)

        return RecoveryOutcome(
            closed=closed,
            paired_recovery=paired,
            recovered=recovered,
            recovered_verdict=recovered_verdict,
            unrecoverable_reason=unrecoverable_reason,
            distinguishable=distinguishable,
            durable_on_reread=durable,
            new_record_count=len(new_records),
        )


@pytest.fixture
def recovery_fixture(tmp_path) -> RecoveryFixture:
    """The single composition-root service all slice-01 step methods delegate to."""
    return RecoveryFixture(tmp_path)


@pytest.fixture
def state_01() -> dict:
    """Per-scenario scratchpad: `case`, `outcome`, `before`."""
    return {}


__all__ = [
    "RecoveryFixture",
]
