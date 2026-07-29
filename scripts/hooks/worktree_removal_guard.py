#!/usr/bin/env python3
"""worktree-removal guard -- PreToolUse/Bash hook consuming the Sentinel's
worktree anti-rot triage predicate.

fix-worktree-removal-liveness-guard (Ale-authorised 2026-07-29). CORRECTED
same day, team-lead: this is NOT a new mechanism -- it is the removal-time
CONSUMER of the Sentinel's own "worktree anti-rot triage" predicate
(`nWave/skills/nw-throughput/SKILL.md` "Throughput Sentinel",
`des.domain.worktree_anti_rot_triage.triage_worktree`). The Sentinel is
READ-ONLY by spec ("it never removes a worktree automatically"); this hook
is the SEPARATE component that acts on its receipt, so no single component
both judges and deletes.

Root incident: the session orchestrator removed a LIVE lane's worktree
three times in one session: each time it ran `git status --short`, saw a
clean tree, and concluded "safe" -- but `git status` answers "is it
dirty?", never "is it LIVE?", and git has no notion of the latter. The
third time, a lane was running pytest inside that directory; the removal
crashed the test with `FileNotFoundError` on its own cwd and the branch ref
briefly vanished. This hook replaces "did you check?" (a confirmation
prompt collects confident-but-wrong yeses, which is exactly what failed)
with a decision on the PROPERTY (GDP-8): what does the triage predicate's
receipt say.

Consumption rule: ALLOW the removal iff the receipt's state is `CLEAN`
(convergent evidence of no liveness AND nothing at risk -- there is nothing
to decide). Every other state -- `LIVE`, `ABANDONED_CANDIDATE` (liveness
clear, but unintegrated/dirty work is at stake and needs a HUMAN pick among
MERGE/RESUME/DEFER/REMOVE), and `INDETERMINATE` (could not verify) -- BLOCKS
until a human authorises the override.

A STANDALONE Claude Code PreToolUse/Bash hook, mirroring the shape of
`scripts/hooks/git_stash_guard.py` and `scripts/hooks/no_verify_reminder.py`
(tokenized command parsing -- a raw regex would false-negative on a `git
worktree remove` buried after a `&&`, and false-positive on the phrase
appearing inside a quoted commit message). On a match it collects the four
evidence signals the triage predicate consumes -- through `ProcessCwdProbePort`
(a live process's cwd inside the target) and `WorktreeRemovalSafetyPort`
(`git worktree lock`, dirty state, unmerged commits) -- then asks
`triage_worktree` for a receipt.

Located as a HOOK, not a `des` subcommand, because the incident is a
forgetting failure: a hook fires whether or not anyone remembers to run a
check, which is the exact property a subcommand cannot offer (Ale's brief:
"a hook fires whether or not anyone remembers it -- that is the whole
point"). Mirrors the DES_HOOKS shipping pattern: this script is listed in
`scripts/install/plugins/des_plugin.py:DESPlugin.DES_HOOKS` and wired via
`scripts/shared/hook_definitions.py` so it survives the install-time
settings.json rewrite the same way the git-stash guard does.

Override (human authorisation, not a self-granted convenience flag): a
BLOCK is bypassed ONLY when `NWAVE_WORKTREE_REMOVE_REASON` carries a
non-trivial justification string (>= 15 characters after stripping -- a bare
`1`/`true`/`yes` does not qualify). The reason is logged VERBATIM to a
`WorktreeRemovalBypassUsed` audit event, mirroring
`git_stash_guard.py`'s `NWAVE_GIT_STASH_ALLOW` kill-switch + audit pattern,
but shaped after `des wave-clear --reason`'s discipline (a REQUIRED prose
justification, not a truthy toggle) so that writing the override is visibly
an attributable authorisation act, not something to blindly `export ...=1`.
This is also the mechanical stand-in for the Sentinel's human-picks-one-of-
four-actions step: writing the reason IS the human's REMOVE decision,
recorded.

Protocol: reads the PreToolUse JSON on stdin; a BLOCK prints
`{"decision": "block", "reason": ...}` and exits 2; an ALLOW exits 0
silently. Fails OPEN on malformed stdin or an unparsable command string
(matches the established convention of the sibling guards in this file) --
this hook is a safety net over a destructive command, not the sole control.
"""

from __future__ import annotations

import json
import os
import shlex
import sys
from datetime import datetime, timezone
from pathlib import Path


# Human-authorisation override env var. Required to carry actual prose (see
# _reason_is_valid) -- a bare truthy flag does not qualify.
_REASON_ENV = "NWAVE_WORKTREE_REMOVE_REASON"
_MIN_REASON_LENGTH = 15

# Optional target-branch override for the unmerged-commits check. Defaults to
# the CURRENT branch of the invoking repo (the orchestrator's own vantage
# point: "is this worktree's work reachable from where I stand").
_TARGET_BRANCH_ENV = "NWAVE_WORKTREE_GUARD_TARGET_BRANCH"

# Test-harness env var so the hook locates the audit-log dir without relying
# on Path.cwd(). Production leaves it unset. Mirrors
# git_stash_guard.NWAVE_GIT_STASH_GUARD_TARGET_ROOT.
_TARGET_ROOT_ENV = "NWAVE_WORKTREE_GUARD_TARGET_ROOT"

_AUDIT_LOG_DIR_RELPATH = Path(".nwave") / "des" / "logs"
_BYPASS_EVENT = "WorktreeRemovalBypassUsed"

_SEPARATORS = frozenset({"&&", "||", ";", "|", "&"})


def _read_hook_event() -> dict[str, object]:
    """Read the Claude Code PreToolUse hook event JSON from stdin.

    Returns `{}` on empty/malformed stdin -- treated as non-actionable
    (approve silently). Mirrors git_stash_guard._read_hook_event.
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
    tool_input = event.get("tool_input", {})
    if not isinstance(tool_input, dict):
        return ""
    command = tool_input.get("command", "")
    return command if isinstance(command, str) else ""


def _split_subcommands(command: str) -> list[list[str]] | None:
    """Tokenize `command` and split on shell separators.

    Returns None on unparsable input (unbalanced quotes) -- the caller
    fails open rather than false-block on a command it cannot understand.
    """
    try:
        tokens = shlex.split(command)
    except ValueError:
        return None
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
    return sub_commands


def _worktree_remove_target(sub_command: list[str]) -> str | None:
    """Return the target path argument of a `git worktree remove <path>` sub-command.

    Returns None when `sub_command` is not a `git worktree remove` invocation,
    or when it carries no positional path argument (git itself will error --
    nothing for this guard to check).
    """
    if len(sub_command) < 3:
        return None
    if (
        sub_command[0] != "git"
        or sub_command[1] != "worktree"
        or sub_command[2] != "remove"
    ):
        return None
    for token in sub_command[3:]:
        if not token.startswith("-"):
            return token
    return None


def _find_removal_target(command: str) -> str | None:
    """Scan every sub-command of `command` for a `git worktree remove <path>`.

    Returns the target path string of the FIRST match, or None if the
    command is unparsable or carries no such invocation (fast path: no
    liveness probes run at all).
    """
    sub_commands = _split_subcommands(command)
    if sub_commands is None:
        return None
    for sub in sub_commands:
        target = _worktree_remove_target(sub)
        if target is not None:
            return target
    return None


def _reason_is_valid(raw: str) -> bool:
    """True iff the override reason carries a non-trivial justification.

    A bare truthy flag (`1`, `true`, `yes`, ...) does not qualify -- the
    override must read like an actual sentence a human wrote, mirroring
    `des wave-clear --reason`'s required-prose discipline (not a convenience
    toggle).
    """
    return len(raw.strip()) >= _MIN_REASON_LENGTH


def _target_root() -> Path:
    override = os.environ.get(_TARGET_ROOT_ENV, "")
    return Path(override) if override else Path.cwd()


def _audit_log_path(target_root: Path) -> Path:
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    return target_root / _AUDIT_LOG_DIR_RELPATH / f"audit-{today}.log"


def _emit_bypass_event(
    target_root: Path, command: str, reason: str, session_id: str
) -> None:
    log_path = _audit_log_path(target_root)
    log_path.parent.mkdir(parents=True, exist_ok=True)
    event = {
        "event": _BYPASS_EVENT,
        "ts": datetime.now(timezone.utc).isoformat(),
        "command": command,
        "reason": reason,
        "session_id": session_id,
    }
    with log_path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(event, sort_keys=True) + "\n")


def _resolve_target_branch(repo: Path) -> str | None:
    """Resolve the branch the unmerged-commits check compares against.

    `NWAVE_WORKTREE_GUARD_TARGET_BRANCH` wins when set (explicit, no
    guessing -- mirrors `des verify-worktree-cleanup --target-branch`'s "no
    implicit default" stance for the OPERATOR-facing CLI). Otherwise falls
    back to `worktree_triage_collector.resolve_target_branch` (the CURRENT
    branch of `repo` -- the orchestrator's own vantage point), the SAME
    fallback the Sentinel sweep enumerator uses when it carries no override
    of its own. Returns None when neither resolves -- the caller reports
    that as an Indeterminate unmerged-commits signal, never a silent
    "assume merged".
    """
    override = os.environ.get(_TARGET_BRANCH_ENV, "").strip()
    if override:
        return override

    # Lazy import: preserves this hook's fail-closed-not-crashed contract
    # when `des` is unimportable (see `_run_triage`).
    from des.application.worktree_triage_collector import resolve_target_branch

    return resolve_target_branch(repo)


def _emit_block(reason: str) -> None:
    print(json.dumps({"decision": "block", "reason": reason}))


def _format_block_reason(receipt, target: str) -> str:
    lines = [
        f"⛔ WORKTREE REMOVAL REFUSED — triage state {receipt.state.value} for "
        f"{target!r} (CLEAN is required to remove).",
        "",
    ]
    for finding in receipt.evidence:
        lines.append(f"- WHAT: {finding.what}")
        lines.append(f"  WHY:  {finding.why}")
    if receipt.actions:
        lines.append("")
        lines.append(
            f"Recommended actions (human picks ONE): {', '.join(receipt.actions)}"
        )
    lines.append("")
    lines.append(f"HOW: {receipt.how}")
    lines.append(
        "NOTE: evidence categories not yet mechanically available: "
        f"{', '.join(receipt.unavailable_evidence)}."
    )
    return "\n".join(lines)


def _run_triage(repo: Path, target_path: Path):
    """Collect the four evidence signals and return the triage receipt.

    EXTRACTED (sentinel-sweep-enumerator, 2026-07-29) into
    `des.application.worktree_triage_collector.collect_worktree_triage_receipt`
    so the periodic Sentinel sweep can reuse the SAME signal-collection
    instead of re-deriving it -- this function is now a thin wrapper that
    resolves this hook's OWN target-branch policy (env-var override, see
    `_resolve_target_branch`) and delegates the rest. Imports the `des`
    application/domain modules LAZILY (not at module top-level) so a broken
    `des` install fails INSIDE this function, where the caller can convert
    it into a deterministic BLOCK-with-reason rather than an uncaught
    traceback with an ambiguous exit code. GDP-6: the guard itself failing
    to run is exactly the kind of "cannot see" that must refuse loud, never
    silently allow (and never crash into an undefined Claude Code hook
    outcome either).
    """
    from des.application.worktree_triage_collector import (
        collect_worktree_triage_receipt,
    )

    return collect_worktree_triage_receipt(
        repo=repo, target_path=target_path, target_branch=_resolve_target_branch(repo)
    )


def main() -> int:
    event = _read_hook_event()
    command = _bash_command(event)
    if not command:
        return 0

    target = _find_removal_target(command)
    if target is None:
        return 0  # fast path: not a `git worktree remove` invocation

    repo = Path(str(event.get("cwd") or Path.cwd()))
    target_path = Path(target)
    if not target_path.is_absolute():
        target_path = repo / target_path

    raw_reason = os.environ.get(_REASON_ENV, "")
    if raw_reason and _reason_is_valid(raw_reason):
        session_id = str(event.get("session_id", ""))
        _emit_bypass_event(_target_root(), command, raw_reason.strip(), session_id)
        return 0

    try:
        receipt = _run_triage(repo, target_path)
    except Exception as exc:
        _emit_block(
            f"⛔ WORKTREE REMOVAL REFUSED — the triage predicate itself could "
            f"not run ({type(exc).__name__}: {exc}) for {str(target_path)!r}.\n\n"
            "WHY: a guard that cannot see and lets you through is worse than "
            "no guard -- an internal failure here degrades LOUD (refuse), "
            "never silently allow.\n\n"
            f"HOW: fix the `des` install (this hook imports `des.adapters`/"
            "`des.domain` lazily and this is the failure boundary), or -- "
            "ONLY after a HUMAN has confirmed removal is safe -- set "
            f'{_REASON_ENV}="<why a human confirmed this is safe>" '
            "(audited) and re-run."
        )
        return 2

    from des.domain.worktree_anti_rot_triage import TriageState

    if receipt.state is TriageState.CLEAN:
        return 0  # convergent evidence: no liveness, nothing at risk

    _emit_block(_format_block_reason(receipt, str(target_path)))
    return 2


if __name__ == "__main__":
    sys.exit(main())
