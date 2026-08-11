"""Canonical DES hook definitions -- the fixed, always-installed set.

Both the plugin builder (build_plugin.py) and the custom installer
(des_plugin.py) generate Claude Code hook configurations for the FIXED set of
hooks below. This module provides the shared definitions so THAT set's hook
events, matchers, and actions have a single definition site, not two
independently-maintained copies.

The two distribution paths differ only in HOW the Python command is
constructed (plugin uses CLAUDE_PLUGIN_ROOT, installer uses $HOME),
not in WHAT hooks are registered.

HOOK_EVENTS is the installed hook SSOT for the fixed manifest.
"""

from __future__ import annotations

import re
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
# fix-execution-log-bash-guard-consolidation follow-on (Ale-authorised
# 2026-08-09): the standalone git-stash guard registration below is retired
# -- the pre-activation universal `hook_router` call now evaluates the same
# `bash_command_guards.evaluate_git_stash_command` decision inline on every
# installed PreToolUse/Bash invocation, so a second, independently-scheduled
# Python process is no longer needed. The exact retired command string is
# tombstoned in `des_plugin.py:_RETIRED_HOOK_COMMANDS` so upgrade removes
# the stale nested registration.

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
# fix-execution-log-bash-guard-consolidation follow-on (Ale-authorised
# 2026-08-09): the standalone worktree-removal guard registration below is
# retired for the same reason as the git-stash guard above -- the
# pre-activation universal `hook_router` call now evaluates
# `bash_command_guards.evaluate_worktree_remove_command` inline. The exact
# retired command string is tombstoned in
# `des_plugin.py:_RETIRED_HOOK_COMMANDS`.

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
    # Root-activation single-pass guard (K4 overhead slice): routes
    # PreToolUse/SendMessage to the existing portable pre-tool-use action --
    # no new hook implementation, process, controller, state, ledger, or
    # schema. See pre_tool_use_handler.handle_pre_tool_use's SendMessage
    # branch for the decision itself.
    HookEvent(event="PreToolUse", matcher="SendMessage", action="pre-tool-use"),
    HookEvent(event="PreToolUse", matcher="Write", action="pre-write", is_guard=True),
    HookEvent(event="PreToolUse", matcher="Edit", action="pre-edit", is_guard=True),
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


_DES_MODULE_INVOCATION = "-m des.adapters.drivers.hooks.claude_code_hook_adapter"

# Old (pre-`-m`) flat, path-style invocation the installer used to emit:
# `python3 src/des/adapters/drivers/hooks/claude_code_hook_adapter.py <action>`.
# Anchored at the start of the command and restricted to the known action
# vocabulary below -- not a bare substring check -- so it matches only the
# exact historical structure the installer wrote, never a foreign command
# that merely mentions the script path (see WTBD-165 / issue97 falsifiers).
_LEGACY_SCRIPT_INVOCATION_RE = re.compile(
    r"^python3?\s+src/des/adapters/drivers/hooks/claude_code_hook_adapter\.py\s+(\S+)"
)

_KNOWN_HOOK_ACTIONS: frozenset[str] = frozenset(h.action for h in HOOK_EVENTS)


def _is_des_command(command: str) -> bool:
    """Check if a command string is an installer-owned DES hook command.

    Recognizes only the positive structures the installer actually emits
    (present or historical), not bare substrings:
    - Python-based hooks via the exact module invocation
      (`-m des.adapters.drivers.hooks.claude_code_hook_adapter`), the form
      `_generate_hook_command`'s `HOOK_COMMAND_TEMPLATE` produces.
    - The legacy flat, path-style invocation
      (`python3 src/des/adapters/drivers/hooks/claude_code_hook_adapter.py
      <action>`) the installer used to emit before the `-m` module form,
      restricted to a known hook action so it stays a positive structural
      match rather than a substring check.
    - Shell-based hooks via the leading marker (`# des-hook:...`), which
      every shell hook command starts with (see `_RETIRED_HOOK_COMMANDS`).

    A bare-substring check (e.g. `"claude_code_hook_adapter" in command`)
    also matches unrelated user commands that merely mention the module
    name or path (`echo des.adapters.drivers.hooks`, `grep
    claude_code_hook_adapter .`), which would delete them on
    install/uninstall. Requiring the full `-m <module>` invocation, the
    exact legacy script-path structure with a known action, and anchoring
    the shell marker to the start of the command excludes those false
    positives while still matching every command the installer itself
    writes (present or historical).
    """
    if _DES_MODULE_INVOCATION in command or command.startswith("# des-hook:"):
        return True
    legacy_match = _LEGACY_SCRIPT_INVOCATION_RE.match(command)
    return legacy_match is not None and legacy_match.group(1) in _KNOWN_HOOK_ACTIONS


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


def strip_des_hooks_from_entries(entries: list) -> list:
    """Remove DES-owned commands from a hook-event's entry list.

    An old flat entry whose own command is DES-owned is dropped outright.
    A nested entry may bundle a DES hook alongside an unrelated sibling
    hook (e.g. a user's own Bash hook) under the same matcher; only the
    DES-owned nested hooks are removed, so the sibling and all entry
    metadata survive. The entry itself is dropped only once stripping
    leaves it with no hooks at all.
    """
    result = []
    for entry in entries:
        if _is_des_command(entry.get("command", "")):
            continue
        hooks = entry.get("hooks")
        if hooks is None:
            result.append(entry)
            continue
        retained_hooks = [h for h in hooks if not _is_des_command(h.get("command", ""))]
        if not retained_hooks:
            continue
        if len(retained_hooks) != len(hooks):
            result.append({**entry, "hooks": retained_hooks})
        else:
            result.append(entry)
    return result
