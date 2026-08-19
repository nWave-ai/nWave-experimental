"""Projection tests for the whole-suite verification-scope lever (K4 Run 12).

Run 12 debrief's single biggest wall-clock lever: `verification-scope.
commands` only ever named the new oracle's own narrow test, never the
subject's own declared whole-suite command; regressions outside the narrow
scope surfaced only through 3 reviewer rounds. This wires the requirement
into `nw-acceptance-designer` (authoring) and `nw-distill` (the compiling
skill's own routing text) -- the CLI-level refusal/detection is covered
separately by `tests/des/unit/domain/test_workspace_test_command_resolver.py`
and `tests/des/acceptance/test_dispatch_whole_suite_scope.py`.
"""

from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
ACCEPTANCE_DESIGNER = ROOT / "nWave/agents/nw-acceptance-designer.md"
DISTILL_SKILL = ROOT / "nWave/skills/nw-distill/SKILL.md"


def _text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def test_acceptance_designer_asks_for_the_whole_suite_command_alongside_the_oracle() -> (
    None
):
    compact = " ".join(_text(ACCEPTANCE_DESIGNER).split())

    assert (
        "does it also carry the subject workspace's own declared\n"
        "   whole-suite command".replace("\n   ", " ")
        in compact
    )
    assert "Run the subject's own tests" in compact
    assert "K4 Run 12" in compact
    assert "`Check.to_dict()`" in compact
    assert (
        "`des dispatch` now refuses a\n   whole-suite-declaring workspace".replace(
            "\n   ", " "
        )
        in compact
    )


def test_distill_skill_treats_verification_scope_commands_as_a_set() -> None:
    text = _text(DISTILL_SKILL)
    compact = " ".join(text.split())

    assert "`verification-scope.commands` is a set, not a slot" in compact
    assert "the workspace's own whole-suite command" in compact
    assert "copied verbatim, never" in compact
    assert "K4 Run 12" in compact
    # Placed right after the architecture-brief-supplies paragraph, before Output.
    brief_index = text.index("The architecture brief supplies")
    set_index = text.index("`verification-scope.commands` is a set")
    output_index = text.index("## Output")
    assert brief_index < set_index < output_index
