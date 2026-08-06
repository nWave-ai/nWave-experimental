"""git-stash guard PreToolUse hook -- slice-01 of fix-crafter-stash-structural-mitigation.

A STANDALONE Claude Code PreToolUse/Bash hook that mechanically enforces the
STANDING "no git stash, use git worktree" rule (10 cumulative text-rule
violations as of 2026-05-28 -- see
[[feedback_no_worktrees_no_excessive_parallel_2026_05_19]]). The hook receives
the tool invocation event as JSON on stdin, inspects `tool_input.command`, and
dispatches:

  Fast-path (non-git-stash Bash):
    Regex-match `^\\s*git\\s+stash\\b` on the command. If NO match, exit 0
    silently -- a bare Python early-exit before any filesystem work. The
    HOOK_EVENTS registration greps the command before spawning the
    interpreter, and this Python entry point repeats the discriminator so the
    decision is unambiguous even when invoked directly.

  Mutating git-stash path (BLOCK):
    A mutating subcommand (bare `git stash`, or `push`/`pop`/`apply`/`drop`/
    `clear`/`save`/`branch`/`create`/`store`) is refused: print
    `{"decision": "block", "reason": "..."}` to stdout + exit 2. The reason
    names the safe alternative (`git worktree add /tmp/probe HEAD`) AND the
    bypass mechanism (`NWAVE_GIT_STASH_ALLOW`) so the operator sees an
    actionable remedy.

  Read-only git-stash path (ALLOW):
    `git stash list`, `git stash show` (incl. `-p`), and any `git stash`
    carrying `--help`/`-h` are read-only/help forms -- exit 0 silently.

  Kill-switch (ALLOW + audit):
    When the command IS a mutating `git stash` AND `NWAVE_GIT_STASH_ALLOW` is
    set to a truthy value (any non-empty string that is not `0`/`false`/`no`/
    `off`, case-insensitive),
    the hook APPROVES (exit 0) and emits one audited `GitStashBypassUsed`
    event (JSONL) to `<target>/.nwave/des/logs/audit-{today}.log`. The event
    carries the `command` field so the operator sees which stash invocation
    was deliberately allowed.

Substrate (Ale 2026-05-28 framing): Claude Code hook lifecycle. NOT git. The
pre-commit framework's INTERNAL `git stash` ("Stashing unstaged files") is a
subprocess spawned BY the pre-commit binary, NOT a Claude `Bash` tool
invocation, so it is never intercepted by this PreToolUse hook.

Stdlib-only (no PyYAML, no third-party deps). Uses the standard PreToolUse/Bash
protocol: JSON stdin, block decision, and audited kill-switch bypasses.

Hook protocol contract (Claude Code PreToolUse on Bash):
    stdin = {"tool_name": "Bash", "tool_input": {"command": "...", ...}, ...}
    stdout (block) = {"decision": "block", "reason": "..."}
    stdout (approve) = "" (empty; exit code 0 is the signal)
    exit 0 = allow tool invocation
    exit 2 = block tool invocation (with stdout JSON for reason)

Test-harness env-var contract (slice-01 ATs):
    NWAVE_GIT_STASH_ALLOW -- kill-switch; truthy value bypasses the block
        (audited GitStashBypassUsed event).
    NWAVE_GIT_STASH_GUARD_TARGET_ROOT -- target machine root override so the
        hook locates the audit-log dir without relying on Path.cwd().

In production (no target-root override), the hook uses `Path.cwd()` as the
target root and `<target>/.nwave/des/logs/` as the audit-log dir.
"""

from __future__ import annotations

import json
import os
import re
import sys
from datetime import datetime, timezone
from pathlib import Path


# Kill-switch env var: truthy value approves the mutating git-stash invocation
# and emits an audited GitStashBypassUsed event.
_ALLOW_ENV = "NWAVE_GIT_STASH_ALLOW"

# Test-harness env var so the hook locates the target tree (audit-log dir)
# without relying on Path.cwd(). Production leaves it unset and falls back to
# Path.cwd().
_TARGET_ROOT_ENV = "NWAVE_GIT_STASH_GUARD_TARGET_ROOT"

_AUDIT_LOG_DIR_RELPATH = Path(".nwave") / "des" / "logs"

# The audit-event name the guard emits on a kill-switch bypass.
_BYPASS_EVENT = "GitStashBypassUsed"

# Shell-fast-path discriminator: a bash command starts with `git stash` (with
# optional leading whitespace) followed by a word boundary so `git stashed`
# (hypothetical) does not match.
_GIT_STASH_RE = re.compile(r"^\s*git\s+stash\b")

# Read-only `git stash` subcommands: the next non-flag token after `git stash`.
# Only `list` + `show` are non-mutating in modern git. Every other subcommand
# (push/pop/apply/drop/clear/save/branch/create/store) -- and the bare
# `git stash` (implicit push) -- mutates the stash stack or working tree.
_READ_ONLY_SUBCOMMANDS = frozenset({"list", "show"})

# Help flags that turn ANY `git stash` invocation into a read-only doc request.
_HELP_FLAGS = frozenset({"--help", "-h"})

# Falsy env-var spellings that DO NOT activate the kill-switch, mirroring
# standard shell conventions for boolean flags.
_FALSY_ENV_VALUES = frozenset({"0", "false", "no", "off"})

# Block reason: names the safe alternative AND the bypass mechanism so the
# operator sees a directly actionable remedy. AT-1 asserts both substrings.
_BLOCK_REASON = (
    "git stash is forbidden per STANDING (10 cumulative violations); "
    "use `git worktree add /tmp/probe HEAD` for clean-tree isolation instead. "
    "To bypass deliberately, set NWAVE_GIT_STASH_ALLOW=1 "
    "(audited GitStashBypassUsed event)."
)


def _read_hook_event() -> dict[str, object]:
    """Read the Claude Code PreToolUse hook event JSON from stdin.

    Returns `{}` if stdin is empty or malformed; the caller treats this as a
    non-actionable event (approve silently). The hook fails OPEN on protocol
    violations -- a malformed event is a Claude Code bug, not an operator
    violation.
    """
    raw = sys.stdin.read()
    if not raw.strip():
        return {}
    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError:
        return {}
    return parsed if isinstance(parsed, dict) else {}


def _bash_command(event: dict[str, object]) -> str:
    """Extract the bash command literal from the hook event payload."""
    tool_input = event.get("tool_input", {})
    if not isinstance(tool_input, dict):
        return ""
    command = tool_input.get("command", "")
    return command if isinstance(command, str) else ""


def _session_id(event: dict[str, object]) -> str:
    """Extract the Claude Code session id from the hook event payload."""
    session_id = event.get("session_id", "")
    return session_id if isinstance(session_id, str) else ""


def _is_git_stash(command: str) -> bool:
    """True iff the bash command begins with `git stash` (word-boundary match)."""
    return _GIT_STASH_RE.match(command) is not None


def _is_mutating_git_stash(command: str) -> bool:
    """True iff a `git stash` command mutates state (block candidate).

    Discriminator: tokenise the command; any token in `--help`/`-h` makes the
    invocation a read-only help request (ALLOW). Otherwise peek the first
    non-flag token AFTER `stash`; if it is in `{list, show}` -> read-only
    (ALLOW). Bare `git stash` (no subcommand) and every other subcommand
    (push/pop/apply/drop/clear/save/branch/create/store) -> mutating (BLOCK).
    """
    tokens = command.split()
    if any(token in _HELP_FLAGS for token in tokens):
        return False
    subcommand = _first_subcommand_after_stash(tokens)
    return subcommand not in _READ_ONLY_SUBCOMMANDS


def _first_subcommand_after_stash(tokens: list[str]) -> str | None:
    """Return the first non-flag token after the `stash` token, or None.

    Walks past the leading `git stash` tokens, then returns the first token
    that is not a flag (does not start with `-`). A bare `git stash` with no
    following token returns None (treated as mutating implicit push).
    """
    seen_stash = False
    for token in tokens:
        if not seen_stash:
            if token == "stash":
                seen_stash = True
            continue
        if token.startswith("-"):
            continue
        return token
    return None


def _allow_env_active() -> bool:
    """True when NWAVE_GIT_STASH_ALLOW is set to a truthy value.

    Truthy = any non-empty string that is not one of `_FALSY_ENV_VALUES`
    (case-insensitive), so an operator who exports the var with any non-zero
    value gets the bypass.
    """
    raw = os.environ.get(_ALLOW_ENV, "")
    if not raw:
        return False
    return raw.strip().lower() not in _FALSY_ENV_VALUES


def _target_root() -> Path:
    """Resolve the target machine root from env override or Path.cwd()."""
    override = os.environ.get(_TARGET_ROOT_ENV, "")
    return Path(override) if override else Path.cwd()


def _audit_log_path(target_root: Path) -> Path:
    """Return today's UTC-dated audit log path under the target root."""
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    return target_root / _AUDIT_LOG_DIR_RELPATH / f"audit-{today}.log"


def _emit_bypass_event(target_root: Path, command: str, session_id: str) -> None:
    """Append one GitStashBypassUsed event to today's audit log (JSONL format).

    The directory is created on demand so the first bypass on a clean target
    succeeds. The event carries the git-stash command + session id.
    """
    log_path = _audit_log_path(target_root)
    log_path.parent.mkdir(parents=True, exist_ok=True)
    event = {
        "event": _BYPASS_EVENT,
        "ts": datetime.now(timezone.utc).isoformat(),
        "command": command,
        "session_id": session_id,
    }
    with log_path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(event, sort_keys=True) + "\n")


def _emit_block() -> None:
    """Print a single-line `{decision: block}` JSON object on stdout."""
    print(json.dumps({"decision": "block", "reason": _BLOCK_REASON}, sort_keys=True))


def main() -> int:
    """Read the hook event, dispatch by command shape, return the exit code.

    Decision order:
        1. Read stdin event JSON (empty/malformed -> approve silently).
        2. Fast-path: non-git-stash command -> exit 0 (no filesystem work).
        3. Read-only git-stash (list/show/--help) -> exit 0 (approve).
        4. Kill-switch active -> exit 0 (approve) + audited GitStashBypassUsed.
        5. Mutating git-stash -> exit 2 (block) + {decision: block} reason.
    """
    event = _read_hook_event()
    command = _bash_command(event)
    if not _is_git_stash(command):
        return 0
    if not _is_mutating_git_stash(command):
        return 0
    if _allow_env_active():
        _emit_bypass_event(_target_root(), command, _session_id(event))
        return 0
    _emit_block()
    return 2


if __name__ == "__main__":
    sys.exit(main())
