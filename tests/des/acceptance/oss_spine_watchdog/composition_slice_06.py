"""Composition root + shared fixtures for oss-spine-watchdog slice-06.

Pillar 3 (App as in production): the SUT is the REAL `handle_subagent_stop`
G_COMMIT exit-gate SubagentStop hook, invoked over its JSON stdin protocol AS A
SUBPROCESS, exactly as the shipped, proven slice-02 sibling
(`composition_slice_02.py`, the bounded-block terminal) and slice-05 sibling
(`composition_slice_05.py`, the collection-precheck gate-wiring) drive it. Slice-06
closes residue R-69-F (the timeout-countability gap) surfaced by the feature-end
deep review (`a01511d9`).

── THE DEFECT (R-69-F) ──
`_handle_g_commit_exit_gate`'s `except subprocess.TimeoutExpired` path
(`subagent_stop_handler.py:1047-1052`) emits a FIELDLESS `SliceCommitBlocked`:

    except subprocess.TimeoutExpired as exc:
        _emit_g_commit_ledger_event(resolved, "SliceCommitBlocked")   # no fields
        return _emit_atdd_pure_block(..., "GateInvocationTimeout")

The NORMAL block path (`:1036-1041`) emits `SliceCommitBlocked` WITH
`pinned_commit_sha=pinned_sha` + `block_reason=failed`, so the bounded-block count
(`count_slice_commit_blocked`, keyed on `(slice_id, pinned_commit_sha,
block_reason)`) matches identical-key priors and terminates at N=3. The TIMEOUT
path's FIELDLESS record can NEVER match that key → a timeout-driven re-fire loop on
the SAME commit is UNCOUNTABLE → the N=3 bound is DEFEATED for timeout-originated
blocks (backstopped only by slice-03's coarse stale-timeout).

GREEN target: thread `pinned_commit_sha=pinned_sha` (already resolved at
`:933`) + `block_reason="gate-timeout"` into the timeout emit, so identical timeout
blocks on `(slice, sha, "gate-timeout")` count toward N=3 and the bounded-block
terminal fires on the 3rd.

── DRIVING PORT (Mandate-13, invariant 1+2): real hook subprocess ──
Slice-06 drives the REAL G_COMMIT exit-gate hook:

    python -c "... from ...subagent_stop_handler import handle_subagent_stop;
               sys.exit(handle_subagent_stop())"

against a real git repo under tmp_path, with the gate subprocess forced to TIME OUT
via the production timeout-fault seam `NWAVE_U2_FORCE_GATE_TIMEOUT=1` — the
GREEN-added sibling of the existing `NWAVE_U2_FORCE_HANDLER_FAULT` test seam
(`subagent_stop_handler.py:917`, already driven through the real hook subprocess by
the `atdd_pure_spine_hardening` slice02/slice04 compositions). The seam raises a
real `subprocess.TimeoutExpired` from inside the gate try-block, exercising the REAL
`except subprocess.TimeoutExpired` branch DETERMINISTICALLY and FAST — NOT a 120s
sleep (a real-timeout test against the 120s `G_COMMIT_GATE_SUBPROCESS_TIMEOUT_SECONDS`
constant would be too slow, and the constant has no env override; the fault seam is
the realistic injection point the composition machinery supports). The seam selects
a production code branch — the SUT is still exercised ONLY via the hook subprocess.

This module NEVER does `from des.adapters.drivers.hooks.subagent_stop_handler import
_handle_g_commit_exit_gate` (or any direct-domain/application/adapter import) to
invoke the SUT at the test boundary. `AtCompletionLedger` is imported ONLY to SEED
the 2 prior `(slice, sha, "gate-timeout")` blocks + RE-READ the durable terminal
records the assertions observe (the S2 tolerable-variant — seed/observe through the
production writer/reader); it is substrate + the observable port surface, NOT the
SUT.

── THE DIVERGENCE PAIR (the anti-vacuity discriminator) ──
  THIRD_IDENTICAL_TIMEOUT — seed 2 prior `(slice, sha, "gate-timeout")` blocks,
    then force the gate to time out a 3rd time on the SAME key. The 3rd identical
    timeout block → the bounded-block terminal must fire (a durable
    `SliceCommitBlockedTerminal` + non-block return).
      RED TODAY: the timeout emit is fieldless → the 2 seeded fielded priors + the
      fieldless 3rd never reach count==N-1 on a MATCHING `(slice, sha,
      "gate-timeout")` key → `_prior_identical_block_count` returns 0 → no terminal
      → a `{decision:block}` re-fire. So `terminated` is False (no genuine-terminal
      record) and `blocked` is True. SEMANTIC mismatch (`set_to(True)` expected for
      `terminated`, False observed), NOT an import error (Mandate-7 RED-vs-BROKEN
      preserved).
      GREEN: the timeout emit threads `pinned_commit_sha` + `block_reason=
      "gate-timeout"` → the count matches the 2 seeded priors → count==N-1=2 → the
      bounded-block terminal fires (durable `SliceCommitBlockedTerminal` +
      non-block).

  FIRST_TIMEOUT_NO_PRIORS — no priors seeded; force the gate to time out once. The
    bounded-block count is 0 (< N-1=2) → the gate takes the ORDINARY block path (a
    `{decision:block}` re-fire), NOT a terminal.
      GREEN TODAY and MUST STAY GREEN: today's fieldless emit re-blocks (count 0);
      post-GREEN the fielded emit still has count 0 for a first timeout → ordinary
      block. A count-blind fix that terminated EVERY timeout would wrongly terminate
      this first timeout → this pin would RED. The discriminator pins the terminal
      is keyed on the Nth identical timeout, nothing else.

── Mechanical assertion (Mandate-13 invariant 5) ──
Python + git + filesystem only, cross-OS. The terminal is exit 0 with NO
`{decision:block}` body (DESIGN OQ-5 / DV-5). The durable-record observable is a
re-read count delta over the GENUINE-terminal event set (EXCLUDING the non-terminal
`SliceCommitBlocked` re-fire record) — a port-exposed observable, never an internal
field.

Universe (Mandate 8): {outcome.terminated, outcome.blocked}. Internal plumbing
(Popen handle, env dict, transcript bytes, raw ledger path) NEVER appears.

Layer 3/4 (real git repo + real ledger JSONL + forced-timeout real hook subprocess
against tmp_path): example-only (Mandate 9 v2 — @real-io because the driven set
includes a real filesystem adapter + a real git subprocess + a real hook subprocess
→ NOT PBT; Mandate 11 — sad paths enumerated explicitly). No PBT machinery imported.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

# Precondition-substrate writer + observable-record reader (NOT the SUT). Seeds the
# prior `(slice, sha, "gate-timeout")` SliceCommitBlocked records the bounded-block
# count reads, and re-reads the durable terminal records the assertions observe —
# the S2 tolerable-variant "seed/observe through the production writer/reader"
# (slice-02 / slice-04 / slice-05 siblings).
from des.adapters.driven.logging.at_completion_ledger import AtCompletionLedger

from .steps.domain_types_slice_06 import (
    FeatureId,
    GateOutcome,
    SliceId,
    TimeoutBlockHistory,
)


# Repo root = .../nWave-dev (this file lives 4 dirs deep under tests/des/...).
_REPO_ROOT = Path(__file__).resolve().parents[4]
_REPO_SRC = _REPO_ROOT / "src"

_HANDLER_MODULE = "des.adapters.drivers.hooks.subagent_stop_handler"

# The feature + slice this acceptance suite builds gate invocations for.
_FEATURE_ID = FeatureId("oss-spine-watchdog-demo")
_SLICE_ID = SliceId("slice-13")

# The bound: terminate ON the Nth identical block (DISCUSS D-4 / DESIGN OQ-3), so
# N-1 priors precede the terminating invocation. N=3.
_N_BOUND = 3
_PRIOR_IDENTICAL_TIMEOUTS = _N_BOUND - 1  # = 2

# The block reason a TIMEOUT-originated block must carry so it is COUNTABLE on the
# same `(slice, sha, block_reason)` key as the ordinary block path (R-69-F GREEN
# target). The AT seeds its priors with THIS reason and asserts the 3rd forced
# timeout terminates — pinning the timeout emit threads exactly this reason.
_TIMEOUT_BLOCK_REASON = "gate-timeout"

# The test-only env seam that forces a real `subprocess.TimeoutExpired` from inside
# the gate try-block (the GREEN-added sibling of `NWAVE_U2_FORCE_HANDLER_FAULT` at
# `subagent_stop_handler.py:917`). Exercises the REAL `except subprocess
# .TimeoutExpired` branch deterministically + fast — no 120s sleep.
_FORCE_GATE_TIMEOUT_ENV = "NWAVE_U2_FORCE_GATE_TIMEOUT"

# The genuine-terminal event set — a durable record in this set means the gate
# TERMINATED (not re-blocked). The bounded-block terminal routes through the
# slice-04 shared `_emit_terminating_indeterminate`, writing a durable
# `SliceCommitBlockedTerminal`. The non-terminal `SliceCommitBlocked` re-fire record
# is DELIBERATELY EXCLUDED — observing it as a "terminal" would be the exact
# BLOCKER-3 false-positive slice-04 fixed.
_GENUINE_TERMINAL_EVENTS = frozenset(
    {"SliceCommitBlockedTerminal", "StaleAgentClosed", "CollectionCrashTerminal"}
)


def _git(repo: Path, *args: str) -> str:
    """Run a git command inside the repo and return its stdout."""
    completed = subprocess.run(
        ["git", *args], cwd=repo, capture_output=True, text=True, check=True
    )
    return completed.stdout


class TimeoutCountabilityFixture:
    """Composition-root service for oss-spine-watchdog slice-06 ATs.

    Pillar 3: builds a real git repo under tmp_path whose HEAD commit reaches the
    G_COMMIT exit gate, optionally seeds N-1 prior `(slice, sha, "gate-timeout")`
    blocks through the production `AtCompletionLedger` writer, then fires the SAME
    `handle_subagent_stop` G_COMMIT exit-gate hook the live spine fires — with the
    gate subprocess FORCED TO TIME OUT (the `NWAVE_U2_FORCE_GATE_TIMEOUT` seam). The
    AT observes the gate's decision via a re-read of the ledger (was a durable
    GENUINE-terminal record appended?) + the hook's decision body (was it a non-block
    return?).

    Mandate-12 criterion 3: every public method is the SSOT for one piece of business
    logic. Step bodies do a typed lookup + one method call; nothing more.
    """

    def __init__(self, tmp_path: Path) -> None:
        self._repo = tmp_path / "deliver-repo"
        self._transcript_path = self._repo / "agent.jsonl"
        self._head_sha: str | None = None

    # --- repo + commit provisioning (the seam the gate interrogates) ---------

    def build_commit(self) -> None:
        """Lay out a real git repo whose HEAD commit reaches the G_COMMIT gate.

        Mirrors the slice-02 sibling: a seed commit, then a slice commit carrying a
        `Slice-Id:` trailer (so the slice is identified). The exact E1/E2 verdict is
        irrelevant here — the gate subprocess is FORCED TO TIME OUT before any E1/E2
        code is read (the `NWAVE_U2_FORCE_GATE_TIMEOUT` seam raises inside the try
        block), so the handler enters the `except subprocess.TimeoutExpired` branch
        regardless of the commit's gate outcome.

        GIT-aware (a real `git rev-parse HEAD` is what the handler pins as
        `pinned_sha`), isolated to tmp_path so it never touches the real repo.
        """
        self._repo.mkdir(parents=True, exist_ok=True)
        _git(self._repo, "init", "--quiet")
        _git(self._repo, "config", "user.email", "watchdog-slice06@example.test")
        _git(self._repo, "config", "user.name", "Watchdog Slice 06 AT")
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

    # --- precondition substrate: prior identical timeout blocks --------------

    def seed_prior_identical_timeout_blocks(self) -> None:
        """Seed N-1 (=2) prior identical `(slice, sha, "gate-timeout")` blocks.

        Each seeded record is keyed on the SAME `(slice_id, pinned_commit_sha)` the
        handler will resolve when it runs against this repo (HEAD SHA) AND carries
        `block_reason="gate-timeout"` — so the bounded-block count (DDD-2b) sees
        exactly 2 prior identical TIMEOUT blocks. The incoming forced-timeout
        invocation is then the 3rd identical timeout block → the terminal must fire
        (DISCUSS D-4 / DESIGN OQ-3, "terminate ON the 3rd").

        Seeded through the production `AtCompletionLedger` writer carrying the
        `pinned_commit_sha` + `block_reason` extra fields (the `verdict_hash`
        precedent — extra fields are hashed into `record_hash`; DDD-2a). This is
        precondition state, NOT the SUT.
        """
        assert self._head_sha is not None, "build the commit before seeding"
        ledger = AtCompletionLedger(_FEATURE_ID, self._repo)
        for _ in range(_PRIOR_IDENTICAL_TIMEOUTS):
            ledger._append_record(
                {
                    "event": "SliceCommitBlocked",
                    "slice_id": str(_SLICE_ID),
                    "pinned_commit_sha": self._head_sha,
                    "block_reason": _TIMEOUT_BLOCK_REASON,
                }
            )

    # --- observable port reads (re-read count deltas) ------------------------

    def _count_genuine_terminals(self) -> int:
        """Count durable GENUINE-terminal records in the ledger (port read).

        A genuine-terminal record means the gate TERMINATED. EXCLUDES the
        non-terminal `SliceCommitBlocked` re-fire record (observing it as a terminal
        would be the BLOCKER-3 false-positive). Returns 0 when the ledger is absent /
        unreadable (mirror slice-04 / slice-05 `_count_*`).
        """
        ledger = AtCompletionLedger(_FEATURE_ID, self._repo)
        try:
            records = ledger.read_records()
        except Exception:
            return 0
        return sum(
            1 for record in records if record.get("event") in _GENUINE_TERMINAL_EVENTS
        )

    # --- driving-port invocation (the REAL forced-timeout hook subprocess) ---

    def run_forced_timeout_gate(self, *, history: TimeoutBlockHistory) -> GateOutcome:
        """Fire the REAL G_COMMIT gate with the subprocess forced to time out.

        Builds the commit, seeds 2 prior identical timeout blocks IFF the history is
        THIRD_IDENTICAL_TIMEOUT (else no priors), re-reads the genuine-terminal
        count, fires the hook with `NWAVE_U2_FORCE_GATE_TIMEOUT=1` (a real
        `subprocess.TimeoutExpired`), re-reads the count. The OBSERVABLE is the COUNT
        DELTA (did the gate write a durable terminal?) + whether the hook returned a
        `{decision:block}` body (did it re-fire?). Mirror of
        composition_slice_05.run_g_commit_gate's re-read-count-delta observable +
        composition_slice_02's non-block read.
        """
        self.build_commit()
        _SEED_FOR_HISTORY[history](self)
        terminals_before = self._count_genuine_terminals()
        self._write_g_commit_transcript()
        completed = self._fire_hook(session="watchdog-slice06")
        terminals_after = self._count_genuine_terminals()
        return GateOutcome(
            terminated=terminals_after > terminals_before,
            blocked=_blocked(completed),
        )

    def _seed_third_identical(self) -> None:
        self.seed_prior_identical_timeout_blocks()

    def _seed_none(self) -> None:
        # FIRST_TIMEOUT_NO_PRIORS: no prior timeout blocks → count 0 → ordinary block.
        pass

    def _write_g_commit_transcript(self) -> None:
        """Write a transcript whose LAST atdd_pure block is a G_COMMIT return."""
        block = (
            "<!-- DES-VALIDATION : required -->\n"
            "<!-- DES-MODE : atdd_pure -->\n"
            "<!-- DES-PHASE : G_COMMIT -->\n"
            f"<!-- DES-SLICE : {_SLICE_ID} -->\n"
            f"<!-- DES-PROJECT-ID : {_FEATURE_ID} -->\n"
            f"<!-- DES-PROJECT-ROOT : {self._repo} -->\n"
        )
        line = json.dumps(
            {
                "type": "user",
                "message": {"role": "user", "content": block},
                "uuid": "g-commit-return",
                "timestamp": "2026-06-04T10:00:00Z",
            }
        )
        self._transcript_path.write_text(line + "\n", encoding="utf-8")

    def _fire_hook(self, *, session: str) -> subprocess.CompletedProcess[str]:
        """Invoke the REAL `handle_subagent_stop` hook with the gate forced to time out.

        `NWAVE_U2_FORCE_GATE_TIMEOUT=1` makes the production gate path raise a real
        `subprocess.TimeoutExpired` from inside the try-block, so the REAL `except
        subprocess.TimeoutExpired` branch (the R-69-F defect site) fires — without a
        120s sleep. The hook resolves its own repo + ledger from the transcript
        context (slice-02 / slice-05 sibling pattern).
        """
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
        env[_FORCE_GATE_TIMEOUT_ENV] = "1"
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


# history -> seed method. Module-level dispatch keeps the seeding selection a single
# typed lookup with no control flow (Mandate-12 criterion 3).
_SEED_FOR_HISTORY = {
    TimeoutBlockHistory.THIRD_IDENTICAL_TIMEOUT: (
        TimeoutCountabilityFixture._seed_third_identical
    ),
    TimeoutBlockHistory.FIRST_TIMEOUT_NO_PRIORS: TimeoutCountabilityFixture._seed_none,
}


@pytest.fixture
def timeout_countability_fixture(tmp_path) -> TimeoutCountabilityFixture:
    """The single composition-root service all slice-06 step methods delegate to."""
    return TimeoutCountabilityFixture(tmp_path)


@pytest.fixture
def state_06() -> dict:
    """Per-scenario scratchpad: `history`, `outcome`, `before`."""
    return {}


__all__ = [
    "TimeoutCountabilityFixture",
]
