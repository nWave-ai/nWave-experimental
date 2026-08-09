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
`scripts/hooks/git_stash_guard.py` (tokenized command parsing -- a raw regex
would false-negative on a `git worktree remove` buried after a `&&`, and
false-positive on the phrase appearing inside a quoted commit message). On a
match it collects the four evidence signals the triage predicate consumes --
through `ProcessCwdProbePort`
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
import sys
from pathlib import Path


# Decision algorithm lives in `des.adapters.drivers.hooks.bash_command_guards`
# (fix-execution-log-bash-guard-consolidation follow-on, Ale-authorised) --
# this script is now a thin stdin/stdout/exit-code CLI wrapper around it, so
# the universal `src/des` PreToolUse/Bash handler and this standalone
# registration cannot diverge into two decision algorithms. Imported lazily
# inside `main()` so a broken `des` install fails INSIDE the call, where it
# is converted to a deterministic BLOCK-with-reason (see `main`).
def _guards():
    from des.adapters.drivers.hooks import bash_command_guards

    return bash_command_guards


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


def _session_id(event: dict[str, object]) -> str:
    session_id = event.get("session_id", "")
    return session_id if isinstance(session_id, str) else ""


def main() -> int:
    """Read the hook event, delegate the decision, return the exit code.

    All decision logic (fast-path, target extraction, override, triage)
    lives in `bash_command_guards.evaluate_worktree_remove_command`; this
    wrapper only translates the stdin event into that call and the returned
    decision into the stdout/exit-code protocol.
    """
    guards = _guards()
    event = _read_hook_event()
    command = _bash_command(event)
    if not command:
        return 0

    repo = Path(str(event.get("cwd") or Path.cwd()))
    decision = guards.evaluate_worktree_remove_command(command, repo)
    if decision is None:
        return 0
    if decision.audit_event is not None:
        guards.write_bash_guard_audit_event(
            guards.worktree_guard_target_root(),
            decision.audit_event,
            {**(decision.audit_data or {}), "session_id": _session_id(event)},
        )
    if decision.allow:
        return 0
    print(json.dumps({"decision": "block", "reason": decision.reason}))
    return 2


if __name__ == "__main__":
    sys.exit(main())
