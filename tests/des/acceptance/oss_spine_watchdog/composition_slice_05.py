"""Composition root + shared fixtures for oss-spine-watchdog slice-05.

Pillar 3 (App as in production): the SUT is the REAL `handle_subagent_stop`
G_COMMIT exit-gate SubagentStop hook, invoked over its JSON stdin protocol AS A
SUBPROCESS, exactly as the shipped, proven slice-02 sibling (`composition_slice_02.py`,
the G_COMMIT bounded-block terminal) and slice-04 sibling (`composition_slice_04.py`,
the terminal-coherence fix) drive it. Slice-05 is the LAST slice — it closes
BLOCKER-1 of the deep feature-end review (`a360758f`, 2026-06-05): slice-01 shipped
the collection-precheck PROBE but the gate handler NEVER CALLS it, so a real
collection crash on the live spine STILL re-fires the agent (the #68 loop the
walking-skeleton exists to kill is NOT killed on the production hot path).

── DRIVING PORT (Mandate-13, invariant 1+2): real hook subprocess (THE AT-tier fix) ──
This is the EXACT defect BLOCKER-1 is about — slice-01's ATs drove the `--collect-only`
PROBE DIRECTLY (the wrong tier), asserting the probe names a module rather than that
the GATE INVOKES the probe. Slice-05 drives the REAL G_COMMIT exit-gate hook:

    python -c "... from ...subagent_stop_handler import handle_subagent_stop;
               sys.exit(handle_subagent_stop())"

against a real git repo under tmp_path whose COMMITTED contract suite crashes on
collection (a committed import-time-crashing test module). The OBSERVABLE is that the
REAL GATE terminates (a durable terminal record + a non-block return), NOT that the
probe in isolation names a module. This module NEVER does `from
des.adapters.drivers.hooks.subagent_stop_handler import _handle_g_commit_exit_gate`
(or any direct domain/application/adapter import) to invoke the SUT at the test
boundary — the SUT is exercised ONLY via the hook subprocess. `AtCompletionLedger`
is imported ONLY to RE-READ the durable terminal/block records the assertions observe
(the S2 tolerable-variant — observe observable state through the production reader);
it is the observable port surface, NOT the SUT.

── THE DIVERGENCE PAIR (the anti-vacuity discriminator) ──
  COLLECTION_CRASHES — a real git repo whose COMMITTED contract suite carries an
    import-time-crashing test module (isolated to tmp_path — the SHAPE, not the
    BLAST RADIUS). The real `run_contract_gate --collect-only` precheck (when wired)
    returns exit 2 → the gate TERMINATES (durable terminal record + non-block).
      RED TODAY: `_handle_g_commit_exit_gate` runs NO precheck before E2 (grep
      `collect-only|precheck` in the handler = 0). The crash flows into E2
      (`run_contract_gate --verify-gate-scope`) → exit non-zero → the block branch
      → a `SliceCommitBlocked` re-fire record + `{decision:block}`. So `terminated`
      is False (no genuine-terminal record written — only the non-terminal block) and
      `blocked` is True (the crash re-blocks → re-fire). SEMANTIC mismatch
      (`set_to(True)` expected for `terminated`, False observed), NOT an import error
      (Mandate-7 RED-vs-BROKEN preserved).
      GREEN: the EXTEND runs `run_contract_gate --collect-only` (NWAVE_FRESHNESS-
      cleared, D-7) BEFORE E2; exit 2 → terminate via the slice-04 shared
      `_emit_terminating_indeterminate` (a durable terminal record + loud stderr +
      non-block), short-circuiting before E2 re-blocks.

  COLLECTS_CLEAN — a real git repo whose COMMITTED contract suite collects cleanly,
    whose commit still fails E1/E2 for an ORDINARY reason (no `Gate-Scope:` trailer →
    E2 exit 1). The collection precheck does NOT fire the collection terminal — the
    gate proceeds to the ORDINARY block path.
      GREEN TODAY and MUST STAY GREEN: today the ordinary block path is unchanged
      (no precheck); post-GREEN the precheck on a cleanly-collecting suite (exit 0)
      lets the gate proceed to E1/E2, which block normally (`terminated` False,
      `blocked` True). A collection-blind precheck that terminated EVERY commit would
      wrongly collection-terminate this clean commit → this pin would RED. The
      discriminator pins the terminal is keyed on a COLLECTION CRASH (exit 2),
      nothing else.

── Mechanical assertion (Mandate-13 invariant 5) ──
Python + git + filesystem only (the hook resolves a real repo + the real precheck
collects a real synthetic suite + reads/writes a real ledger JSONL, as in
production), cross-OS. The terminal is exit 0 with NO `{decision:block}` body (DESIGN
OQ-5 / DV-5). The durable-record observable is a re-read count delta over the
GENUINE-terminal event set (EXCLUDING the non-terminal `SliceCommitBlocked` re-fire
record) — a port-exposed observable, never an internal field.

Universe (Mandate 8): {outcome.terminated, outcome.blocked}. Internal plumbing
(Popen handle, env dict, transcript bytes, raw ledger path) NEVER appears.

Layer 3/4 (real git repo + real ledger JSONL + real collection-precheck subprocess +
real hook subprocess against tmp_path): example-only (Mandate 9 v2 — @real-io because
the driven set includes a real filesystem adapter + a real git subprocess + a real
hook subprocess → NOT PBT; Mandate 11 — sad paths enumerated explicitly). No PBT
machinery imported.
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest

# Observable-record reader (NOT the SUT). Re-reads the durable terminal / block
# records the assertions observe — the S2 tolerable-variant "observe observable
# state through the production reader" (slice-02 / slice-03 / slice-04 siblings).
from des.adapters.driven.logging.at_completion_ledger import AtCompletionLedger

# The REAL `handle_subagent_stop` SubagentStop hook handler, driven IN-PROCESS
# over its stdin protocol (node-C enabler `run_hook_in_process`) —
# behaviour-identical to the prior `python -c "... handle_subagent_stop()"`
# subprocess fork, no fresh interpreter. No-argv, reads its JSON event from stdin.
from des.adapters.drivers.hooks.subagent_stop_handler import handle_subagent_stop
from tests.common.in_process_cli import run_hook_in_process

from .steps.domain_types_slice_05 import (
    FeatureId,
    GateOutcome,
    SliceId,
    SuiteCollectability,
)


_HANDLER_MODULE = "des.adapters.drivers.hooks.subagent_stop_handler"

# The feature + slice this acceptance suite builds gate invocations for.
_FEATURE_ID = FeatureId("oss-spine-watchdog-demo")
_SLICE_ID = SliceId("slice-12")

# The genuine-terminal event set — a durable record in this set means the gate
# TERMINATED (not re-blocked). The collection-crash terminal routes through the
# slice-04 shared `_emit_terminating_indeterminate`, which writes a durable terminal
# record (e.g. `SliceCommitBlockedTerminal`). The non-terminal `SliceCommitBlocked`
# re-fire record is DELIBERATELY EXCLUDED — observing it as a "terminal" would be the
# exact BLOCKER-3 false-positive slice-04 fixed. The AT recognises ANY genuine
# terminal so DELIVER has reuse-first latitude on the exact event name it routes the
# collection terminal through (the slice-04 helper's `event_name` parameter), while a
# bare re-fire block cannot satisfy it.
_GENUINE_TERMINAL_EVENTS = frozenset(
    {"SliceCommitBlockedTerminal", "StaleAgentClosed", "CollectionCrashTerminal"}
)

# The non-terminal re-fire record the gate writes TODAY on the crash path (RED). A
# durable record of THIS event is NOT a terminal — it is the re-fire record the loop
# is built from.
_NON_TERMINAL_BLOCK_EVENT = "SliceCommitBlocked"


def _git(repo: Path, *args: str) -> str:
    """Run a git command inside the repo and return its stdout."""
    completed = subprocess.run(
        ["git", *args], cwd=repo, capture_output=True, text=True, check=True
    )
    return completed.stdout


class CollectionPrecheckGateFixture:
    """Composition-root service for oss-spine-watchdog slice-05 ATs.

    Pillar 3: builds a real git repo under tmp_path whose COMMITTED contract suite
    either crashes on collection or collects cleanly, writes a real `G_COMMIT`
    crafter transcript, then fires the SAME `handle_subagent_stop` G_COMMIT
    exit-gate hook the live spine fires. The AT observes the gate's decision via a
    re-read of the ledger (was a durable GENUINE-terminal record appended?) + the
    hook's decision body (was it a non-block return?).

    Mandate-12 criterion 3: every public method is the SSOT for one piece of
    business logic. Step bodies do a typed lookup + one method call; nothing more.
    """

    def __init__(self, tmp_path: Path) -> None:
        self._repo = tmp_path / "deliver-repo"
        self._transcript_path = self._repo / "agent.jsonl"

    # --- repo provisioning ---------------------------------------------------

    def _init_repo(self) -> None:
        """Lay out a real git repo with a seed commit (the hook resolves its cwd)."""
        self._repo.mkdir(parents=True, exist_ok=True)
        _git(self._repo, "init", "--quiet")
        _git(self._repo, "config", "user.email", "watchdog-slice05@example.test")
        _git(self._repo, "config", "user.name", "Watchdog Slice 05 AT")
        (self._repo / "README.md").write_text("seed\n", encoding="utf-8")
        _git(self._repo, "add", "README.md")
        _git(self._repo, "commit", "--quiet", "-m", "chore: seed")

    def build_commit(self, *, collectability: SuiteCollectability) -> None:
        """Commit a contract suite that crashes on collection OR collects cleanly.

        Every repo gets a `conftest.py` marking each collected item with the
        contract marker (`unit`) so the gate's contract scope is non-empty, plus one
        clean contract test. For COLLECTION_CRASHES, ALSO commit one contract test
        module with an import-time crash (a broken import) → the real
        `run_contract_gate --collect-only` precheck collection aborts (exit 2), the
        #68 root. The crashing module is COMMITTED so the committed-tree precheck
        (and today's E2 committed-scope digest) collects it. The commit carries a
        `Slice-Id:` trailer (so the slice is identified) but NO `Gate-Scope:` trailer
        (so the clean case still fails E2 for an ORDINARY reason — the discriminator
        needs a clean-collecting commit that nonetheless blocks).

        GIT-tracked, pure filesystem. The crashing module is isolated to this
        tmp_path repo so it cannot poison the real test tree's collection (DEVOPS CI
        constraint: reproduce the SHAPE, not the BLAST RADIUS).
        """
        self._init_repo()
        tests_dir = self._repo / "tests"
        tests_dir.mkdir(parents=True, exist_ok=True)
        (self._repo / "conftest.py").write_text(
            "import pytest\n\n\n"
            "def pytest_collection_modifyitems(config, items):\n"
            "    for item in items:\n"
            "        item.add_marker(pytest.mark.unit)\n",
            encoding="utf-8",
        )
        (tests_dir / "test_clean_contract.py").write_text(
            "def test_collects_fine():\n    assert True\n", encoding="utf-8"
        )
        if collectability is SuiteCollectability.COLLECTION_CRASHES:
            (tests_dir / "test_broken_import_xyz.py").write_text(
                "import this_module_does_not_exist_xyz  # noqa\n\n\n"
                "def test_never_runs():\n    assert True\n",
                encoding="utf-8",
            )
        _git(self._repo, "add", "--all")
        _git(
            self._repo,
            "commit",
            "--quiet",
            "-m",
            f"feat: deliver slice work\n\nSlice-Id: {_SLICE_ID}",
        )

    # --- observable port reads (re-read count deltas) ------------------------

    def _count_genuine_terminals(self) -> int:
        """Count durable GENUINE-terminal records in the ledger (port read).

        A genuine-terminal record means the gate TERMINATED. EXCLUDES the
        non-terminal `SliceCommitBlocked` re-fire record (observing it as a terminal
        would be the BLOCKER-3 false-positive). Returns 0 when the ledger is absent /
        unreadable (mirror slice-04 `_count_event`).
        """
        ledger = AtCompletionLedger(_FEATURE_ID, self._repo)
        try:
            records = ledger.read_records()
        except Exception:
            return 0
        return sum(
            1 for record in records if record.get("event") in _GENUINE_TERMINAL_EVENTS
        )

    # --- driving-port invocation (the REAL hook subprocess) ------------------

    def run_g_commit_gate(self, *, collectability: SuiteCollectability) -> GateOutcome:
        """Fire the REAL G_COMMIT exit-gate hook; observe terminate-vs-block.

        Commits the contract suite (crash OR clean), re-reads the genuine-terminal
        count, fires the hook, re-reads the count. The OBSERVABLE is the COUNT DELTA
        (did the gate write a durable terminal?) + whether the hook returned a
        `{decision:block}` body (did it re-fire?). Mirror of
        composition_slice_04.run_bounded_block_terminal's re-read-count-delta
        observable + composition_slice_02's non-block read.
        """
        self.build_commit(collectability=collectability)
        terminals_before = self._count_genuine_terminals()
        self._write_transcript(phase="G_COMMIT")
        completed = self._fire_hook(session="watchdog-slice05")
        terminals_after = self._count_genuine_terminals()
        return GateOutcome(
            terminated=terminals_after > terminals_before,
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
        """Invoke the REAL `handle_subagent_stop` hook over its JSON protocol.

        The hook env is NOT given `NWAVE_FRESHNESS=skip` — the gate's precheck (when
        wired) clears it internally for the collection subprocess (D-7 / DV-4). The
        hook resolves its own repo + ledger from the transcript context (slice-04
        sibling pattern).
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


@pytest.fixture
def collection_precheck_gate_fixture(tmp_path) -> CollectionPrecheckGateFixture:
    """The single composition-root service all slice-05 step methods delegate to."""
    return CollectionPrecheckGateFixture(tmp_path)


@pytest.fixture
def state_05() -> dict:
    """Per-scenario scratchpad: `collectability`, `outcome`, `before`."""
    return {}


__all__ = [
    "CollectionPrecheckGateFixture",
]
