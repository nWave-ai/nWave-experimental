"""Projection tests for construction-owned whole-suite scope (K4 Run 12).

The compiler includes the declared whole-suite command in the mandatory
skeleton. ATD cannot author a narrower contract and no later omission gate is
needed.
"""

from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
ACCEPTANCE_DESIGNER = ROOT / "nWave/agents/nw-acceptance-designer.md"
DISTILL_SKILL = ROOT / "nWave/skills/nw-distill/SKILL.md"


def _text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def test_acceptance_designer_cannot_author_a_narrow_manual_contract() -> None:
    compact = " ".join(_text(ACCEPTANCE_DESIGNER).split())

    assert "It MUST resolve to the root-compiled skeleton" in compact
    assert "There is no manual contract-authoring fallback" in compact
    assert "write no oracle, support or contract bytes" in compact
    assert "verification-scope.commands" in compact


def test_distill_skill_treats_verification_scope_commands_as_a_set() -> None:
    text = _text(DISTILL_SKILL)
    compact = " ".join(text.split())

    assert "`verification-scope.commands` is a set, not a slot" in compact
    assert "the workspace's own whole-suite command" in compact
    assert "copied verbatim, never" in compact
    assert "K4 Run 12" in compact
    assert "required mechanical skeleton producer" in compact
    assert "included by construction" in compact
    assert "later omission gate" in compact
    # Placed right after the architecture-brief-supplies paragraph, before Output.
    brief_index = text.index("The architecture brief supplies")
    set_index = text.index("`verification-scope.commands` is a set")
    output_index = text.index("## Output")
    assert brief_index < set_index < output_index
