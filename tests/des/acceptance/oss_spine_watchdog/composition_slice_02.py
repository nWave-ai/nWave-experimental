"""Composition root + shared fixtures for oss-spine-watchdog slice-02.

Pillar 3 (App as in production): the SUT is the REAL G_COMMIT exit-gate
SubagentStop intercept — `handle_subagent_stop` invoked over its JSON stdin
protocol AS A SUBPROCESS, exactly as the shipped, proven sibling
`tests/des/acceptance/atdd_pure_spine_hardening/steps/slice02_composition.py`
drives it (and the slice-01 sibling of THIS feature proves the real-hook port is
reachable). The composition builds a real git repo under tmp_path, writes a real
`G_COMMIT` crafter transcript, seeds prior `SliceCommitBlocked` records as
PRECONDITION substrate through the production `AtCompletionLedger` writer, then
fires the hook and reads back the decision body + exit code + the loud diagnostic.

Mandate-13 (invariant 1+2): the driving port is the real hook SUBPROCESS. This
module NEVER does `from des.adapters.drivers.hooks.subagent_stop_handler import
_handle_g_commit_exit_gate` (or any direct-domain/application/adapter import) to
invoke the SUT at the test boundary — the SUT is exercised only via the hook
subprocess (`python -c "... handle_subagent_stop() ..."`). `AtCompletionLedger`
is imported ONLY to SEED the precondition `SliceCommitBlocked` records (the S2
tolerable-variant — seed precondition state through the production writer, same
as both siblings); it is substrate, not the SUT.

Mandate-12 criterion 2/3: `BoundedBlockFixture` is the single source of truth for
ALL business logic the step methods need. Step bodies in
`steps_slice_02_bounded_block.py` delegate here — each body is ≤2 statements
ending in one `fixture.<method>(...)` call (or one assertion), no control flow.

DISTILL-authored RED scaffold (ADR-025) — the slice-02 NEW behaviour that does NOT
exist yet (DESIGN R-4/R-5/R-6):
  * `_emit_g_commit_ledger_event` writes `SliceCommitBlocked` with only
    `event` + `slice_id` — NO `pinned_commit_sha` field (DDD-2a not yet threaded).
  * there is NO `count_slice_commit_blocked(slice_id, pinned_commit_sha)` query
    (DDD-2b not yet added).
  * the block branch (`subagent_stop_handler.py:672-678`) re-emits
    `SliceCommitBlocked` + `{decision:block}` UNCONDITIONALLY — it never counts,
    never switches to a terminating INDETERMINATE.
So the 3rd identical block STILL emits `{decision:block}` today. AT-01 (asserting
the 3rd identical block TERMINATES — no `decision:block`) RED-fails with a SEMANTIC
assertion mismatch (`blocked` is True today, expected False) — NOT an import error
(Mandate-7 RED-vs-BROKEN preserved). AT-02 / AT-03 (asserting genuine progress
STILL `{decision:block}`s — the reset guardrail) GREEN-pass today as the
anti-vacuity regression pins: a gate that ALWAYS terminates at the 3rd block
regardless of key would red AT-02/AT-03; the current always-block gate passes them.

Layer 3/4 (real git repo + real ledger JSONL + real hook subprocess against
tmp_path): example-only (Mandate 9 v2 — @real-io because the driven set includes
a real filesystem adapter + a real git subprocess + a real hook subprocess). No
PBT machinery imported (Mandate 11 — sad paths enumerated explicitly).

── SPEED (bugfix-oss-spine-watchdog-in-memory) ──
All 3 scenarios drive the SAME downstream state machine: the bounded-block COUNT
consuming an E1-failure decision, never the gate mechanism that PRODUCES that
decision (the collection precheck / E1 / E2 subprocess forks are slice-01/05
territory — that proof stays real there). `_fire_hook` sets the production
`NWAVE_U2_FORCE_GATE_CODES` seam (`subagent_stop_handler._resolve_g_commit_gate_codes`)
so the hook still runs for real (Mandate-13 driving port unchanged) but the 3
gate-subprocess forks it would otherwise pay per invocation are replaced with the
in-memory codes "0:1:0" (precheck proceeds, E1 fails => `failed="slice-commit-
completeness"`, E2 irrelevant to that label) the real fork would have produced for
this fixture's `build_blocking_commit` shape. Same assertions, same observable
`InterceptOutcome`, no re-fork.
"""

from __future__ import annotations

import json
import os
import subprocess
from contextlib import contextmanager
from pathlib import Path

import pytest


# SPEED seam name (bugfix-oss-spine-watchdog-in-memory): mirrors the production
# `_FORCE_GATE_CODES_ENV` constant in `subagent_stop_handler.py` without importing
# it (Mandate-13 -- no direct production import at the test boundary beyond the
# tolerable substrate/observable exceptions already documented above).
_FORCE_GATE_CODES_ENV = "NWAVE_U2_FORCE_GATE_CODES"

# precheck=0 (proceed) : e1=1 (fails -- `build_blocking_commit`'s E1-incomplete
# shape) : e2=0 (irrelevant to the "failed" label once e1 != 0). The codes a real
# fork would have produced for every scenario in this family (all 3 arrange an
# E1-incomplete commit).
_FORCED_GATE_CODES = "0:1:0"


@contextmanager
def _forced_gate_codes():
    """Set/restore the production SPEED seam around one hook invocation."""
    prior = os.environ.get(_FORCE_GATE_CODES_ENV)
    os.environ[_FORCE_GATE_CODES_ENV] = _FORCED_GATE_CODES
    try:
        yield
    finally:
        if prior is None:
            os.environ.pop(_FORCE_GATE_CODES_ENV, None)
        else:
            os.environ[_FORCE_GATE_CODES_ENV] = prior


# Precondition-substrate writer (NOT the SUT). Seeds the prior SliceCommitBlocked
# records the bounded-block count reads — the S2 tolerable-variant "seed
# precondition state through the production writer" (slice-01 / slice02 siblings).
from des.adapters.driven.logging.at_completion_ledger import AtCompletionLedger

# The REAL G_COMMIT SubagentStop hook handler, driven IN-PROCESS over its stdin
# protocol (node-C enabler `run_hook_in_process`) — behaviour-identical to the
# prior `python -c "... handle_subagent_stop()"` subprocess fork, no fresh
# interpreter. The handler is no-argv and reads its JSON event from sys.stdin.
from des.adapters.drivers.hooks.subagent_stop_handler import handle_subagent_stop
from tests.common.in_process_cli import run_hook_in_process

from .steps.domain_types_slice_02 import (
    BlockProgress,
    FeatureId,
    InterceptOutcome,
    SliceId,
)


# Repo root = .../nWave-dev (this file lives 4 dirs deep under tests/des/...).
_HANDLER_MODULE = "des.adapters.drivers.hooks.subagent_stop_handler"

# The feature + slice this acceptance suite builds blocks for. A real
# `@slice-NN`-tagged `.feature` file is authored on disk (but kept OUT of the
# commit) so E1 (slice-commit completeness) FAILS — the block branch is reached.
_FEATURE_ID = FeatureId("oss-spine-watchdog-demo")
_SLICE_ID = SliceId("slice-07")

# The bound: terminate ON the 3rd identical block (DISCUSS D-4 / DESIGN OQ-3 —
# "terminate ON the 3rd identical block", so 2 ordinary blocks precede it). The
# AT seeds N-1 prior identical blocks, then drives the hook once: that single
# invocation IS the Nth (3rd) block.
_N_BOUND = 3
_PRIOR_IDENTICAL_BLOCKS = _N_BOUND - 1  # = 2

# A bound-naming token the loud INDETERMINATE diagnostic must carry (DISCUSS KPI-2
# / "loud → terminating"). The terminal must NAME why it terminated — that it hit
# the bounded-block limit — not merely fall silent. Recognised case-insensitively
# under any of these adjacent tokens so DELIVER has reuse-first wording latitude
# while a bare allow (empty diagnostic) cannot satisfy it.
_BOUND_NAMING_TOKENS: tuple[str, ...] = (
    "bounded",
    "indeterminate",
    "identical block",
    "max attempts",
    "no progress",
    "re-fire",
    "terminat",
)


def _git(repo: Path, *args: str) -> str:
    """Run a git command inside the repo and return its stdout."""
    completed = subprocess.run(
        ["git", *args], cwd=repo, capture_output=True, text=True, check=True
    )
    return completed.stdout


def _names_bound(diagnostic: str) -> bool:
    """Decide whether the diagnostic NAMES the bounded-block terminal reason.

    The loud half of "loud → terminating" (DESIGN OQ-5): a terminating
    INDETERMINATE must name WHY it terminated (it hit the N=3 identical-block
    bound), so an operator reading the durable record / stderr learns the cause —
    never a silent allow. Recognised case-insensitively under any bound-naming
    token. Pure function.
    """
    low = diagnostic.lower()
    return any(token in low for token in _BOUND_NAMING_TOKENS)


class BoundedBlockFixture:
    """Composition-root service for oss-spine-watchdog slice-02 ATs.

    Pillar 3: builds a real git repo under tmp_path, authors the slice's
    `.feature` AT on disk but keeps it OUT of the HEAD commit (so E1 fails and the
    block branch is reached), seeds N-1 prior identical `SliceCommitBlocked`
    records keyed on `(slice_id, pinned_commit_sha)` through the production ledger
    writer, then fires the SAME `handle_subagent_stop` hook the live spine fires.
    The AT observes the intercept's decision via the hook's stdout decision body +
    exit code + the loud diagnostic.

    Mandate-12 criterion 3: every public method is the SSOT for one piece of
    business logic. Step bodies do a typed lookup + one method call; nothing more.
    """

    def __init__(self, tmp_path: Path) -> None:
        self._repo = tmp_path / "deliver-repo"
        self._transcript_path = self._repo / "agent.jsonl"
        self._head_sha: str | None = None

    # --- repo + commit provisioning (the seam E1 interrogates) ---------------

    def build_blocking_commit(self) -> None:
        """Lay out a real git repo whose HEAD commit FAILS the E1 exit gate.

        The slice's `@slice-NN` `.feature` AT is authored on disk but kept OUT of
        the HEAD commit (the RCA Branch-A "incomplete commit" shape) → E1
        (slice-commit completeness) fails → the handler reaches the
        `SliceCommitBlocked` + `{decision:block}` branch (the slice-02 seam). The
        commit STILL carries the `Slice-Id:` trailer so the slice is identified.

        GIT-aware (a real `git rev-parse HEAD` is what the handler pins), isolated
        to tmp_path so it never touches the real repo.
        """
        self._repo.mkdir(parents=True, exist_ok=True)
        _git(self._repo, "init", "--quiet")
        _git(self._repo, "config", "user.email", "watchdog-slice02@example.test")
        _git(self._repo, "config", "user.name", "Watchdog Slice 02 AT")
        (self._repo / "README.md").write_text("seed\n", encoding="utf-8")
        _git(self._repo, "add", "README.md")
        _git(self._repo, "commit", "--quiet", "-m", "chore: seed")
        # Author the slice AT on disk but DO NOT stage it → E1 incomplete.
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

    # --- precondition substrate: prior identical blocks ----------------------

    def seed_prior_identical_blocks(self) -> None:
        """Seed N-1 (=2) prior identical `SliceCommitBlocked` records (substrate).

        Each seeded record is keyed on the SAME `(slice_id, pinned_commit_sha)`
        the handler will resolve when it runs against this repo (HEAD SHA), so the
        bounded-block count (DDD-2b) sees exactly 2 prior identical blocks. The
        incoming hook invocation is then the 3rd identical block → the terminal
        must fire (DISCUSS D-4 / DESIGN OQ-3, "terminate ON the 3rd").

        Seeded through the production `AtCompletionLedger` writer carrying a
        `pinned_commit_sha` extra field (the `verdict_hash` precedent — extra
        fields are hashed into `record_hash`; DDD-2a). This is precondition state,
        NOT the SUT.
        """
        self._seed_blocks(count=_PRIOR_IDENTICAL_BLOCKS, pinned_sha=self._head_sha)

    def _seed_blocks(self, *, count: int, pinned_sha: str | None) -> None:
        """Append `count` `SliceCommitBlocked` records for the key (substrate)."""
        assert pinned_sha is not None, "build the blocking commit before seeding"
        ledger = AtCompletionLedger(_FEATURE_ID, self._repo)
        for _ in range(count):
            ledger._append_record(
                {
                    "event": "SliceCommitBlocked",
                    "slice_id": str(_SLICE_ID),
                    "pinned_commit_sha": pinned_sha,
                }
            )

    def amend_head_commit(self) -> None:
        """Amend HEAD → a NEW pinned SHA, so the incoming block's key differs.

        Models genuine progress (DISCUSS D-4): the agent amended its commit
        mid-loop. The 2 seeded prior blocks are keyed on the OLD SHA; the handler
        now resolves a NEW HEAD SHA → a fresh count key starting at 0 → the
        bounded-block terminal must NOT fire (the handler must still
        `{decision:block}`). The amended commit stays E1-incomplete (the AT file
        is still unstaged) so the block branch is still reached.
        """
        (self._repo / "code.py").write_text("x = 2\n", encoding="utf-8")
        _git(self._repo, "add", "code.py")
        _git(self._repo, "commit", "--quiet", "--amend", "--no-edit")
        self._head_sha = _git(self._repo, "rev-parse", "HEAD").strip()

    # --- driving-port invocation (the REAL hook subprocess) ------------------

    def run_intercept(self, *, progress: BlockProgress) -> InterceptOutcome:
        """Fire the REAL G_COMMIT SubagentStop intercept on the blocking commit.

        Drives `handle_subagent_stop` over its JSON stdin protocol as a subprocess
        (the shipped sibling pattern). The `progress` arg selects the arriving
        block's relationship to the seeded prior blocks:

          IDENTICAL  — seed 2 prior blocks for the current HEAD; fire → 3rd
                       identical block → terminal expected (AT-01).
          NEW_SHA    — seed 2 prior blocks for the current HEAD, THEN amend HEAD
                       (new SHA); fire → fresh key → re-fire expected (AT-02).
          NEW_REASON — seed 2 prior blocks with a DIFFERENT block reason for the
                       current HEAD; fire → reason differs → reset → re-fire
                       expected (AT-03).

        Returns an InterceptOutcome capturing the port-exposed observables: whether
        the hook emitted a `{decision:block}` body (re-fire) or none (terminating
        INDETERMINATE), the decision event, and the loud diagnostic text.
        """
        self._arrange_progress(progress)
        self._write_g_commit_transcript()
        completed = self._fire_hook()
        return self._interpret(completed)

    def _arrange_progress(self, progress: BlockProgress) -> None:
        """Arrange the seeded-blocks / commit topology for the progress case."""
        _ARRANGERS[progress](self)

    def _arrange_identical(self) -> None:
        self.seed_prior_identical_blocks()

    def _arrange_new_sha(self) -> None:
        self.seed_prior_identical_blocks()
        self.amend_head_commit()

    def _arrange_new_reason(self) -> None:
        # Seed 2 prior blocks carrying a DIFFERENT reason token for the SAME key.
        # The incoming block (E1 slice-commit-completeness) differs in reason from
        # these E2-flavoured priors → the bounded-block count for the *identical*
        # reason is 0 → no terminal (DISCUSS D-4: a different reason resets).
        assert self._head_sha is not None
        ledger = AtCompletionLedger(_FEATURE_ID, self._repo)
        for _ in range(_PRIOR_IDENTICAL_BLOCKS):
            ledger._append_record(
                {
                    "event": "SliceCommitBlocked",
                    "slice_id": str(_SLICE_ID),
                    "pinned_commit_sha": self._head_sha,
                    "block_reason": "contract-gate",
                }
            )

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

    def _fire_hook(self) -> subprocess.CompletedProcess[str]:
        """Invoke the REAL `handle_subagent_stop` hook over its JSON protocol.

        SPEED (bugfix-oss-spine-watchdog-in-memory): wrapped in
        `_forced_gate_codes()` so the handler's precheck/E1/E2 subprocess forks
        are replaced with the in-memory codes this fixture's E1-incomplete commit
        shape would have produced for real — the hook itself still runs (the
        driving port is unchanged), only the 3 nested gate-subprocess forks it
        would otherwise pay per invocation are skipped.
        """
        hook_input = json.dumps(
            {
                "session_id": "watchdog-slice02-session",
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
        with _forced_gate_codes():
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

    def _interpret(
        self, completed: subprocess.CompletedProcess[str]
    ) -> InterceptOutcome:
        """Build the port-exposed observable outcome from the hook's surfaces."""
        decision_event: str | None = None
        blocked = False
        reason = ""
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
                decision_event = payload.get("event")
                reason = str(payload.get("reason", ""))
        diagnostic = reason if blocked else (completed.stdout + completed.stderr)
        return InterceptOutcome(
            blocked=blocked,
            decision_event=decision_event,
            diagnostic=diagnostic,
            names_bound=_names_bound(diagnostic),
        )


# progress -> arrange method. Module-level dispatch keeps `_arrange_progress`
# a single typed lookup with no control flow (Mandate-12 criterion 3).
_ARRANGERS = {
    BlockProgress.IDENTICAL: BoundedBlockFixture._arrange_identical,
    BlockProgress.NEW_SHA: BoundedBlockFixture._arrange_new_sha,
    BlockProgress.NEW_REASON: BoundedBlockFixture._arrange_new_reason,
}


@pytest.fixture
def bounded_block_fixture(tmp_path) -> BoundedBlockFixture:
    """The single composition-root service all slice-02 step methods delegate to."""
    return BoundedBlockFixture(tmp_path)


@pytest.fixture
def state_02() -> dict:
    """Per-scenario scratchpad: `progress`, `outcome`, `before`."""
    return {}


__all__ = [
    "BoundedBlockFixture",
]
