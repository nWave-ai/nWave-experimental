"""SubagentStart hook handler — skill loading reminder injection.

Reads hook input JSON from stdin. For nWave sub-agents (agent_type starting
with "nw-"), writes an additionalContext JSON reminder to stdout instructing
the agent to load its relevant skills.

Fail-open: any exception exits 0 so the spawned sub-agent session is never
blocked by a reminder hook.

Skills are named, never path-hardcoded (D3-analog:
`root_activation_context.py`'s D3 fix already established this pattern for
the root reminder — a literal home-relative config-directory path is invalid
under any non-default `CLAUDE_CONFIG_DIR`, which is exactly what an isolated
install produces). The Skill tool resolves a name against whatever config dir
is active, so the reminder names skills and lets the harness do the resolution.

Output format (for nw-* agents only):
    {"additionalContext": "MANDATORY: You are @{agent_type}. Load any
    relevant skill not already loaded this session via the Skill tool --
    invoke each nw-<skill-name> skill by name (for example:
    nw-tdd-methodology, nw-bdd-methodology, nw-progressive-refactoring) for
    the ones applicable to your current role, task, and phase that are not
    already loaded. Skills already loaded this session do not need to be
    reloaded -- this reminder is idempotent, not a blanket reload mandate."}
"""

from __future__ import annotations

import json
import sys


def _build_reminder_message(agent_type: str) -> str:
    """Build the additionalContext reminder for a nWave sub-agent.

    Names skills by NAME and resolves them via the Skill tool -- never a
    literal home-relative config-directory path (D3-analog). Idempotent by
    wording, not by state: it tells the agent that already-loaded skills
    need not be reloaded, without tracking or persisting what was loaded.
    """
    return (
        f"MANDATORY: You are @{agent_type}. Load any relevant skill not "
        "already loaded this session via the Skill tool -- invoke each "
        "nw-<skill-name> skill by name (for example: nw-tdd-methodology, "
        "nw-bdd-methodology, nw-progressive-refactoring) for the ones "
        "applicable to your current role, task, and phase that are not "
        "already loaded. Skills already loaded this session do not need to "
        "be reloaded -- this reminder is idempotent, not a blanket reload "
        "mandate."
    )


def handle_subagent_start() -> int:
    """Handle subagent-start hook: inject skill loading reminder for nWave agents.

    Reads JSON from stdin (Claude Code SubagentStart hook protocol). If the
    spawning agent_type starts with "nw-", writes an additionalContext JSON
    reminder to stdout instructing the agent to load its skill files.

    Returns:
        0 always (fail-open: sub-agent session must never be blocked).
    """
    try:
        raw = sys.stdin.read()
        hook_input = json.loads(raw)
        agent_type = hook_input["agent_type"]

        if agent_type.startswith("nw-"):
            message = _build_reminder_message(agent_type)
            print(json.dumps({"additionalContext": message}))

        return 0

    except Exception:
        return 0
