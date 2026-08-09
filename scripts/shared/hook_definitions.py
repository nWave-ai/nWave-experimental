"""Canonical DES hook definitions -- the fixed, always-installed set.

Both the plugin builder (build_plugin.py) and the custom installer
(des_plugin.py) generate Claude Code hook configurations for the FIXED set of
hooks below. This module provides the shared definitions so THAT set's hook
events, matchers, and actions have a single definition site, not two
independently-maintained copies.

The two distribution paths differ only in HOW the Python command is
constructed (plugin uses CLAUDE_PLUGIN_ROOT, installer uses $HOME),
not in WHAT hooks are registered.

SCOPE DISCLAIMER: this module is NOT the complete registry of every
`hooks.PreToolUse` entry this repo can write into `~/.claude/settings.json`.
`scripts/install/attribution_utils.py` (`register_attribution_hook`) builds
and writes an INDEPENDENT `PreToolUse`/`Bash` entry (action
`pre-commit-attribution`) with its own on/off lifecycle, gated by
`attribution.enabled` in the DES config and toggled without touching the
install manifest -- it is invisible to `HOOK_EVENTS` and to this module's own
exhaustive test. An audit, count, or invariant that wants "every PreToolUse
hook this repo can register" must ALSO consult `attribution_utils.py`; this
module alone answers only "every hook the fixed install/plugin manifest
writes."
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


# Pure-shell wrapper around the git-stash guard PreToolUse hook (slice-01 of
# fix-crafter-stash-structural-mitigation). The shell wrapper buffers stdin
# (the hook event JSON), greps the bash command for `^\s*git\s+stash\b` as a
# shell-fast-path (avoiding a Python interpreter startup on every non-stash
# Bash invocation), and only then invokes the Python entry point.
#
# Matcher coexistence: Claude Code's PreToolUse protocol permits
# multiple registrations per (event, matcher) tuple; execution is
# registration-ordered; ANY hook returning `{decision: block}` blocks the tool
# invocation. The git-stash guard greps for `^git stash` only -- orthogonal to
# the execution-log grep and the other independent guards -- so a `git stash
# push` matches only this guard and its block decision wins by construction.
#
# Uses module-import form (`python3 -m scripts.hooks.git_stash_guard`) and does
# not bake `$HOME` into the shell command, so it
# remains valid in BOTH installer-path AND plugin-bundle distribution modes. The
# DES_HOOKS list in `des_plugin.py` ships the script file to the operator's
# `~/.claude/scripts/` tree so the module resolves at runtime.
_BASH_GIT_STASH_GUARD = (
    "# des-hook:pre-bash-git-stash-guard\n"
    "INPUT=$(cat); "
    "CMD=$(printf '%s' \"$INPUT\" | python3 -c "
    '"import sys,json; print(json.load(sys.stdin)'
    ".get('tool_input',{}).get('command',''))\"); "
    "printf '%s' \"$CMD\" | grep -qE '^\\s*git\\s+stash\\b' || exit 0; "
    "printf '%s' \"$INPUT\" | python3 -m scripts.hooks.git_stash_guard"
)

# Pure-shell wrapper around the worktree-removal guard
# (fix-worktree-removal-liveness-guard, Ale-authorised 2026-07-29). This is
# the removal-time CONSUMER of the Sentinel's own read-only "worktree
# anti-rot triage" predicate (`nWave/skills/nw-throughput/SKILL.md`
# "Throughput Sentinel"; `des.domain.worktree_anti_rot_triage.
# triage_worktree`) -- the Sentinel never removes a worktree itself, so this
# is the separate component that acts on its receipt. Mirrors
# `_BASH_GIT_STASH_GUARD`'s shape exactly: the shell fast-path greps the
# command for `git worktree remove` (cheap pre-filter; the Python hook does
# the precise tokenized detection -- a raw grep would false-negative a
# `git worktree remove` buried after `&&`/`;` and false-positive on the
# phrase inside a quoted commit message, which is why the Python layer
# re-checks with `shlex`) and only then invokes the Python entry point.
#
# Matcher coexistence: this entry joins the existing PreToolUse/Bash roster
# alongside the independent execution-log and git-stash guards.
# Claude Code permits multiple registrations per (event,
# matcher) tuple; execution is registration-ordered; ANY hook returning
# `{decision: block}` blocks the tool invocation. This guard greps for
# `git worktree remove` only -- orthogonal to every other Bash entry's grep,
# so its block decision wins by construction on a match.
#
# Uses module-import form (no `$HOME`) so it is valid in BOTH
# installer-path AND plugin-bundle distribution modes; `des_plugin.py:
# DES_HOOKS` ships `worktree_removal_guard.py` to the operator's
# `~/.claude/scripts/` tree so the module resolves at runtime.
_BASH_WORKTREE_REMOVAL_GUARD = (
    "# des-hook:pre-bash-worktree-removal-guard\n"
    "INPUT=$(cat); "
    "CMD=$(printf '%s' \"$INPUT\" | python3 -c "
    '"import sys,json; print(json.load(sys.stdin)'
    ".get('tool_input',{}).get('command',''))\"); "
    "printf '%s' \"$CMD\" | grep -qE 'git\\s+worktree\\s+remove' || exit 0; "
    "printf '%s' \"$INPUT\" | python3 -m scripts.hooks.worktree_removal_guard"
)

# Canonical hook event definitions -- the ONLY place these are defined.
# Order matters: PreToolUse/Agent must come before Write/Edit guards. The
# Each registration is independently useful; avoid introducing a protocol chain
# that makes a normal coding action depend on historical workflow bookkeeping.
#
# fix-worktree-removal-liveness-guard (Ale-authorised 2026-07-29): 1 new entry
# joins -- PreToolUse/Bash for the worktree-removal liveness guard (3rd Bash
# entry; greps `git worktree remove`, orthogonal to every other Bash entry's
# grep). Blocks a `git worktree remove` while a live process's cwd is inside
# the target, the target carries an explicit `git worktree lock`, or the
# target's branch carries unmerged commits -- closing the incident where a
# clean `git status` was mistaken for "safe to remove" while a lane's pytest
# run was still live inside the worktree.
#
# The standalone execution-log Bash guard (_BASH_EXECUTION_LOG_GUARD) was
# removed (Ale-authorised): the nested/duplicate registration it produced
# under some install paths is retired via des_plugin.py's retired-command
# tombstone. The universal `pre-tool-use` action below (registered
# unconditionally on PreToolUse/Bash) remains installed and unaffected.
# Write/Edit execution-log refusal is unchanged -- see build_guard_command.
HOOK_EVENTS: tuple[HookEvent, ...] = (
    HookEvent(event="PreToolUse", matcher="Agent", action="pre-task"),
    HookEvent(event="PreToolUse", matcher="Write", action="pre-write", is_guard=True),
    HookEvent(event="PreToolUse", matcher="Edit", action="pre-edit", is_guard=True),
    HookEvent(
        event="PreToolUse",
        matcher="Bash",
        action="pre-bash-git-stash-guard",
        shell_command=_BASH_GIT_STASH_GUARD,
    ),
    HookEvent(
        event="PreToolUse",
        matcher="Bash",
        action="pre-bash-worktree-removal-guard",
        shell_command=_BASH_WORKTREE_REMOVAL_GUARD,
    ),
    # Universal root mode-selection gate. Unlike the specialised Bash guards
    # above, this uses the distribution's portable DES module command so the
    # existing pre_tool_use handler is reached on every installed Bash event.
    HookEvent(event="PreToolUse", matcher="Bash", action="pre-tool-use"),
    HookEvent(event="PostToolUse", matcher="Agent", action="post-tool-use"),
    HookEvent(event="SubagentStop", matcher=None, action="subagent-stop"),
    HookEvent(event="SubagentStart", matcher=None, action="subagent-start"),
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
    3. If a deliver-session.json is active, invokes Python for full DES
       enforcement
    4. Otherwise (no active session), invokes Python ONLY when the target path
       looks nWave-adjacent (`src/`, `nWave/`, `tests/`, `scripts/`) -- a
       coarse, over-inclusive shell-level pre-filter; the authoritative
       pertinence check (which also excludes `.nwave/**`) lives in
       `root_activation_context.is_nwave_adjacent_write` and runs inside
       Python. This lets K3-A's root-activation reminder reach root's own
       direct Write/Edit (no sub-agent dispatch, no deliver session) without
       spawning Python on irrelevant writes (telemetry, unrelated repos).
    5. Otherwise, exits 0 (fast path, unchanged for irrelevant/out-of-tree
       writes)

    Args:
        python_cmd: The full Python command string (PYTHONPATH=... python3 -m ...)
            WITHOUT the action suffix. The action will be appended by the caller.

    Returns:
        Shell command template string. The caller must format it with the action.
    """
    return (  # noqa: UP032 — .format() required for shell template with literal braces
        "INPUT=$(cat); "
        "printf '%s' \"$INPUT\" | grep -q 'execution-log\\.json' && "
        "{{ printf '%s' \"$INPUT\" | {python_cmd}; exit $?; }}; "
        "test -f .nwave/des/deliver-session.json && "
        "{{ printf '%s' \"$INPUT\" | {python_cmd}; exit $?; }}; "
        'printf \'%s\' "$INPUT" | grep -qE \'"file_path"[[:space:]]*:[[:space:]]*"[^"]*'
        "(/src/|/nWave/|/tests/|/scripts/)' && "
        "{{ printf '%s' \"$INPUT\" | {python_cmd}; exit $?; }}; "
        "exit 0"
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
