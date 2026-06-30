"""Composition root + shared fixtures for oss-spine-watchdog slice-03.

Pillar 3 (App as in production): the SUT is the REAL SubagentStop hook stale-agent
terminal-state check — `handle_subagent_stop` invoked over its JSON stdin protocol
AS A SUBPROCESS, exactly as the shipped, proven slice-02 sibling
(`composition_slice_02.py`) drives the G_COMMIT exit gate (and the spine-hardening
sibling `tests/des/acceptance/atdd_pure_spine_hardening/steps/slice02_composition.py`
proves the real-hook port is reachable). The composition builds a real git repo
under tmp_path, writes a real atdd_pure `A_GREEN` crafter transcript (a
re-fired-without-progress return — the generic atdd_pure return path where the
stale check grafts, DESIGN R-7 / `subagent_stop_handler.py:1360`
`_handle_atdd_pure_return`), seeds the agent's LAST PROGRESS ledger record carrying
an EXPLICIT timestamp as PRECONDITION substrate through the production
`AtCompletionLedger` writer, then fires the hook and reads back whether the agent
was closed loud (a StaleAgentClosed terminal) or left alone (a normal return).

── DRIVING PORT (Mandate-13, invariant 1+2): real hook subprocess ──
The driving port is the REAL `handle_subagent_stop` SubagentStop hook, invoked over
its JSON stdin protocol AS A SUBPROCESS:
    python -c "... from ...subagent_stop_handler import handle_subagent_stop;
               sys.exit(handle_subagent_stop())"
This module NEVER does `from des.adapters.drivers.hooks.subagent_stop_handler import
_handle_atdd_pure_return` (or any direct-domain/application/adapter import) to invoke
the SUT at the test boundary — the SUT is exercised only via the hook subprocess.
`AtCompletionLedger` is imported ONLY to SEED the precondition progress / terminal
records (the S2 tolerable-variant — seed precondition state through the production
writer, same as the slice-01 / slice-02 siblings); it is substrate, NOT the SUT.

── THE CONTROLLABLE CLOCK (deterministic stale gap, NO real sleep) ──
The progress signal is the AT-completion ledger record `timestamp`
(`at_completion_ledger.py:703`). The F-13 producer-timestamp contract
(`at_completion_ledger.py:665` — "a `timestamp` already present in `fields` is
honoured") lets the AT seed a record with an EXPLICIT OLD timestamp (25 minutes ago)
so the wall-clock gap the hook computes is deterministic WITHOUT a real sleep. A
FRESH record (2 minutes ago) is seeded the same way for the no-false-positive
guardrail (AT-02). The threshold is the DESIGN OQ-4 default of 20 minutes; a 25-min
stale seed is comfortably past it and a 2-min fresh seed comfortably within it, so
the discrimination is robust to small clock jitter and needs no real time to pass.

── R1 config-SSOT surface NOT YET LANDED (the 20-min default residue) ──
DESIGN OQ-4 / D-10: slice-03 reads the stale threshold from R1's stabilized
`.nwave/config.yaml` control-plane. Confirmed empirically 2026-06-04: `.nwave/config.yaml`
EXISTS but exposes only `workflow` / `atdd_pure` / `gate` keys — there is NO
stale-threshold surface yet. So slice-03 GREEN uses the hard-coded 20-minute default
(DESIGN OQ-4) with a named R1 residue (`# TODO(R1): read from control-plane config`).
This AT seeds gaps (25 min / 2 min) that discriminate against the 20-min default,
independent of any config file — the threshold source is a DELIVER seam decision.

── THE TERMINAL ASSERTION (the load-bearing NEW behavior, RED today) ──
The generic atdd_pure return handler (`_handle_atdd_pure_return`,
`subagent_stop_handler.py:1360-1420`) today does NOT read the ledger timestamps,
does NOT compute a staleness gap, and has NO StaleAgentClosed emission — a returning
atdd_pure agent gets the NORMAL return (the SubagentStop service allow, exit 0, no
StaleAgentClosed record). So a STALE agent currently gets the same normal return as
a fresh one. AT-01 asserts the stale agent is CLOSED (a StaleAgentClosed terminal:
non-block, loud, durable record) — RED today (no close happens), GREEN once DELIVER
grafts the timestamp-gap check + threshold + StaleAgentClosed emission into
`_handle_atdd_pure_return` (DESIGN R-7). That is the slice-03 feature debt this AT
specifies.

── THE ANTI-VACUITY DISCRIMINATOR (DESIGN OQ-4 / G-3 guardrail, GREEN today) ──
AT-02 (fresh gap) + AT-03 (already-terminal) are the no-false-positive guardrail: a
check that ALWAYS closes a returning agent would wrongly close them; the current
never-close handler passes them. Together with AT-01 (which the never-close handler
fails) they bracket the contract: a closer that NEVER closes fails AT-01; one that
ALWAYS closes fails AT-02/AT-03. AT-02 forces the threshold-comparison; AT-03 forces
the no-existing-terminal precondition.

── Mechanical assertion (Mandate-13 invariant 5) ──
Python + git + filesystem only (the hook resolves a real repo + reads a real ledger
JSONL, as in production), cross-OS. The terminal is exit 0 with NO `{decision:block}`
body (DESIGN OQ-5 / DEVOPS: the terminal is loud via stderr + ledger, NEVER a
non-zero exit — a non-zero-exit assertion would invert the contract and red CI).

Universe (Mandate 8): {outcome.closed, outcome.names_staleness}. Internal fields
(Popen handle, env dict, transcript bytes, raw ledger path) NEVER appear.

Layer 3/4 (real git repo + real ledger JSONL + real hook subprocess against
tmp_path): example-only (Mandate 9 v2 — the driven set includes a real filesystem
adapter + a real git subprocess + a real hook subprocess → @real-io → example-based,
NOT PBT). Sad paths explicit (Mandate 11). No PBT machinery imported.
"""

from __future__ import annotations

import json
import subprocess
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

# Precondition-substrate writer (NOT the SUT). Seeds the agent's last-progress
# record (with an explicit OLD/FRESH timestamp) and the optional prior terminal
# record the stale check reads — the S2 tolerable-variant "seed precondition state
# through the production writer" (slice-01 / slice-02 siblings).
from des.adapters.driven.logging.at_completion_ledger import AtCompletionLedger

# The REAL `handle_subagent_stop` SubagentStop hook handler, driven IN-PROCESS
# over its stdin protocol (node-C enabler `run_hook_in_process`) —
# behaviour-identical to the prior `python -c "... handle_subagent_stop()"`
# subprocess fork, no fresh interpreter. No-argv, reads its JSON event from stdin.
from des.adapters.drivers.hooks.subagent_stop_handler import handle_subagent_stop
from tests.common.in_process_cli import run_hook_in_process

from .steps.domain_types_slice_03 import (
    FeatureId,
    ProgressAge,
    SliceId,
    StaleCheckOutcome,
    TerminalPresence,
)


_HANDLER_MODULE = "des.adapters.drivers.hooks.subagent_stop_handler"

# The feature + slice this acceptance suite builds a stale agent for.
_FEATURE_ID = FeatureId("oss-spine-watchdog-demo")
_SLICE_ID = SliceId("slice-09")

# The DESIGN OQ-4 default stale threshold = 20 minutes (R1 config-SSOT surface not
# yet landed — see module docstring). The seeded gaps straddle this default so the
# discrimination is deterministic without a real wall-clock sleep.
_THRESHOLD_MINUTES = 20
_STALE_GAP_MINUTES = 25  # > threshold → AT-01 stale agent closed
_FRESH_GAP_MINUTES = 2  # < threshold → AT-02 fresh agent left alone

# A non-gate atdd_pure phase: a re-fired-without-progress A_GREEN return routes to
# the generic `_handle_atdd_pure_return` (NOT the commit-gate / feature-end / distill
# branches), which is where the stale check grafts (DESIGN R-7).
_RETURN_PHASE = "A_GREEN"

# Staleness-naming tokens the loud StaleAgentClosed diagnostic must carry (the loud
# half of "loud → terminating", DESIGN OQ-5). The terminal must NAME why it closed
# the agent (it went stale past the threshold) — not fall silent. Recognised
# case-insensitively under any adjacent token so DELIVER has reuse-first wording
# latitude while a bare allow (empty diagnostic) cannot satisfy it.
_STALENESS_NAMING_TOKENS: tuple[str, ...] = (
    "stale",
    "staleagentclosed",
    "no progress",
    "threshold",
    "timed out",
    "timeout",
    "indeterminate",
    "closing",
    "closed",
)

# The terminal events that mean "this agent already reached a terminal state" — the
# no-double-close precondition (AT-03). A SliceCommitVerified is the "completed"
# terminal; a SliceCommitBlockedTerminal is the "blocked" terminal.
_EXISTING_TERMINAL_EVENT = "SliceCommitVerified"


def _git(repo: Path, *args: str) -> str:
    """Run a git command inside the repo and return its stdout."""
    completed = subprocess.run(
        ["git", *args], cwd=repo, capture_output=True, text=True, check=True
    )
    return completed.stdout


def _explicit_timestamp(minutes_ago: int) -> str:
    """An ISO-8601 ledger timestamp `minutes_ago` minutes before NOW.

    Mirrors the ledger writer's own format (`at_completion_ledger.py:703-705`:
    UTC ISO with the `+00:00` offset rendered as `Z`) so the seeded record is
    byte-identical in shape to a real producer record. Pure function — the
    controllable clock that makes the stale gap deterministic without a real sleep.
    """
    moment = datetime.now(timezone.utc) - timedelta(minutes=minutes_ago)
    return moment.isoformat().replace("+00:00", "Z")


def _names_staleness(diagnostic: str) -> bool:
    """Decide whether the diagnostic NAMES the stale-agent terminal reason.

    The loud half of "loud → terminating" (DESIGN OQ-5): a StaleAgentClosed
    terminal must name WHY it closed the agent (it went stale past the threshold),
    so an operator reading the durable record / stderr learns the cause — never a
    silent allow. Recognised case-insensitively under any staleness-naming token.
    Pure function.
    """
    low = diagnostic.lower()
    return any(token in low for token in _STALENESS_NAMING_TOKENS)


class StaleAgentFixture:
    """Composition-root service for oss-spine-watchdog slice-03 ATs.

    Pillar 3: builds a real git repo under tmp_path, seeds the agent's last-progress
    ledger record carrying an EXPLICIT timestamp (the controllable clock), optionally
    seeds a prior terminal record (AT-03), writes a real atdd_pure A_GREEN crafter
    transcript, then fires the SAME `handle_subagent_stop` hook the live spine fires.
    The AT observes the stale check's decision via a re-read of the ledger (was a
    StaleAgentClosed record appended?) + the hook's decision body + exit code + the
    loud diagnostic.

    Mandate-12 criterion 3: every public method is the SSOT for one piece of
    business logic. Step bodies do a typed lookup + one method call; nothing more.
    """

    def __init__(self, tmp_path: Path) -> None:
        self._repo = tmp_path / "deliver-repo"
        self._transcript_path = self._repo / "agent.jsonl"
        self._head_sha: str | None = None

    # --- repo provisioning (the seam the hook resolves its cwd against) ------

    def build_returning_agent_repo(self) -> None:
        """Lay out a real git repo a returning atdd_pure agent committed work in.

        A normal seed commit + a slice-work commit carrying the `Slice-Id:` trailer
        so the slice is identified. The agent is NOT at the commit gate (the
        transcript carries an `A_GREEN` phase) — it is a generic re-fired return,
        the path the stale check grafts onto (DESIGN R-7).

        GIT-aware (the handler resolves a real repo), isolated to tmp_path so it
        never touches the real repo.
        """
        self._repo.mkdir(parents=True, exist_ok=True)
        _git(self._repo, "init", "--quiet")
        _git(self._repo, "config", "user.email", "watchdog-slice03@example.test")
        _git(self._repo, "config", "user.name", "Watchdog Slice 03 AT")
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
        self._head_sha = _git(self._repo, "rev-parse", "HEAD").strip()

    # --- precondition substrate: the last-progress record (controllable clock) --

    def seed_last_progress(self, *, age: ProgressAge) -> None:
        """Seed the agent's LAST PROGRESS ledger record with an EXPLICIT timestamp.

        The stale check reads the most-recent ledger record `timestamp` for this
        `(feature_id, slice_id)` as the agent's last progress signal (DESIGN R-7).
        For a STALE agent the timestamp is 25 minutes ago (> 20-min threshold); for
        a FRESH agent it is 2 minutes ago (< threshold). The explicit timestamp is
        honoured by the writer (F-13, `at_completion_ledger.py:665`), so the gap is
        deterministic WITHOUT a real sleep. This is precondition state, NOT the SUT.
        """
        minutes = _GAP_BY_AGE[age]
        ledger = AtCompletionLedger(_FEATURE_ID, self._repo)
        ledger._append_record(
            {
                "event": "AtGreenSliceProgress",
                "slice_id": str(_SLICE_ID),
                "timestamp": _explicit_timestamp(minutes),
            }
        )

    # --- precondition substrate: an optional prior terminal (AT-03) ----------

    def seed_existing_terminal(self, *, presence: TerminalPresence) -> None:
        """Optionally seed a prior `completed`/`blocked` terminal for the key (AT-03).

        When `presence is PRESENT`, append a `SliceCommitVerified` (the completed
        terminal) AFTER the stale last-progress record, so the stale check sees that
        the agent ALREADY reached a terminal state and must NOT re-close it (the
        no-double-close precondition, DESIGN OQ-4). When ABSENT this is a no-op (the
        common AT-01 / AT-02 case).

        Anti-vacuity (AT-review BLOCKER fix): the terminal record carries a STALE
        timestamp (25-min-old, the SAME age as the progress record) — NOT a fresh
        one — so the MOST-RECENT ledger record (the contract's "last progress
        signal", domain_types_slice_03.py:9-14) is ALSO past the threshold. The
        computed gap is therefore > threshold whether the check keys on the progress
        record or the terminal record. This forces the no-existing-terminal
        PRECONDITION to be the ONLY thing that can withhold the close: a
        precondition-blind closer that does only `gap > threshold` would CLOSE here
        (the gap IS stale) and so RED-fail AT-03 — exactly the discrimination AT-03
        must provide. Were the terminal seeded fresh, a gap-only closer would pass
        AT-03 by leaving the agent alone for the WRONG reason (a fresh most-recent
        gap), collapsing AT-03 onto AT-02's threshold axis (the vacuity the AT-review
        blocked).
        """
        if presence is TerminalPresence.ABSENT:
            return
        ledger = AtCompletionLedger(_FEATURE_ID, self._repo)
        ledger._append_record(
            {
                "event": _EXISTING_TERMINAL_EVENT,
                "slice_id": str(_SLICE_ID),
                "timestamp": _explicit_timestamp(_STALE_GAP_MINUTES),
            }
        )

    # --- driving-port invocation (the REAL hook subprocess) ------------------

    def run_stale_check(
        self,
        *,
        age: ProgressAge,
        terminal: TerminalPresence = TerminalPresence.ABSENT,
    ) -> StaleCheckOutcome:
        """Fire the REAL SubagentStop stale check on the returning agent.

        Drives `handle_subagent_stop` over its JSON stdin protocol as a subprocess
        (the shipped slice-02 sibling pattern). The `age` arg selects the last-progress
        timestamp (stale 25 min / fresh 2 min via the controllable clock); the
        `terminal` arg optionally seeds a prior terminal (AT-03 no-double-close).

        Returns a StaleCheckOutcome capturing the port-exposed observables: whether
        a StaleAgentClosed terminal was emitted (durable ledger record + loud
        INDETERMINATE), whether the hook blocked, and whether the diagnostic names
        the staleness.
        """
        self.seed_last_progress(age=age)
        self.seed_existing_terminal(presence=terminal)
        records_before = self._read_stale_closed_count()
        self._write_a_green_transcript()
        completed = self._fire_hook()
        records_after = self._read_stale_closed_count()
        return self._interpret(completed, records_before, records_after)

    def _write_a_green_transcript(self) -> None:
        """Write a transcript whose LAST atdd_pure block is an A_GREEN return.

        An A_GREEN phase routes to the generic `_handle_atdd_pure_return`
        (NOT the commit-gate / feature-end / distill branches) — the path the stale
        check grafts onto (DESIGN R-7). Models a re-fired-without-progress agent.
        """
        block = (
            "<!-- DES-VALIDATION : required -->\n"
            "<!-- DES-MODE : atdd_pure -->\n"
            f"<!-- DES-PHASE : {_RETURN_PHASE} -->\n"
            f"<!-- DES-SLICE : {_SLICE_ID} -->\n"
            f"<!-- DES-PROJECT-ID : {_FEATURE_ID} -->\n"
            f"<!-- DES-PROJECT-ROOT : {self._repo} -->\n"
        )
        line = json.dumps(
            {
                "type": "user",
                "message": {"role": "user", "content": block},
                "uuid": "a-green-return",
                "timestamp": "2026-06-04T10:00:00Z",
            }
        )
        self._transcript_path.write_text(line + "\n", encoding="utf-8")

    def _fire_hook(self) -> subprocess.CompletedProcess[str]:
        """Invoke the REAL `handle_subagent_stop` hook over its JSON protocol."""
        hook_input = json.dumps(
            {
                "session_id": "watchdog-slice03-session",
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

    def _read_stale_closed_count(self) -> int:
        """Count durable `StaleAgentClosed` records in the ledger (port read).

        The durable half of "loud" (DEVOPS cross-env invariant 2): a not-watching
        operator reads the StaleAgentClosed record after the fact. The AT observes
        the close by the appearance of a NEW StaleAgentClosed record between the
        before-snapshot and the after-snapshot — a port-exposed observable, never an
        internal field. Returns 0 when the ledger is absent (no records yet).
        """
        ledger = AtCompletionLedger(_FEATURE_ID, self._repo)
        try:
            records = ledger.read_records()
        except Exception:
            return 0
        return sum(1 for r in records if r.get("event") == "StaleAgentClosed")

    def _interpret(
        self,
        completed: subprocess.CompletedProcess[str],
        closed_before: int,
        closed_after: int,
    ) -> StaleCheckOutcome:
        """Build the port-exposed observable outcome from the hook's surfaces."""
        blocked = False
        for raw in completed.stdout.splitlines():
            line = raw.strip()
            if not line.startswith("{"):
                continue
            try:
                payload = json.loads(line)
            except json.JSONDecodeError:
                continue
            if payload.get("decision") == "block":
                blocked = True
        terminal_recorded = closed_after > closed_before
        diagnostic = completed.stdout + completed.stderr
        return StaleCheckOutcome(
            closed=terminal_recorded,
            blocked=blocked,
            names_staleness=_names_staleness(diagnostic),
            terminal_recorded=terminal_recorded,
        )


# progress-age -> minutes-ago. Module-level dispatch keeps `seed_last_progress`
# a single typed lookup with no control flow (Mandate-12 criterion 3).
_GAP_BY_AGE = {
    ProgressAge.STALE: _STALE_GAP_MINUTES,
    ProgressAge.FRESH: _FRESH_GAP_MINUTES,
}


@pytest.fixture
def stale_agent_fixture(tmp_path) -> StaleAgentFixture:
    """The single composition-root service all slice-03 step methods delegate to."""
    return StaleAgentFixture(tmp_path)


@pytest.fixture
def state_03() -> dict:
    """Per-scenario scratchpad: `age`, `terminal`, `outcome`, `before`."""
    return {}


__all__ = [
    "StaleAgentFixture",
]
