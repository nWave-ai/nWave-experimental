"""git --no-verify guard -- PreToolUse/Bash hook (sibling of git_stash_guard).

A STANDALONE Claude Code PreToolUse/Bash hook that mechanically enforces the
STANDING "a gate bypass needs explicit HUMAN authorization, not the agent's
self-judgment" rule. Empirical anchor (2026-06-25): the agent used
`git commit/push --no-verify` 5x in one session, self-authorizing each, because
NO mechanical guard existed -- the `nwave-bypass-detector` is a post-commit
AUDIT logger that cannot block (and whose `--no-verify` detection was broken).
A pre-commit-framework hook structurally CANNOT catch `--no-verify` (the flag
skips pre-commit by design), so the interception must live one layer up, at the
Claude Code Bash-tool boundary -- exactly where `git_stash_guard` already sits.

The hook receives the tool invocation event as JSON on stdin, inspects
`tool_input.command`, and dispatches:

  Fast-path (no bypass flag):
    No `--no-verify` / `--no-gpg-sign` token -> exit 0 silently. The
    HOOK_EVENTS registration greps the flag BEFORE spawning the interpreter;
    this Python entry repeats the discriminator so a direct invocation is
    unambiguous too.

  Bypass-flag on a git command (BLOCK):
    A `git ...` command carrying `--no-verify` or `--no-gpg-sign` is refused:
    print `{"decision": "block", "reason": "..."}` + exit 2. The reason states
    that the bypass needs the HUMAN's explicit go and names the audited
    kill-switch so the operator sees an actionable remedy.

  Help / non-git path (ALLOW):
    `--help`/`-h`, or a command that is not a git invocation (the flag appears
    only inside an echoed/greped string), is not a real bypass -> exit 0.

  Kill-switch (ALLOW + audit):
    When the command IS a guarded git bypass AND `NWAVE_ALLOW_NO_VERIFY` is set
    truthy (any non-empty value not in {0,false,no,off}, case-insensitive), the
    hook APPROVES (exit 0) and emits one audited `NoVerifyBypassUsed` JSONL
    event to `<target>/.nwave/des/logs/audit-{today}.log`. RULE (not mechanical):
    the agent MUST NOT set this var itself -- it is the HUMAN's grant. The audit
    event is the accountability: every deliberate bypass is loud and logged.

Substrate (mirrors git_stash_guard's framing): Claude Code hook lifecycle, NOT
git. The pre-commit framework's own internal subprocesses are never Claude Bash
tool invocations, so they are never intercepted here.

Stdlib-only (no third-party deps).

Hook protocol contract (Claude Code PreToolUse on Bash):
    stdin = {"tool_name": "Bash", "tool_input": {"command": "...", ...}, ...}
    stdout (block) = {"decision": "block", "reason": "..."}
    stdout (approve) = "" (exit code 0 is the signal)
    exit 0 = allow tool invocation
    exit 2 = block tool invocation (with stdout JSON for reason)

Test-harness env-var contract:
    NWAVE_ALLOW_NO_VERIFY -- kill-switch; truthy bypasses the block (audited
        NoVerifyBypassUsed event). The HUMAN's grant, not the agent's.
    NWAVE_NO_VERIFY_GUARD_TARGET_ROOT -- target-root override so the hook
        locates the audit-log dir without relying on Path.cwd().
"""

from __future__ import annotations

import json
import os
import re
import sys
from datetime import datetime, timezone
from pathlib import Path


# Kill-switch env var: truthy value approves the git bypass and emits an audited
# NoVerifyBypassUsed event. By RULE this is the human's grant, never agent-set.
_ALLOW_ENV = "NWAVE_ALLOW_NO_VERIFY"

# Test-harness env var so the hook locates the target tree (audit-log dir)
# without relying on Path.cwd(). Production leaves it unset.
_TARGET_ROOT_ENV = "NWAVE_NO_VERIFY_GUARD_TARGET_ROOT"

_AUDIT_LOG_DIR_RELPATH = Path(".nwave") / "des" / "logs"

# The audit-event name the guard emits on a kill-switch bypass.
_BYPASS_EVENT = "NoVerifyBypassUsed"

# The guarded bypass flags, matched as standalone tokens (so `--no-verify-foo`
# or a substring inside another word never matches). `--no-verify` skips the
# pre-commit / commit-msg / pre-push verification hooks; `--no-gpg-sign` skips
# the commit-signature gate.
_BYPASS_FLAG_RE = re.compile(r"(?:^|\s)(--no-verify|--no-gpg-sign)(?=\s|=|$)")

# Discriminator that the command actually INVOKES git (not merely mentions it
# inside an echoed/greped string). Matches a `git` command word at the start of
# the command or after a shell separator / env-assignment prefix.
_GIT_INVOKE_RE = re.compile(r"(?:^|[\s;&|(]|&&|\|\|)git(?=\s)")

# Help flags that turn ANY invocation into a read-only doc request.
_HELP_FLAGS = frozenset({"--help", "-h"})

# Falsy env-var spellings that DO NOT activate the kill-switch.
_FALSY_ENV_VALUES = frozenset({"0", "false", "no", "off"})

# Block reason: names the rule AND the audited bypass mechanism. The agent must
# get the human's go; it must NOT set the kill-switch itself.
_BLOCK_REASON = (
    "git --no-verify / --no-gpg-sign BYPASSES the verification hooks and "
    "requires EXPLICIT HUMAN authorization -- the agent must not self-authorize "
    "a gate bypass (STANDING). Ask the human; do not set the kill-switch "
    "yourself. To grant deliberately, the human sets NWAVE_ALLOW_NO_VERIFY=1 "
    "(audited NoVerifyBypassUsed event)."
)


def _read_hook_event() -> dict[str, object]:
    """Read the Claude Code PreToolUse hook event JSON from stdin.

    Returns `{}` if stdin is empty or malformed; the caller treats this as a
    non-actionable event (approve silently). Fails OPEN on protocol violations.
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


def _has_bypass_flag(command: str) -> bool:
    """True iff the command carries a guarded bypass flag as a standalone token."""
    return _BYPASS_FLAG_RE.search(command) is not None


def _is_git_invocation(command: str) -> bool:
    """True iff the command actually invokes git (not just mentions it)."""
    return _GIT_INVOKE_RE.search(command) is not None


def _is_help(command: str) -> bool:
    """True iff the command is a read-only help request."""
    return any(token in _HELP_FLAGS for token in command.split())


def _is_guarded_bypass(command: str) -> bool:
    """True iff this is a real git verification bypass that must be blocked."""
    if not _has_bypass_flag(command):
        return False
    if _is_help(command):
        return False
    return _is_git_invocation(command)


def _allow_env_active() -> bool:
    """True when NWAVE_ALLOW_NO_VERIFY is set to a truthy value.

    Truthy = any non-empty string not in `_FALSY_ENV_VALUES` (case-insensitive).
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
    """Append one NoVerifyBypassUsed event to today's audit log (JSONL format).

    The directory is created on demand. The event carries the command + session
    id so the operator sees which bypass was deliberately allowed.
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
        2. Fast-path: no guarded git bypass -> exit 0 (no filesystem work).
        3. Kill-switch active -> exit 0 (approve) + audited NoVerifyBypassUsed.
        4. Guarded git bypass -> exit 2 (block) + {decision: block} reason.
    """
    event = _read_hook_event()
    command = _bash_command(event)
    if not _is_guarded_bypass(command):
        return 0
    if _allow_env_active():
        _emit_bypass_event(_target_root(), command, _session_id(event))
        return 0
    _emit_block()
    return 2


if __name__ == "__main__":
    sys.exit(main())
