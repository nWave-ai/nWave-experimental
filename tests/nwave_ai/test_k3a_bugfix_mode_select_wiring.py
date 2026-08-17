"""activation-routing-before-mutation: the managed project CLAUDE section is
the single upstream owner of mode/size classification, and nw-bugfix stops
hardcoding `~/.claude`-relative skill paths.

Prior evidence, corroborated by the Haiku review of the same commit, showed a neutral M-shaped
bugfix task reaching `Skill(nw-bugfix)` via the generated project CLAUDE.md
before any hook fired, but never producing an explicit S/M/L classification.
That gap is now closed upstream: the managed CLAUDE section itself
establishes posture and S/M/L, and invokes `nw-mode-select` where required,
before any tool call. By the time `Skill(nw-bugfix)` fires, routing is
already settled -- nw-bugfix consumes an already-terminal DISTILL
DeliveryContract locator and must not restate route selection. Requiring
`nw-mode-select` again inside nw-bugfix would duplicate routing ceremony and
risk a second, competing workflow.

nw-bugfix also carried three `~/.claude/skills/nw-<skill>/SKILL.md` literal
path mentions describing how the troubleshooter, the charter author, and the
lane-map SSOT load their own skills -- the same D3-class defect
`root_activation_context.py` already fixed for the root reminder, reachable
here because this text is part of the skill body loaded into the
orchestrator's own context the moment `Skill(nw-bugfix)` fires.

These tests pin the current contract: nw-mode-select is never named inside
nw-bugfix (routing stays upstream, not duplicated), and every skill-loading
mention resolves by name via the Skill tool rather than a literal
home-relative path.
"""

from __future__ import annotations

from pathlib import Path


REPO = Path(__file__).resolve().parents[2]
BUGFIX_SKILL_PATH = REPO / "nWave/skills/nw-bugfix/SKILL.md"


def _text() -> str:
    return BUGFIX_SKILL_PATH.read_text(encoding="utf-8")


def test_bugfix_skill_file_exists() -> None:
    assert BUGFIX_SKILL_PATH.is_file()


def test_bugfix_does_not_duplicate_mode_select() -> None:
    """Routing is owned upstream by the managed project CLAUDE section, which
    establishes posture and S/M/L before any tool call. nw-bugfix consumes an
    already-terminal DISTILL DeliveryContract locator and must not restate
    route selection by naming nw-mode-select itself -- doing so would
    duplicate routing ceremony and risk a second, competing workflow."""
    text = _text()
    assert "nw-mode-select" not in text, (
        "nw-bugfix names nw-mode-select -- routing is owned upstream by the "
        "managed project CLAUDE section, and nw-bugfix must not duplicate it."
    )


def test_bugfix_skill_does_not_hardcode_home_relative_skill_paths() -> None:
    """D3-analog: no `~/.claude`-relative literal path anywhere in the body
    -- invalid under an isolated CLAUDE_CONFIG_DIR, the same defect class
    already fixed in root_activation_context.py and subagent_start_handler.py.
    """
    text = _text()
    assert "~/.claude" not in text, (
        "nw-bugfix must not hardcode a ~/.claude-relative skill path; "
        "resolve every skill by name via the Skill tool instead."
    )
