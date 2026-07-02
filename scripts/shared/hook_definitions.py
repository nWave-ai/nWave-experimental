"""Canonical DES hook definitions -- single source of truth.

Both the plugin builder (build_plugin.py) and the custom installer
(des_plugin.py) generate Claude Code hook configurations. This module
provides the shared definitions so hook events, matchers, and actions
are defined exactly once.

The two distribution paths differ only in HOW the Python command is
constructed (plugin uses CLAUDE_PLUGIN_ROOT, installer uses $HOME),
not in WHAT hooks are registered.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class HookEvent:
    """A single DES hook event registration.

    Attributes:
        event: Claude Code hook event type (e.g., "PreToolUse").
        matcher: Optional matcher string (e.g., "Agent", "Write").
            None means the hook fires for all invocations of that event.
        action: DES adapter action string (e.g., "pre-task").
        is_guard: Whether this hook uses the shell fast-path guard
            (only for Write/Edit hooks that need to check for active
            deliver sessions before spawning Python).
        shell_command: Verbatim shell command string. When set,
            generate_hook_config uses this directly instead of
            command_fn or guard_command_fn. No Python handler needed.
    """

    event: str
    matcher: str | None
    action: str
    is_guard: bool = False
    shell_command: str | None = None


# Pure-shell guard for Bash commands that target execution-log.json.
# The "# des-hook:pre-bash;" prefix is a shell comment (no-op) that serves
# as a DES marker string for is_des_hook_entry detection.
_BASH_EXECUTION_LOG_GUARD = (
    "# des-hook:pre-bash\n"
    "INPUT=$(cat); "
    'CMD=$(echo "$INPUT" | python3 -c '
    '"import sys,json; print(json.load(sys.stdin)'
    ".get('tool_input',{}).get('command',''))\"); "
    "echo \"$CMD\" | grep -q 'execution-log' || exit 0; "
    'echo "$CMD" | grep -qE '
    "'des\\.cli\\.(log_phase|init_log|verify_deliver_integrity)|"
    "des +(log-phase|init-log|verify-integrity)' && exit 0; "
    'echo \'{"decision":"block","reason":"Direct modification of '
    "execution-log.json via Bash is blocked.\\n"
    "To read it, use the Read tool.\\n"
    "To modify it, use the des log-phase subcommand.\"}'; "
    "exit 2"
)

# Pure-shell wrapper around the spine-ledger PreToolUse hook (slice-02 of
# atdd-spine-ledger-enforcement-gate-v2). The shell wrapper buffers stdin
# (the hook event JSON), greps the bash command for `^git commit` as a
# shell-fast-path (avoiding a Python interpreter startup on every non-
# commit Bash invocation), and only then invokes the Python entry point.
#
# Matcher coexistence: this entry is registered as a NEW HookEvent ADJACENT
# to `_BASH_EXECUTION_LOG_GUARD` (do NOT modify the existing guard). Claude
# Code's PreToolUse protocol permits multiple registrations per
# (event, matcher) tuple; execution is registration-ordered; ANY hook
# returning `{decision: block}` blocks the tool invocation. The execution-
# log guard does NOT block git-commit commands (its `grep -q 'execution-log'`
# test fails on a git-commit command line, so it exits 0 silently). The
# spine-ledger hook's block decision therefore wins by construction.
#
# Stdin is consumed twice: once by the shell to grep the command, once by
# the Python hook to parse the full event payload. Both reads see the same
# buffered `$INPUT` so the Python hook's stdin carries the original event.
#
# The `$HOME` placeholder is the installed-artifact root. When the installer
# plugin registers this entry (slice-04), it substitutes the real path; in
# dev mode the entry is invoked via `python -m scripts.hooks.spine_ledger_pre_commit_hook`
# directly through the repo root.
_BASH_SPINE_LEDGER_PRE_COMMIT_HOOK = (
    "# des-hook:pre-bash-spine-ledger\n"
    "INPUT=$(cat); "
    'CMD=$(echo "$INPUT" | python3 -c '
    '"import sys,json; print(json.load(sys.stdin)'
    ".get('tool_input',{}).get('command',''))\"); "
    "echo \"$CMD\" | grep -qE '^\\s*git\\s+commit\\b' || exit 0; "
    'echo "$INPUT" | python3 -m scripts.hooks.spine_ledger_pre_commit_hook'
)

# Pure-shell wrapper around the spine-ledger gate as a SECOND PreToolUse/Bash
# entry, slice-04 of atdd-spine-ledger-enforcement-gate-v2. This entry is the
# defense-in-depth companion to `_BASH_SPINE_LEDGER_PRE_COMMIT_HOOK`: it
# invokes the production gate script DIRECTLY (rather than through the
# pre-commit-hook wrapper) so the gate's verdict-emission contract is
# observable even when the wrapper script is absent or being upgraded.
#
# It deliberately does NOT reference `spine_ledger_pre_commit_hook` in its
# command text: the PreToolUse/Bash count must reach 6 post-slice-04 per
# AT-3 pin, while AT-1 demands EXACTLY ONE entry textually naming
# `spine_ledger_pre_commit_hook` (the slice-02 wrapper). This second entry
# satisfies "+1 PreToolUse" without colliding with AT-1's substring filter.
#
# Uses module-import form (`python3 -m scripts.hooks.spine_ledger_gate`)
# mirroring the slice-02 entry's pattern — does NOT bake `$HOME` into the
# shell command so it remains valid in BOTH installer-path AND plugin-bundle
# distribution modes (plugin bundle adds `scripts/hooks/` to sys.path via
# its discovery wrapper; installer ships the same package at the deployed
# location). The DES_HOOKS list in `des_plugin.py` ensures the script files
# arrive at `<claude_dir>/scripts/` so the operator's PATH/sys.path can
# resolve the module at runtime.
_BASH_SPINE_LEDGER_GATE_INSTALLED = (
    "# des-hook:pre-bash-spine-ledger-gate-installed\n"
    "INPUT=$(cat); "
    'CMD=$(echo "$INPUT" | python3 -c '
    '"import sys,json; print(json.load(sys.stdin)'
    ".get('tool_input',{}).get('command',''))\"); "
    "echo \"$CMD\" | grep -qE '^\\s*git\\s+commit\\b' || exit 0; "
    "python3 -m scripts.hooks.spine_ledger_gate "
    "--commit-msg-file .git/COMMIT_EDITMSG "
    "--ledger-root .nwave/telemetry/atdd-pure "
    "--target-root . >/dev/null 2>&1 || true"
)

# Pure-shell wrapper around the git-stash guard PreToolUse hook (slice-01 of
# fix-crafter-stash-structural-mitigation). The shell wrapper buffers stdin
# (the hook event JSON), greps the bash command for `^\s*git\s+stash\b` as a
# shell-fast-path (avoiding a Python interpreter startup on every non-stash
# Bash invocation), and only then invokes the Python entry point. Mirrors the
# `_BASH_SPINE_LEDGER_PRE_COMMIT_HOOK` pattern exactly.
#
# Matcher coexistence: this entry is the 4th PreToolUse/Bash registration,
# ADJACENT to the execution-log guard + the two spine-ledger entries (do NOT
# modify any existing entry). Claude Code's PreToolUse protocol permits
# multiple registrations per (event, matcher) tuple; execution is
# registration-ordered; ANY hook returning `{decision: block}` blocks the tool
# invocation. The git-stash guard greps for `^git stash` only -- orthogonal to
# the execution-log grep, the `^git commit` grep, and the best-effort gate -- so
# a `git stash push` matches ONLY this guard and its block decision wins by
# construction; the other three exit 0 silently on a `git stash` command.
#
# Uses module-import form (`python3 -m scripts.hooks.git_stash_guard`) mirroring
# the spine-ledger entries -- does NOT bake `$HOME` into the shell command so it
# remains valid in BOTH installer-path AND plugin-bundle distribution modes. The
# DES_HOOKS list in `des_plugin.py` ships the script file to the operator's
# `~/.claude/scripts/` tree so the module resolves at runtime.
_BASH_GIT_STASH_GUARD = (
    "# des-hook:pre-bash-git-stash-guard\n"
    "INPUT=$(cat); "
    'CMD=$(echo "$INPUT" | python3 -c '
    '"import sys,json; print(json.load(sys.stdin)'
    ".get('tool_input',{}).get('command',''))\"); "
    "echo \"$CMD\" | grep -qE '^\\s*git\\s+stash\\b' || exit 0; "
    'echo "$INPUT" | python3 -m scripts.hooks.git_stash_guard'
)

# Pure-shell wrapper around the --no-verify reminder guard (lean reminder,
# Ale 2026-06-26). The shell fast-path greps the bash command for a `git` token
# (cheap pre-filter; the Python hook does the precise tokenized detection) and
# only then invokes the Python entry point. Mirrors `_BASH_GIT_STASH_GUARD`.
#
# Matcher coexistence: this entry is the 5th PreToolUse/Bash registration,
# ADJACENT to the execution-log guard + the two spine-ledger entries + the
# git-stash guard (do NOT modify any existing entry). Claude Code's PreToolUse
# protocol permits multiple registrations per (event, matcher) tuple; execution
# is registration-ordered; ANY hook returning `{decision: block}` blocks the
# tool invocation. The no-verify guard fires ONLY on a real git verify-bypass
# flag (`--no-verify` / `--no-gpg-sign`, or `-n` on `git commit`); its block
# decision is orthogonal to the other four Bash entries, which grep different
# command shapes and exit 0 silently on a plain bypass commit.
#
# The reminder is durable across installs because it lives in the DES HOOK_EVENTS
# SSOT (carrying the `# des-hook:` marker) — a manual settings.json edit would be
# dropped on the next install (the gotcha this entry fixes). Uses module-import
# form (no `$HOME`) so it is valid in BOTH installer-path AND plugin-bundle
# distribution modes; `des_plugin.py:DES_HOOKS` ships `no_verify_reminder.py` to
# the operator's `~/.claude/scripts/hooks/` tree so the module resolves at runtime.
_BASH_NO_VERIFY_REMINDER = (
    "# des-hook:pre-bash-no-verify-reminder\n"
    "INPUT=$(cat); "
    'CMD=$(echo "$INPUT" | python3 -c '
    '"import sys,json; print(json.load(sys.stdin)'
    ".get('tool_input',{}).get('command',''))\"); "
    "echo \"$CMD\" | grep -qE '\\bgit\\b' || exit 0; "
    'echo "$INPUT" | python3 -m scripts.hooks.no_verify_reminder'
)

# Pure-shell wrapper around the slice-03 spine-ledger SubagentStop detector,
# slice-04 of atdd-spine-ledger-enforcement-gate-v2. Mirrors the slice-02
# module-import pattern (`python3 -m
# scripts.hooks.spine_ledger_subagent_stop_detector`) — does NOT bake `$HOME`
# into the shell command so it remains valid in BOTH installer-path AND
# plugin-bundle distribution modes.
_SUBAGENT_STOP_SPINE_LEDGER_DETECTOR_INSTALLED = (
    "# des-hook:subagent-stop-spine-detector\n"
    "INPUT=$(cat); "
    'echo "$INPUT" | python3 -m scripts.hooks.spine_ledger_subagent_stop_detector'
)

# Harness-neutral declare-done backstop -- the git pre-push done-gate
# (f-nonbypassable-attestation slice-01, DDD-2). The terminal "declare a feature
# done" action in the dogfood is a `git push`; this is the missing harness-neutral
# surface that auto-fires the SAME portable done-gate core (`des verify-integrity`
# / `verify_deliver_integrity`) on the terminal push, INDEPENDENT of the
# Claude-Code F_FINAL_REVIEW SubagentStop the incident's hand-dispatch never
# reached. It adds NO new decision logic -- a thin DDD-7 shim that REUSES
# `des_declare_done_pre_push` (which delegates to `verify_deliver_integrity.main`)
# and PROPAGATES its veto (a non-zero exit aborts the push).
#
# RETIRED (fix-pre-push-hook-dual-installer-collision RCA, slice-01): the
# `_GIT_PRE_PUSH_DECLARE_DONE_BACKSTOP` shim template + `render_pre_push_backstop_shim`
# that used to render it into `.git/hooks/pre-push` (chaining any pre-existing
# hook aside) are REMOVED -- that second writer of the SAME file
# `pre-commit install` also writes tripped `verify-hooks`'s foreign-hook
# detector. RCA: docs/analysis/root-cause-analysis-pre-push-hook-dual-installer-collision.md
# The backstop's BEHAVIOR is unchanged and still fires -- it is now a `local`
# `stages: [pre-push]` hook in `.pre-commit-config.yaml`, so `pre-commit install`
# is the SOLE writer of `.git/hooks/pre-push`.
#
# The pre-push backstop's Python entry module (the DDD-7 thin shim that delegates
# to the portable `verify_deliver_integrity` done-gate). The DES plugin still
# ships this script alongside the other DES_HOOKS (deployed to
# ~/.claude/scripts/) so the `.pre-commit-config.yaml` local hook can invoke it.
GIT_PRE_PUSH_BACKSTOP_SCRIPT = "des_declare_done_pre_push.py"


# Canonical hook event definitions -- the ONLY place these are defined.
# Order matters: PreToolUse/Agent must come before Write/Edit guards. The
# spine-ledger PreToolUse/Bash entries are registered AFTER the execution-log
# guard (registration order = Claude Code execution order); the spine-ledger
# entries can block git-commit commands lacking ledger evidence while the
# execution-log guard silently approves them.
#
# Slice-04 (FINAL of F-ATDD-SPINE-LEDGER-ENFORCEMENT-GATE-v2): 2 new entries
# joined the registry -- PreToolUse/Bash for the installed-path spine-ledger
# GATE (#5 -> #6 PreToolUse; uses gate script directly so AT-1's substring
# filter on `spine_ledger_pre_commit_hook` still matches exactly the slice-02
# entry), and SubagentStop for the installed-path spine-ledger detector
# (#2 -> #3 SubagentStop). Total grew 10 -> 12.
#
# slice-01 of fix-crafter-stash-structural-mitigation: 1 new entry joins --
# PreToolUse/Bash for the git-stash guard (4th Bash entry; #6 -> #7 PreToolUse;
# greps `^git stash`, orthogonal to the other three Bash entries). Total grows
# 12 -> 13.
#
# slice-04 amendment of nwave-flow-v2-enforcement (post-install smoke finding
# #2): 1 new entry joins -- UserPromptSubmit for the wave-active anchor
# (`hook_router` dispatches action `user-prompt-submit` to
# `user_prompt_submit_handler.handle_user_prompt_submit`). The handler is a
# deterministic no-op on non-`/nw-<wave>` prompts (NoWaveActive, zero writes),
# so firing on every prompt is safe. No matcher (UserPromptSubmit has no tool
# matcher). Total grows 13 -> 14; event types 5 -> 6.
#
# --no-verify reminder guard (Ale 2026-06-26): 1 new entry joins -- PreToolUse/
# Bash for the lean verify-bypass reminder (5th Bash entry; #7 -> #8 PreToolUse;
# greps `\bgit\b` fast-path then the Python hook tokenizes for a real bypass flag,
# orthogonal to the other four Bash entries). Lives in the SSOT so the reminder
# survives the install-time settings.json rewrite that drops manual hook edits.
# Total grows 14 -> 15.
HOOK_EVENTS: tuple[HookEvent, ...] = (
    HookEvent(event="PreToolUse", matcher="Agent", action="pre-task"),
    HookEvent(event="PreToolUse", matcher="Write", action="pre-write", is_guard=True),
    HookEvent(event="PreToolUse", matcher="Edit", action="pre-edit", is_guard=True),
    HookEvent(
        event="PreToolUse",
        matcher="Bash",
        action="pre-bash",
        shell_command=_BASH_EXECUTION_LOG_GUARD,
    ),
    HookEvent(
        event="PreToolUse",
        matcher="Bash",
        action="pre-bash-spine-ledger",
        shell_command=_BASH_SPINE_LEDGER_PRE_COMMIT_HOOK,
    ),
    HookEvent(
        event="PreToolUse",
        matcher="Bash",
        action="pre-bash-spine-ledger-gate-installed",
        shell_command=_BASH_SPINE_LEDGER_GATE_INSTALLED,
    ),
    HookEvent(
        event="PreToolUse",
        matcher="Bash",
        action="pre-bash-git-stash-guard",
        shell_command=_BASH_GIT_STASH_GUARD,
    ),
    HookEvent(
        event="PreToolUse",
        matcher="Bash",
        action="pre-bash-no-verify-reminder",
        shell_command=_BASH_NO_VERIFY_REMINDER,
    ),
    HookEvent(event="PostToolUse", matcher="Agent", action="post-tool-use"),
    HookEvent(event="SubagentStop", matcher=None, action="subagent-stop"),
    HookEvent(event="SubagentStop", matcher=None, action="deliver-progress"),
    HookEvent(
        event="SubagentStop",
        matcher=None,
        action="subagent-stop-spine-detector",
        shell_command=_SUBAGENT_STOP_SPINE_LEDGER_DETECTOR_INSTALLED,
    ),
    HookEvent(event="SessionStart", matcher="startup", action="session-start"),
    HookEvent(event="SubagentStart", matcher=None, action="subagent-start"),
    HookEvent(event="UserPromptSubmit", matcher=None, action="user-prompt-submit"),
)

# The distinct event types DES registers (for validation).
HOOK_EVENT_TYPES: frozenset[str] = frozenset(h.event for h in HOOK_EVENTS)


def generate_hook_config(
    command_fn: callable,
    guard_command_fn: callable | None = None,
) -> dict[str, list[dict]]:
    """Generate hooks config in Claude Code hooks.json format.

    Args:
        command_fn: Callable(action: str) -> str that produces the
            hook command string for a given action. Each distribution
            path provides its own (plugin vs installer paths).
        guard_command_fn: Optional callable(action: str) -> str for
            Write/Edit guard hooks that use shell fast-path. If None,
            guard hooks use command_fn instead (no fast-path).

    Returns:
        Dict mapping event names to lists of hook entries, matching
        the Claude Code hooks.json schema:
        {"EventName": [{"matcher": "...", "hooks": [{"type": "command", "command": "..."}]}]}
    """
    config: dict[str, list[dict]] = {}

    for hook_event in HOOK_EVENTS:
        if hook_event.shell_command is not None:
            command = hook_event.shell_command
        elif hook_event.is_guard and guard_command_fn is not None:
            command = guard_command_fn(hook_event.action)
        else:
            command = command_fn(hook_event.action)

        entry: dict = {"hooks": [{"type": "command", "command": command}]}
        if hook_event.matcher is not None:
            entry["matcher"] = hook_event.matcher

        config.setdefault(hook_event.event, []).append(entry)

    return config


def build_guard_command(python_cmd: str) -> str:
    """Build the shell fast-path guard command template for Write/Edit hooks.

    The guard:
    1. Buffers stdin (hook input JSON)
    2. If the target is execution-log.json, always invokes Python (unconditional)
    3. Otherwise, checks for deliver-session.json -- exits 0 if absent (fast path)
    4. If present, invokes Python for full DES enforcement

    Args:
        python_cmd: The full Python command string (PYTHONPATH=... python3 -m ...)
            WITHOUT the action suffix. The action will be appended by the caller.

    Returns:
        Shell command template string. The caller must format it with the action.
    """
    return (  # noqa: UP032 — .format() required for shell template with literal braces
        "INPUT=$(cat); "
        "echo \"$INPUT\" | grep -q 'execution-log\\.json' && "
        '{{ echo "$INPUT" | {python_cmd}; exit $?; }}; '
        "test -f .nwave/des/deliver-session.json || exit 0; "
        'echo "$INPUT" | {python_cmd}'
    ).format(python_cmd=python_cmd)


def _is_des_command(command: str) -> bool:
    """Check if a command string belongs to DES.

    Detects:
    - Python-based hooks via module name (claude_code_hook_adapter)
    - Python-based hooks via module path (des.adapters.drivers.hooks)
    - Shell-based hooks via marker prefix (# des-hook:)

    Multiple markers provide defense-in-depth: if the adapter module is
    renamed or the command format changes between versions, at least one
    marker should still match, preventing duplicate hooks on upgrade.
    """
    return (
        "claude_code_hook_adapter" in command
        or "des-hook:" in command
        or "des.adapters.drivers.hooks" in command
    )


def is_des_hook_entry(hook_entry: dict) -> bool:
    """Check if a hook entry is a DES hook.

    Supports old flat format, new nested format, and shell-based hooks:
    - Old flat: {"command": "...claude_code_hook_adapter..."}
    - New nested: {"hooks": [{"type": "command", "command": "...claude_code_hook_adapter..."}]}
    - Shell-based: {"hooks": [{"type": "command", "command": "# des-hook:pre-bash; ..."}]}

    Args:
        hook_entry: Hook entry dictionary from settings JSON.

    Returns:
        True if entry is a DES hook.
    """
    # Check old flat format
    if _is_des_command(hook_entry.get("command", "")):
        return True
    # Check new nested format
    for h in hook_entry.get("hooks", []):
        if _is_des_command(h.get("command", "")):
            return True
    return False
