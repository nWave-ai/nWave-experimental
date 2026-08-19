"""Hook adapter CLI entry point — routes commands to handler modules.

This is the thin dispatcher that replaces the monolithic main() function.
Each handler is in its own module for single-responsibility.

Entry point: python3 -m des.adapters.drivers.hooks.claude_code_hook_adapter <command>
"""

import io
import json
import sys

from des.adapters.drivers.hooks.activation_gate import apply_gate
from des.adapters.drivers.hooks.post_write_handler import handle_post_write
from des.adapters.drivers.hooks.pre_tool_use_handler import (
    evaluate_bash_safety_guards,
    handle_pre_tool_use,
)
from des.adapters.drivers.hooks.pre_write_handler import handle_pre_write
from des.adapters.drivers.hooks.subagent_start_handler import handle_subagent_start
from des.adapters.drivers.hooks.subagent_stop_handler import handle_subagent_stop


_PRE_TOOL_USE_COMMANDS = ("pre-tool-use", "pre-task")


def apply_bash_safety_guards(command: str, stdin_text: str) -> None:
    """Consolidated git-stash / worktree-remove safety decision (ADR-AG-001 repair).

    Runs BEFORE `activation_gate.apply_gate`: an inactive project must not be
    able to exit 0 past a live `git stash` or `git worktree remove` mutation.
    Evaluated exactly once per PreToolUse/pre-task dispatch, regardless of
    activation state, via the single decision authority in
    `bash_command_guards.py` (through `pre_tool_use_handler.evaluate_bash_safety_guards`).

    Fail-open on a non-PreToolUse command, non-JSON/non-dict envelope, or a
    non-Bash tool_name -- identical parse tolerance to `apply_gate`'s own
    `_parse_cwd`, since the gate right after this call
    already owns "no readable envelope -> inactive -> allow". Blocks by
    printing the guard's structured payload and calling `sys.exit(2)`,
    matching the existing block exit-code convention.
    """
    if command not in _PRE_TOOL_USE_COMMANDS:
        return
    try:
        hook_input = json.loads(stdin_text)
    except (json.JSONDecodeError, TypeError):
        return
    if not isinstance(hook_input, dict) or hook_input.get("tool_name") != "Bash":
        return
    tool_input = hook_input.get("tool_input", {})
    if not isinstance(tool_input, dict):
        return
    block = evaluate_bash_safety_guards(hook_input, tool_input)
    if block is not None:
        print(json.dumps(block))
        sys.exit(2)


def main() -> None:
    """Hook adapter entry point - routes command to appropriate handler."""
    if len(sys.argv) < 2:
        print(
            json.dumps(
                {
                    "status": "error",
                    "reason": "Missing hook command argument",
                }
            )
        )
        sys.exit(1)

    command = sys.argv[1]

    # Accept both hyphenated and underscore spellings.
    command = command.replace("_", "-")
    # Activation gate (ADR-AG-001): buffer stdin at the top, before any handler
    # reads it, so the gate can resolve the project and re-inject the bytes
    # byte-identically. Inactive commands exit 0 (allow, never block) inside
    # apply_gate. The
    # read is defensive (fail-open): an unreadable stdin yields an empty buffer.
    try:
        buffered_stdin = sys.stdin.read()
    except (OSError, ValueError):
        buffered_stdin = ""

    # ADR-AG-001 ordering repair: the git-stash/worktree-remove safety
    # decision must run BEFORE the activation gate, else an inactive project
    # exits 0 inside apply_gate before this safety check ever runs. Evaluated
    # exactly once here; `handle_pre_tool_use` no longer re-runs it.
    apply_bash_safety_guards(command, buffered_stdin)

    reinjected = apply_gate(command, buffered_stdin)
    sys.stdin = io.StringIO(reinjected if reinjected is not None else buffered_stdin)

    # Freshness is relevant only after explicit project activation. Running it
    # at facade import time created `.nwave/des/logs` before the activation gate
    # could silence an unrelated repository.
    from des.runtime.freshness import assert_fresh_or_explain

    assert_fresh_or_explain(suppress_git_autoskip=True)

    if command in ("pre-tool-use", "pre-task"):
        # "pre-task" accepted for backward compatibility
        exit_code = handle_pre_tool_use()
    elif command in ("pre-write", "pre-edit"):
        exit_code = handle_pre_write()
    elif command in ("post-write", "post-edit"):
        exit_code = handle_post_write()
    elif command == "subagent-start":
        exit_code = handle_subagent_start()
    elif command == "subagent-stop":
        exit_code = handle_subagent_stop()
    else:
        print(json.dumps({"status": "error", "reason": f"Unknown command: {command}"}))
        exit_code = 1

    sys.exit(exit_code)


if __name__ == "__main__":
    main()
