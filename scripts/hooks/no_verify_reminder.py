#!/usr/bin/env python3
"""nWave --no-verify reminder guard — lean PreToolUse/Bash hook.

An imperative reminder (NOT the full audit guard): when a Bash `git` command
carries a verify-bypass flag, BLOCK it with a reminder that the bypass must be
agreed with the human. No audit log, no kill-switch, no marker — detect → block
→ remind. (Supersedes the heavier `git_no_verify_guard.py` thread per the lean
direction: Ale 2026-06-26.)

Detection is TOKENIZED, not a raw-string regex, because a commit MESSAGE that
merely MENTIONS a bypass flag (e.g. `git commit -m "document the --no-verify
guard"`) must NOT be blocked — a naive `re.search("--no-verify")` false-blocks
legitimate commits. `shlex` tokenization + standalone-token matching only fires
on a real flag, never on text inside a quoted argument.

Guarded:
  * `--no-verify` / `--no-gpg-sign` on ANY git subcommand (long form).
  * `git commit ... -n` (the short form of --no-verify).
NOT guarded (correctly):
  * `git push -n`  (that is --dry-run, harmless).
  * `git log -n 5` (that is the count flag).
  * any flag string appearing inside a quoted commit message.

Protocol: reads the PreToolUse JSON on stdin; on a guarded bypass prints a
`{"decision":"block"}` body and exits 0; otherwise exits 0 silently (fast path).
Exit 0 always — a non-zero exit would make Claude Code ignore the stdout body.
"""

from __future__ import annotations

import json
import shlex
import sys


_REMINDER = (
    "⛔ STOP: `--no-verify` skips the quality gates. It must be explicitly "
    "agreed with the human — do NOT self-authorize. Ask the human before "
    "proceeding."
)

# Long-form verify-bypass flags valid on any git subcommand.
_LONG_BYPASS_FLAGS = frozenset({"--no-verify", "--no-gpg-sign"})
# Shell separators that delimit one command from the next inside a Bash string.
_SEPARATORS = frozenset({"&&", "||", ";", "|", "&"})


def _command_carries_git_bypass(command: str) -> bool:
    """True iff ``command`` runs a git verify-bypass as a REAL flag token.

    Tokenizes with shlex so a flag string inside a quoted argument (a commit
    message) is one opaque token, never a standalone match. Splits on shell
    separators so each sub-command is judged on its own git invocation.
    """
    try:
        tokens = shlex.split(command)
    except ValueError:
        # Unbalanced quotes etc. — do NOT false-block on an unparseable command.
        return False

    sub_commands: list[list[str]] = []
    current: list[str] = []
    for token in tokens:
        if token in _SEPARATORS:
            if current:
                sub_commands.append(current)
                current = []
        else:
            current.append(token)
    if current:
        sub_commands.append(current)

    for sub in sub_commands:
        if "git" not in sub:
            continue
        rest = sub[sub.index("git") + 1 :]
        if not rest:
            continue
        # Long form on any subcommand: a standalone --no-verify / --no-gpg-sign.
        if any(flag in rest for flag in _LONG_BYPASS_FLAGS):
            return True
        # Short form: `-n` ONLY on `git commit` (commit -n == --no-verify).
        # `git push -n` is --dry-run and `git log -n` is a count — never guarded.
        if "commit" in rest and "-n" in rest:
            return True
    return False


def main() -> int:
    try:
        payload = json.load(sys.stdin)
    except Exception:
        return 0
    tool_input = payload.get("tool_input") if isinstance(payload, dict) else None
    command = tool_input.get("command") if isinstance(tool_input, dict) else None
    if not isinstance(command, str) or not command:
        return 0
    if _command_carries_git_bypass(command):
        print(json.dumps({"decision": "block", "reason": _REMINDER}))
    return 0


if __name__ == "__main__":
    sys.exit(main())
