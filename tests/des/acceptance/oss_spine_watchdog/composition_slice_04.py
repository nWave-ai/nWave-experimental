"""Composition root + shared fixtures for oss-spine-watchdog slice-04.

Pillar 3 (App as in production): the SUT is the REAL `handle_subagent_stop`
SubagentStop hook, invoked over its JSON stdin protocol AS A SUBPROCESS, exactly as
the shipped, proven slice-02 sibling (`composition_slice_02.py`, the G_COMMIT
exit-gate bounded-block terminal) and slice-03 sibling (`composition_slice_03.py`,
the stale-agent terminal-state check) drive it. Slice-04 is the terminal-coherence
feature-end-fix: the deep feature-end review (`a360758f`, 2026-06-05) REJECTED the
coherent feature because the DDD-5 terminating-INDETERMINATE wire-format
(non-block + loud stderr + DURABLE ledger record) was realized INCONSISTENTLY
across the 3 terminals. This composition drives the REAL hook at the two surfaces
the two surviving blockers live on, and asserts the OBSERVABLE each blocker breaks.

── DRIVING PORT (Mandate-13, invariant 1+2): real hook subprocess ──
The driving port is the REAL `handle_subagent_stop` hook subprocess:
    python -c "... from ...subagent_stop_handler import handle_subagent_stop;
               sys.exit(handle_subagent_stop())"
This module NEVER does `from des.adapters.drivers.hooks.subagent_stop_handler import
_emit_bounded_block_terminal` (or `_maybe_emit_stale_agent_closed`, or any direct
domain/application/adapter import) to invoke the SUT at the test boundary — the SUT
is exercised ONLY via the hook subprocess. `AtCompletionLedger` is imported ONLY to
SEED the precondition records AND to RE-READ the durable terminal record the
assertion observes (the S2 tolerable-variant — seed/observe precondition+observable
state through the production writer/reader, same as both siblings); it is substrate
+ the observable port surface, NOT the SUT.

── AT-01 (BLOCKER-2 / R-69-A): the durable bounded-block terminal record ──
Mirror of composition_slice_02.py: build a real git repo whose HEAD commit FAILS
E1 (the slice's `.feature` AT is authored on disk but kept OUT of the commit), seed
N-1 (=2) prior identical `SliceCommitBlocked` for `(slice, pinned_sha)` through the
production writer, then fire the hook ONCE — that single invocation IS the 3rd
identical block → the bounded-block terminal fires. The OBSERVABLE slice-02 OMITTED
and slice-04 PINS: a DURABLE `SliceCommitBlockedTerminal` ledger record IS written.
Observed by a re-read count delta on `SliceCommitBlockedTerminal` (mirror
composition_slice_03.py `_read_stale_closed_count`).

  RED TODAY: `_emit_bounded_block_terminal` (`subagent_stop_handler.py:518-541`) is
  stderr-ONLY — it prints to `sys.__stderr__` then `return 0`, with NO
  `_append_record`. So `grep SliceCommitBlockedTerminal src/` = 0 and the re-read
  count delta is 0 → `terminal_recorded` is False → SEMANTIC assertion mismatch
  (`set_to(True)` expected, False observed), NOT an import error (Mandate-7
  RED-vs-BROKEN preserved). The 3rd block DOES terminate non-block today (slice-02
  shipped that) — what is MISSING is the durable record.

  GREEN: the bounded-block terminal routes through the EXTRACTed shared
  `_emit_terminating_indeterminate(event, reason)` that writes a durable
  `SliceCommitBlockedTerminal` record (+ loud stderr + DV-2 audit event).

── AT-02 (BLOCKER-3 / R-69-B): the cross-invocation no-false-negative ──
Mirror of composition_slice_03.py: a returning atdd_pure agent whose last progress
is STALE (25-min seed past the 20-min threshold) AND whose ledger history holds a
prior record. The `PriorTerminalKind` discriminates the two histories — both stale,
so the ONLY discriminator is whether the prior record is a GENUINE terminal:

  NON_TERMINAL_BLOCK — a regular `SliceCommitBlocked` re-fire record (the kind a
    bounded-block-terminated agent leaves behind). It is NOT a terminal, so the
    stale check MUST CLOSE the stuck agent (`StaleAgentClosed`).
      RED TODAY: `_EXISTING_TERMINAL_EVENTS = {SliceCommitVerified,
      SliceCommitBlocked}` (`subagent_stop_handler.py:692`) — the stale check's
      `any(record.event in _EXISTING_TERMINAL_EVENTS ...)` precondition treats the
      historical `SliceCommitBlocked` as a terminal → returns False (no close) →
      the genuinely-stuck agent is WRONGLY LEFT ALONE (`closed` is False, expected
      True). SEMANTIC mismatch, not an import error.
      GREEN: `_EXISTING_TERMINAL_EVENTS` re-keyed onto GENUINE terminals
      `{SliceCommitVerified, SliceCommitBlockedTerminal, StaleAgentClosed}` — a
      regular `SliceCommitBlocked` is no longer mistaken for a terminal → the stale
      check closes the stuck agent.

  GENUINE_TERMINAL — a `SliceCommitVerified` completed terminal. The stale check
    MUST NOT close it (the no-double-close precondition is PRESERVED).
      GREEN TODAY and MUST STAY GREEN (the anti-vacuity pin): the current and the
      re-keyed precondition both treat `SliceCommitVerified` as a terminal, so the
      agent is correctly left alone. A re-key that simply DROPPED the precondition
      (always-close on a stale gap) would RED this pin — the pin guards the
      re-key against over-correction.

── THE CONTROLLABLE CLOCK (deterministic stale gap, NO real sleep) ──
The progress signal is the AT-completion ledger record `timestamp`
(`at_completion_ledger.py:703`); the F-13 producer-timestamp contract
(`at_completion_ledger.py:665`) lets the AT seed a record with an EXPLICIT 25-min-old
timestamp so the wall-clock gap the hook computes is deterministic WITHOUT a real
sleep (identical to slice-03's clock). The prior record (block or terminal) is ALSO
seeded 25-min-old so the most-recent record is stale either way — the ONLY thing
that can withhold the close in the GENUINE_TERMINAL case is the no-double-close
precondition (mirrors slice-03's AT-03 anti-vacuity construction).

── Mechanical assertion (Mandate-13 invariant 5) ──
Python + git + filesystem only (the hook resolves a real repo + reads/writes a real
ledger JSONL), cross-OS. The terminal is exit 0 with NO `{decision:block}` body
(DESIGN OQ-5). The durable-record observables (AT-01 + AT-02 close) are re-read
count deltas on the ledger — port-exposed observables, never internal fields.

Universe (Mandate 8): AT-01 {outcome.terminal_recorded, outcome.blocked}; AT-02
{outcome.closed, outcome.blocked}. Internal plumbing NEVER appears.

Layer 3/4 (real git repo + real ledger JSONL + real hook subprocess against
tmp_path): example-only (Mandate 9 v2 — @real-io: the driven set includes a real
filesystem adapter + a real git subprocess + a real hook subprocess → NOT PBT;
Mandate 11 — sad paths enumerated explicitly). No PBT machinery imported.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

# Precondition-substrate writer + observable-record reader (NOT the SUT). Seeds the
# prior SliceCommitBlocked / SliceCommitVerified / last-progress records and re-reads
# the durable terminal records the assertions observe — the S2 tolerable-variant
# "seed/observe precondition+observable state through the production writer/reader"
# (slice-01 / slice-02 / slice-03 siblings).
from des.adapters.driven.logging.at_completion_ledger import AtCompletionLedger

from .steps.domain_types_slice_04 import (
    BoundedTerminalOutcome,
    CrossInvocationOutcome,
    FeatureId,
    PriorTerminalKind,
    SliceId,
)


# Repo root = .../nWave-dev (this file lives 4 dirs deep under tests/des/...).
_REPO_ROOT = Path(__file__).resolve().parents[4]
_REPO_SRC = _REPO_ROOT / "src"

_HANDLER_MODULE = "des.adapters.drivers.hooks.subagent_stop_handler"

# The feature + slice this acceptance suite builds terminals for.
_FEATURE_ID = FeatureId("oss-spine-watchdog-demo")
_SLICE_ID = SliceId("slice-11")

# The bounded-block bound: terminate ON the 3rd identical block (DISCUSS D-4 /
# DESIGN OQ-3), so 2 ordinary blocks precede the terminating invocation. The AT
# seeds N-1 prior identical blocks, then drives the hook once: that single
# invocation IS the Nth (3rd) block (mirror slice-02).
_N_BOUND = 3
_PRIOR_IDENTICAL_BLOCKS = _N_BOUND - 1  # = 2

# The DESIGN OQ-4 stale threshold (default 20 min, R1 config-SSOT not yet landed).
# The seeded gap (25 min) is comfortably past it (mirror slice-03's controllable
# clock), so the stale discrimination is deterministic without a real sleep.
_THRESHOLD_MINUTES = 20
_STALE_GAP_MINUTES = 25

# A non-gate atdd_pure phase: a re-fired-without-progress A_GREEN return routes to
# the generic `_handle_atdd_pure_return` (the stale check's host), NOT the
# commit-gate branch (mirror slice-03 / DESIGN R-7).
_RETURN_PHASE = "A_GREEN"

# The durable terminal record the bounded-block terminal MUST write (DDD-5 / DV-1 /
# BLOCKER-2). RED today (`grep SliceCommitBlockedTerminal src/` = 0).
_BOUNDED_TERMINAL_EVENT = "SliceCommitBlockedTerminal"

# The genuine completed terminal (AT-02 anti-vacuity pin). A `SliceCommitVerified`
# is a real terminal under BOTH the current and the re-keyed precondition.
_GENUINE_TERMINAL_EVENT = "SliceCommitVerified"

# The non-terminal re-fire record (AT-02 BLOCKER-3 pin). A regular
# `SliceCommitBlocked` is NOT a genuine terminal — the slice-04 re-key drops it
# from `_EXISTING_TERMINAL_EVENTS`.
_NON_TERMINAL_BLOCK_EVENT = "SliceCommitBlocked"


def _git(repo: Path, *args: str) -> str:
    """Run a git command inside the repo and return its stdout."""
    completed = subprocess.run(
        ["git", *args], cwd=repo, capture_output=True, text=True, check=True
    )
    return completed.stdout


def _explicit_timestamp(minutes_ago: int) -> str:
    """An ISO-8601 ledger timestamp `minutes_ago` minutes before NOW.

    Mirrors the ledger writer's own format (`at_completion_ledger.py:703-705`: UTC
    ISO with the `+00:00` offset rendered as `Z`) so the seeded record is
    byte-identical in shape to a real producer record. Pure function — the
    controllable clock that makes the stale gap deterministic without a real sleep
    (identical to slice-03).
    """
    moment = datetime.now(timezone.utc) - timedelta(minutes=minutes_ago)
    return moment.isoformat().replace("+00:00", "Z")


class TerminalCoherenceFixture:
    """Composition-root service for oss-spine-watchdog slice-04 ATs.

    Pillar 3: builds a real git repo under tmp_path, seeds precondition ledger
    records through the production `AtCompletionLedger` writer, then fires the SAME
    `handle_subagent_stop` hook the live spine fires — at the bounded-block terminal
    surface (AT-01) and the cross-invocation stale-check surface (AT-02). The AT
    observes each terminal's DURABLE record via a re-read count delta on the ledger.

    Mandate-12 criterion 3: every public method is the SSOT for one piece of
    business logic. Step bodies do a typed lookup + one method call; nothing more.
    """

    def __init__(self, tmp_path: Path) -> None:
        self._repo = tmp_path / "deliver-repo"
        self._transcript_path = self._repo / "agent.jsonl"
        self._head_sha: str | None = None

    # --- repo provisioning (shared by both surfaces) -------------------------

    def _init_repo(self) -> None:
        """Lay out a real git repo with a seed commit (the hook resolves its cwd)."""
        self._repo.mkdir(parents=True, exist_ok=True)
        _git(self._repo, "init", "--quiet")
        _git(self._repo, "config", "user.email", "watchdog-slice04@example.test")
        _git(self._repo, "config", "user.name", "Watchdog Slice 04 AT")
        (self._repo / "README.md").write_text("seed\n", encoding="utf-8")
        _git(self._repo, "add", "README.md")
        _git(self._repo, "commit", "--quiet", "-m", "chore: seed")

    def build_blocking_commit(self) -> None:
        """Lay out a repo whose HEAD commit FAILS the E1 exit gate (AT-01).

        The slice's `@slice-NN` `.feature` AT is authored on disk but kept OUT of
        the HEAD commit (the RCA Branch-A "incomplete commit" shape) → E1 fails →
        the handler reaches the bounded-block decision branch (mirror slice-02).
        """
        self._init_repo()
        feature = self._repo / f"at_{_SLICE_ID}.feature"
        feature.write_text(
            f"@{_SLICE_ID}\nFeature: demo\n  Scenario: s\n    Given x\n",
            encoding="utf-8",
        )
        (self._repo / "code.py").write_text("x = 1\n", encoding="utf-8")
        _git(self._repo, "add", "code.py")
        _git(
            self._repo,
            "commit",
            "--quiet",
            "-m",
            f"feat: deliver slice work\n\nSlice-Id: {_SLICE_ID}",
        )
        self._head_sha = _git(self._repo, "rev-parse", "HEAD").strip()

    def build_returning_agent_repo(self) -> None:
        """Lay out a repo a returning atdd_pure agent committed work in (AT-02).

        A seed commit + a slice-work commit carrying the `Slice-Id:` trailer so the
        slice is identified. The agent is NOT at the commit gate (an `A_GREEN`
        transcript) — it is a generic re-fired return, the stale check's host path
        (mirror slice-03 / DESIGN R-7).
        """
        self._init_repo()
        (self._repo / "code.py").write_text("x = 1\n", encoding="utf-8")
        _git(self._repo, "add", "code.py")
        _git(
            self._repo,
            "commit",
            "--quiet",
            "-m",
            f"feat: deliver slice work\n\nSlice-Id: {_SLICE_ID}",
        )
        self._head_sha = _git(self._repo, "rev-parse", "HEAD").strip()

    # --- precondition substrate (seeded through the production writer) --------

    def seed_prior_identical_blocks(self) -> None:
        """Seed N-1 (=2) prior identical `SliceCommitBlocked` records (AT-01).

        Keyed on the SAME `(slice_id, pinned_commit_sha)` the handler will resolve
        (HEAD SHA), so the bounded-block count (DDD-2b) sees exactly 2 prior
        identical blocks → the incoming hook invocation is the 3rd identical block →
        the bounded-block terminal fires (mirror slice-02). Substrate, NOT the SUT.
        """
        assert self._head_sha is not None, "build the blocking commit before seeding"
        ledger = AtCompletionLedger(_FEATURE_ID, self._repo)
        for _ in range(_PRIOR_IDENTICAL_BLOCKS):
            ledger._append_record(
                {
                    "event": "SliceCommitBlocked",
                    "slice_id": str(_SLICE_ID),
                    "pinned_commit_sha": self._head_sha,
                }
            )

    def seed_stale_progress_with_prior(self, *, prior: PriorTerminalKind) -> None:
        """Seed a STALE last-progress + a prior record of the given kind (AT-02).

        Both records carry an EXPLICIT 25-min-old timestamp (the controllable clock,
        F-13) so the most-recent ledger record is stale EITHER WAY — the only
        discriminator between the two cases is whether the prior record is a GENUINE
        terminal. Substrate, NOT the SUT.

          NON_TERMINAL_BLOCK — a regular `SliceCommitBlocked` re-fire record (NOT a
            terminal). With a stale gap and no genuine terminal, the stale check
            MUST close the stuck agent (BLOCKER-3 pin).
          GENUINE_TERMINAL — a `SliceCommitVerified` completed terminal. With a
            stale gap, the stale check MUST NOT close it (anti-vacuity pin).

        Ordering: the prior record is seeded LAST so it is the most-recent record
        (the contract's "last progress signal"), guaranteeing the gap is stale via
        the prior record's own 25-min-old timestamp regardless of which record the
        check keys on (mirror slice-03 AT-03's stale-terminal construction).
        """
        ledger = AtCompletionLedger(_FEATURE_ID, self._repo)
        ledger._append_record(
            {
                "event": "AtGreenSliceProgress",
                "slice_id": str(_SLICE_ID),
                "timestamp": _explicit_timestamp(_STALE_GAP_MINUTES),
            }
        )
        ledger._append_record(
            {
                "event": _PRIOR_EVENT_BY_KIND[prior],
                "slice_id": str(_SLICE_ID),
                "timestamp": _explicit_timestamp(_STALE_GAP_MINUTES),
            }
        )

    # --- observable port reads (re-read count deltas) ------------------------

    def _count_event(self, event: str) -> int:
        """Count durable records of `event` in the ledger (port read).

        The durable half of "loud": a not-watching operator reads the terminal
        record after the fact. The AT observes the terminal by the appearance of a
        NEW record between the before-snapshot and the after-snapshot — a
        port-exposed observable, never an internal field. Returns 0 when the ledger
        is absent / unreadable (mirror slice-03 `_read_stale_closed_count`).
        """
        ledger = AtCompletionLedger(_FEATURE_ID, self._repo)
        try:
            records = ledger.read_records()
        except Exception:
            return 0
        return sum(1 for record in records if record.get("event") == event)

    # --- driving-port invocation (the REAL hook subprocess) ------------------

    def run_bounded_block_terminal(self) -> BoundedTerminalOutcome:
        """Fire the REAL G_COMMIT bounded-block terminal; observe the durable record.

        Seeds 2 prior identical blocks, re-reads the `SliceCommitBlockedTerminal`
        count, fires the hook (the 3rd identical block → terminal), re-reads the
        count. The OBSERVABLE is the COUNT DELTA — a durable record MUST be written
        (BLOCKER-2 / R-69-A). Mirror of composition_slice_02.run_intercept +
        composition_slice_03's re-read-count-delta observable.
        """
        self.seed_prior_identical_blocks()
        terminals_before = self._count_event(_BOUNDED_TERMINAL_EVENT)
        self._write_transcript(phase="G_COMMIT")
        completed = self._fire_hook(session="watchdog-slice04-bounded")
        terminals_after = self._count_event(_BOUNDED_TERMINAL_EVENT)
        return BoundedTerminalOutcome(
            terminal_recorded=terminals_after > terminals_before,
            blocked=_blocked(completed),
        )

    def run_cross_invocation_stale_check(
        self, *, prior: PriorTerminalKind
    ) -> CrossInvocationOutcome:
        """Fire the REAL stale check against a stale agent with a prior record.

        Seeds a stale last-progress + a prior record (a non-terminal block OR a
        genuine terminal), re-reads the `StaleAgentClosed` count, fires the hook,
        re-reads the count. The OBSERVABLE is the COUNT DELTA — whether the agent
        was closed (BLOCKER-3 / R-69-B + anti-vacuity). Mirror of
        composition_slice_03.run_stale_check.
        """
        self.seed_stale_progress_with_prior(prior=prior)
        closed_before = self._count_event("StaleAgentClosed")
        self._write_transcript(phase=_RETURN_PHASE)
        completed = self._fire_hook(session="watchdog-slice04-stale")
        closed_after = self._count_event("StaleAgentClosed")
        return CrossInvocationOutcome(
            closed=closed_after > closed_before,
            blocked=_blocked(completed),
        )

    def _write_transcript(self, *, phase: str) -> None:
        """Write a transcript whose LAST atdd_pure block is a return at `phase`."""
        block = (
            "<!-- DES-VALIDATION : required -->\n"
            "<!-- DES-MODE : atdd_pure -->\n"
            f"<!-- DES-PHASE : {phase} -->\n"
            f"<!-- DES-SLICE : {_SLICE_ID} -->\n"
            f"<!-- DES-PROJECT-ID : {_FEATURE_ID} -->\n"
            f"<!-- DES-PROJECT-ROOT : {self._repo} -->\n"
        )
        line = json.dumps(
            {
                "type": "user",
                "message": {"role": "user", "content": block},
                "uuid": f"{phase.lower()}-return",
                "timestamp": "2026-06-04T10:00:00Z",
            }
        )
        self._transcript_path.write_text(line + "\n", encoding="utf-8")

    def _fire_hook(self, *, session: str) -> subprocess.CompletedProcess[str]:
        """Invoke the REAL `handle_subagent_stop` hook over its JSON protocol."""
        hook_input = json.dumps(
            {
                "session_id": session,
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
            f"sys.path.insert(0, {str(_REPO_SRC)!r}); "
            f"from {_HANDLER_MODULE} import handle_subagent_stop; "
            "sys.exit(handle_subagent_stop())"
        )
        env = dict(os.environ)
        env["PYTHONPATH"] = str(_REPO_SRC)
        return subprocess.run(
            [sys.executable, "-c", runner],
            input=hook_input,
            capture_output=True,
            text=True,
            cwd=str(self._repo),
            env=env,
            timeout=180,
        )


def _blocked(completed: subprocess.CompletedProcess[str]) -> bool:
    """True iff the hook stdout carried a `{decision:block}` body. Pure function."""
    for raw in completed.stdout.splitlines():
        line = raw.strip()
        if not line.startswith("{"):
            continue
        try:
            payload = json.loads(line)
        except json.JSONDecodeError:
            continue
        if payload.get("decision") == "block":
            return True
    return False


# prior-kind -> ledger event name. Module-level dispatch keeps
# `seed_stale_progress_with_prior` a single typed lookup with no inline control flow
# (Mandate-12 criterion 3).
_PRIOR_EVENT_BY_KIND = {
    PriorTerminalKind.NON_TERMINAL_BLOCK: _NON_TERMINAL_BLOCK_EVENT,
    PriorTerminalKind.GENUINE_TERMINAL: _GENUINE_TERMINAL_EVENT,
}


@pytest.fixture
def terminal_coherence_fixture(tmp_path) -> TerminalCoherenceFixture:
    """The single composition-root service all slice-04 step methods delegate to."""
    return TerminalCoherenceFixture(tmp_path)


@pytest.fixture
def state_04() -> dict:
    """Per-scenario scratchpad: `prior`, `outcome`, `before`."""
    return {}


__all__ = [
    "TerminalCoherenceFixture",
]
