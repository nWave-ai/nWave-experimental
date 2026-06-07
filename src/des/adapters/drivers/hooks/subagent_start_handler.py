"""SubagentStart hook handler — skill loading reminder injection.

Reads hook input JSON from stdin. For nWave sub-agents (agent_type starting
with "nw-"), writes an additionalContext JSON reminder to stdout instructing
the agent to load its relevant skill files.

Fail-open: any exception exits 0 so the spawned sub-agent session is never
blocked by a reminder hook.

Output format (for nw-* agents only):
    {"additionalContext": "MANDATORY: You are @{agent_type}. Load your relevant
    skill files from ~/.claude/skills/nw-<skill-name>/SKILL.md for each skill
    you need. Skills use a flat topical layout — for example:
    ~/.claude/skills/nw-tdd-methodology/SKILL.md
    ~/.claude/skills/nw-bdd-methodology/SKILL.md
    ~/.claude/skills/nw-progressive-refactoring/SKILL.md
    Load the ones applicable to your current task at the appropriate phase."}
"""

from __future__ import annotations

import json
import sys


def _build_reminder_message(agent_type: str) -> str:
    """Build the additionalContext reminder for a nWave sub-agent.

    Skills use a flat topical layout: ~/.claude/skills/nw-<skill-name>/SKILL.md
    """
    return (
        f"MANDATORY: You are @{agent_type}. Load your relevant skill files from "
        "~/.claude/skills/nw-<skill-name>/SKILL.md for each skill you need. "
        "Skills use a flat topical layout — for example: "
        "~/.claude/skills/nw-tdd-methodology/SKILL.md, "
        "~/.claude/skills/nw-bdd-methodology/SKILL.md, "
        "~/.claude/skills/nw-progressive-refactoring/SKILL.md. "
        "Load the ones applicable to your current task at the appropriate phase."
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
