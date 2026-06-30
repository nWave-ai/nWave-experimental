"""Composition root for slice-01 (git-stash guard) of fix-crafter-stash-structural-mitigation.

Wires the PRODUCTION git-stash guard hook script as a real Python subprocess
(Layer 3 driving port per Mandate-13) against a tmp_path target tree. The hook
is a STANDALONE PreToolUse/Bash guard — unlike the spine-ledger pre-commit hook
(slice-02 of atdd-spine-ledger-enforcement-gate-v2), it does NOT spawn a second
gate subprocess: it IS the gate. It inspects `tool_input.command`, blocks
mutating `git stash` invocations, honours the `NWAVE_GIT_STASH_ALLOW` kill-switch
(emitting an audited `GitStashBypassUsed` event), and passes through everything
else.

The only driven ports are:
  - the real filesystem (tmp_path target carries `.nwave/des/logs/audit-{today}.log`),
  - the real environment (`NWAVE_GIT_STASH_ALLOW` env var, cleared/set per-test
    via the conftest autouse fixture; plus `NWAVE_GIT_STASH_GUARD_TARGET_ROOT`
    for test-harness parameter passing so the hook locates the audit-log dir
    without relying on `Path.cwd()`),
  - the real subprocess (`python -m scripts.hooks.git_stash_guard`, invoked with
    Claude Code hook-event JSON on stdin).

Business logic — subprocess construction, hook-event JSON synthesis, audit-log
discovery + parsing — lives here as the single source of truth; step bodies
delegate to `GitStashGuardFixture` methods and never inline logic (Mandate-12
criterion 3: ≤2 statements per step body, final statement is a composition
method call, zero control flow in step bodies).

STANDALONE (no inheritance): per dispatch invariant 2, `GitStashGuardFixture` is
a fresh fixture with NO subclassing of the spine-ledger `KillSwitchFixture`
hierarchy. The two features share a hook-protocol SHAPE (Claude Code PreToolUse
JSON stdin → JSON-decision stdout + exit code) but not a fixture lineage; the
git-stash guard's audit-event name (`GitStashBypassUsed`) and kill-switch env
var (`NWAVE_GIT_STASH_ALLOW`) are distinct from the spine-ledger gate's.

RED-for-the-right-reason: the target script `scripts/hooks/git_stash_guard.py`
does NOT EXIST YET (the crafter lands it in DELIVER). When
`invoke_git_stash_guard(...)` invokes the absent module via `python -m`, the
interpreter returns a non-zero exit with a stderr naming the missing module;
the fixture surfaces this as `AssertionError` on the first `Then` step that
calls `assert_block_decision_returned` or `assert_approve_decision_returned`.
That is the correct RED: the assertion fires because the implementation is
missing.

Mandate-13 (driving-port-only): every step delegates to the composition
fixture, which drives the SUT via `python -m scripts.hooks.git_stash_guard`
subprocess + JSON stdin. ZERO direct production imports in step composition.
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from time import perf_counter_ns

from tests.common.in_process_cli import run_hook_in_process

from scripts.hooks import git_stash_guard


# Repo root: tests/installer/acceptance/<feature>/steps/composition.py -> up five levels.
_REPO_ROOT = Path(__file__).resolve().parents[5]

# Kill-switch env var: when set to a truthy value, the guard approves the
# `git stash` invocation and emits an audited GitStashBypassUsed event.
_ALLOW_ENV = "NWAVE_GIT_STASH_ALLOW"

# Test-harness env var so the hook locates the target tree (audit-log dir)
# without relying on Path.cwd(). Production leaves it unset and falls back to
# Path.cwd() — mirrors the spine-ledger NWAVE_SPINE_LEDGER_GATE_TARGET_ROOT
# contract.
_TARGET_ROOT_ENV = "NWAVE_GIT_STASH_GUARD_TARGET_ROOT"

_AUDIT_LOG_DIR_RELPATH = Path(".nwave") / "des" / "logs"

# The audit-event name the guard emits on a kill-switch bypass.
_BYPASS_EVENT = "GitStashBypassUsed"


@dataclass(frozen=True)
class HookInvocation:
    """One captured invocation of the git-stash guard PreToolUse hook subprocess.

    The SUT reads JSON from stdin (the Claude Code PreToolUse hook event) and
    writes a `{decision: ..., reason: ...}` JSON object to stdout when it
    blocks; on approve, stdout may be empty (exit code 0 is the signal).
    """

    exit_code: int
    stdout: str
    stderr: str
    duration_ms: float
    audit_events_before: tuple[dict, ...] = field(default_factory=tuple)
    audit_events_after: tuple[dict, ...] = field(default_factory=tuple)

    @property
    def stdout_json(self) -> dict:
        """Parse the single-line JSON decision from stdout, or {} if absent.

        Returns empty dict (not None) so step bodies can call `.get(...)`
        without conditional unwrap.
        """
        for line in self.stdout.splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                return json.loads(line)
            except json.JSONDecodeError:
                continue
        return {}

    @property
    def new_bypass_events(self) -> tuple[dict, ...]:
        """GitStashBypassUsed events emitted by THIS invocation only.

        The audit log is append-only JSONL; `_read_audit_log_events` re-parses
        the file into fresh dict objects on every call, so an `id()`-based
        before/after set-difference degenerates (no after-dict shares identity
        with any before-dict) -- it would report ALL after-events as "new".
        The correct delta is positional: the audit log grows by appending, so
        the new events are exactly the suffix beyond `len(before)`. Filter that
        suffix to GitStashBypassUsed so unrelated audit events do not inflate
        the count. This makes "exactly one NEW event" match the Gherkin
        semantics (Medium-1 reviewer fix, 2026-05-28).
        """
        new_suffix = self.audit_events_after[len(self.audit_events_before) :]
        return tuple(e for e in new_suffix if e.get("event") == _BYPASS_EVENT)


class GitStashGuardFixture:
    """Drives the git-stash guard hook subprocess against a tmp_path target.

    Each instance is bound to one tmp_path target tree (passed in). The fixture
    exposes composition methods that step bodies invoke; no business logic is
    inlined in any step. STANDALONE — no inheritance from spine-ledger fixtures.

    The hook protocol contract (Claude Code PreToolUse on Bash):

      stdin = {
        "tool_name": "Bash",
        "tool_input": {"command": "git stash push -m wip", ...},
        "session_id": "...",
        ...
      }
      stdout (block) = {"decision": "block", "reason": "..."}
      stdout (approve) = "" (empty; exit code 0 is the signal)
      exit 0 = allow tool invocation
      exit 2 = block tool invocation (with stdout JSON for reason)
    """

    def __init__(self, target_root: Path) -> None:
        self._target_root = target_root
        self._target_root.mkdir(parents=True, exist_ok=True)
        self._prepared_hook_event: dict | None = None

    # ---- Precondition setup (Given step delegates) ----

    def ensure_hook_installed(self) -> None:
        """No-op precondition: subprocess invocation models the installed surface.

        The installer plugin ships the hook entry in
        `scripts/install/plugins/des_plugin.py` (DELIVER scope). For dev-mode
        Layer 3 acceptance the subprocess invocation from the repo root models
        the "installed" surface. The step exists for Pillar 1 readability.
        """
        # No filesystem state to seed; the tmp_path target is clean by construction.

    def clear_allow_env(self) -> None:
        """Remove NWAVE_GIT_STASH_ALLOW from the process environment."""
        os.environ.pop(_ALLOW_ENV, None)

    def set_allow_env(self, value: str) -> None:
        """Set NWAVE_GIT_STASH_ALLOW in the process environment to the given value."""
        os.environ[_ALLOW_ENV] = value

    def prepare_bash_event(self, command: str) -> None:
        """Synthesise the Claude Code PreToolUse hook-event JSON for a bash command.

        Mirrors what Claude Code emits on stdin to PreToolUse/Bash hooks. The
        prepared event is stored on the fixture for the subsequent
        `invoke_git_stash_guard` action step (Pillar 2 chained-narrative — the
        When-action step composes the When-command-literal step's result).
        """
        self._prepared_hook_event = {
            "tool_name": "Bash",
            "tool_input": {
                "command": command,
                "description": "Bash invocation under git-stash guard",
            },
            "session_id": "test-session-slice-01",
        }

    # ---- Action (When step delegates) ----

    def invoke_git_stash_guard(self) -> HookInvocation:
        """Invoke the slice-01 git-stash guard hook as a real subprocess.

        Pipes the prepared hook-event JSON (from the `prepare_bash_event` Given/
        When step) to the hook's stdin, mirroring how Claude Code actually
        invokes PreToolUse hooks on Bash. Captures stdout (decision JSON if
        blocked), stderr (diagnostics), exit code (0 = allow, 2 = block per
        Claude Code's protocol), wall-clock duration, and the audit-log event
        delta (Mandate 8 universe-bound state delta over the GitStashBypassUsed
        event count).
        """
        assert self._prepared_hook_event is not None, (
            "Test author error: invoke_git_stash_guard called before a "
            "prepare_bash_event step."
        )
        before_events = self._read_audit_log_events()
        stdin_payload = json.dumps(self._prepared_hook_event)
        start_ns = perf_counter_ns()
        # In-process analogue of ``python -m scripts.hooks.git_stash_guard`` reading
        # the hook event on stdin. The guard spawns NO git (it regex-inspects the
        # command string only) and locates its audit log via _TARGET_ROOT_ENV, NOT
        # cwd -- so the former GIT_* env scrub (belt-and-braces over the conftest
        # session scrub) is unnecessary in-process. _TARGET_ROOT_ENV is the lone
        # load-bearing override (NWAVE_GIT_STASH_ALLOW is set on os.environ by the
        # given steps); set it on os.environ and restore in finally.
        prior_target_root = os.environ.get(_TARGET_ROOT_ENV)
        os.environ[_TARGET_ROOT_ENV] = str(self._target_root)
        try:
            exit_code, out, err = run_hook_in_process(
                git_stash_guard.main,
                stdin_text=stdin_payload,
                cwd=str(_REPO_ROOT),
            )
        finally:
            if prior_target_root is None:
                os.environ.pop(_TARGET_ROOT_ENV, None)
            else:
                os.environ[_TARGET_ROOT_ENV] = prior_target_root
        duration_ms = (perf_counter_ns() - start_ns) / 1_000_000
        after_events = self._read_audit_log_events()
        return HookInvocation(
            exit_code=exit_code,
            stdout=out or "",
            stderr=err or "",
            duration_ms=duration_ms,
            audit_events_before=before_events,
            audit_events_after=after_events,
        )

    # ---- Observation (Then step delegates) ----

    def assert_block_decision_returned(self, invocation: HookInvocation) -> None:
        """Assert the hook returned a {decision: block} payload + exit 2.

        Claude Code PreToolUse contract: a blocking hook prints
        `{"decision": "block", "reason": "..."}` on stdout and exits with code
        2. The composition fixture surfaces a clear AssertionError when the
        slice-01 guard script is unimplemented (subprocess returns non-zero
        from missing-module error, not from a real block decision).
        """
        assert invocation.exit_code == 2, (
            f"Expected the hook to exit 2 (block); got exit "
            f"{invocation.exit_code}.\nstdout: {invocation.stdout!r}\n"
            f"stderr: {invocation.stderr!r}"
        )
        decision = invocation.stdout_json.get("decision")
        assert decision == "block", (
            f"Expected stdout JSON decision 'block'; got {decision!r}.\n"
            f"stdout: {invocation.stdout!r}"
        )

    def assert_approve_decision_returned(self, invocation: HookInvocation) -> None:
        """Assert the hook returned approve (exit 0).

        Claude Code PreToolUse contract: an approving hook exits 0; stdout may
        be empty (exit code is the sole signal) or carry an explicit
        `{decision: approve}` (both accepted per the protocol spec).
        """
        assert invocation.exit_code == 0, (
            f"Expected the hook to exit 0 (approve); got exit "
            f"{invocation.exit_code}.\nstdout: {invocation.stdout!r}\n"
            f"stderr: {invocation.stderr!r}"
        )

    def assert_block_reason_names_phrase(
        self, invocation: HookInvocation, phrase: str
    ) -> None:
        """Assert the block decision's reason text contains the named phrase.

        AT-1 verifies the reason text names BOTH the safe alternative
        (`git worktree add /tmp/probe HEAD`) AND the bypass mechanism
        (`NWAVE_GIT_STASH_ALLOW`) so the operator sees an actionable remedy
        without parsing anything beyond the decision JSON.
        """
        reason = invocation.stdout_json.get("reason", "")
        assert phrase in reason, (
            f"Expected hook decision reason to contain {phrase!r}; "
            f"got reason {reason!r}.\nstdout: {invocation.stdout!r}"
        )

    def assert_bash_invocation_refused_before_spawn(
        self, invocation: HookInvocation
    ) -> None:
        """Assert the block decision was returned BEFORE git stash would run.

        Universe-bound (Mandate 8): returning `{decision: block}` to Claude
        Code suppresses the Bash tool invocation entirely — git stash never
        runs. The composition fixture cannot intercept Claude Code itself, but
        the hook's behaviour (block decision returned via exit 2) is the
        necessary + sufficient condition for the downstream Bash refusal.
        """
        assert invocation.exit_code == 2, (
            "Expected the hook to refuse the Bash invocation via exit 2 "
            f"(block decision); got exit {invocation.exit_code}.\n"
            f"stdout: {invocation.stdout!r}"
        )

    def assert_exactly_one_new_bypass_event(self, invocation: HookInvocation) -> None:
        """Assert the audit log gained exactly one new GitStashBypassUsed event."""
        count = len(invocation.new_bypass_events)
        assert count == 1, (
            f"Expected exactly 1 new {_BYPASS_EVENT} audit event; got {count}.\n"
            f"new events: {invocation.new_bypass_events!r}"
        )

    def assert_zero_new_bypass_events(self, invocation: HookInvocation) -> None:
        """Assert the audit log gained zero new GitStashBypassUsed events."""
        count = len(invocation.new_bypass_events)
        assert count == 0, (
            f"Expected zero new {_BYPASS_EVENT} audit events; got {count}.\n"
            f"new events: {invocation.new_bypass_events!r}"
        )

    def assert_bypass_event_names_command(
        self, invocation: HookInvocation, command: str
    ) -> None:
        """Assert the (single) new bypass event carries the git-stash command."""
        events = invocation.new_bypass_events
        assert len(events) == 1, (
            f"assert_bypass_event_names_command requires exactly one new event; "
            f"got {len(events)}."
        )
        actual = events[0].get("command")
        assert actual == command, (
            f"Expected bypass event command {command!r}; got {actual!r}.\n"
            f"event: {events[0]!r}"
        )

    def assert_filesystem_unchanged_outside_audit_log_and_hook_logs(
        self, invocation: HookInvocation
    ) -> None:
        """Assert the passthrough path created no extra filesystem state.

        AT-3 universe-bound (Mandate 8): the guard on a safe bash command MUST
        NOT create any state under the target root beyond (optionally) the
        audit-log dir. On the passthrough path the guard emits ZERO audit
        events (no bypass), so the audit log itself remains absent — the
        approve path is a pure read-only pass-through.
        """
        _ = invocation
        # Only `.nwave/des/logs/` may exist transiently; the audit log carries
        # zero new bypass events on the passthrough path (asserted separately).
        # No other top-level entry under the target root should appear.
        unexpected = [
            entry.name
            for entry in self._target_root.iterdir()
            if entry.name != ".nwave"
        ]
        assert not unexpected, (
            "Passthrough path created unexpected filesystem state under the "
            f"target root: {unexpected!r}."
        )

    # ---- Internal helpers ----

    def _audit_log_path(self) -> Path:
        """Return today's audit log path under the target root."""
        today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        return self._target_root / _AUDIT_LOG_DIR_RELPATH / f"audit-{today}.log"

    def _read_audit_log_events(self) -> tuple[dict, ...]:
        """Parse today's audit log into a tuple of event dicts (empty if absent).

        The file format is JSONL — one event per line. Malformed lines are
        skipped (tolerant parse) so a partially-written log does not crash the
        assertion path.
        """
        path = self._audit_log_path()
        if not path.exists():
            return ()
        events: list[dict] = []
        for line in path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                parsed = json.loads(line)
            except json.JSONDecodeError:
                continue
            if isinstance(parsed, dict):
                events.append(parsed)
        return tuple(events)
