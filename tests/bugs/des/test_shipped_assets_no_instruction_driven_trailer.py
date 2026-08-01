"""Regression: shipped agent/skill assets must not instruct the model to
type the nWave attribution trailer literally.

OBSERVED (ADR-CA-008, docs/product/architecture/ADR-CA-008-heredoc-coverage-via-
lifecycle-rewrite.md, lines 68-81): the deterministic attribution mechanism (the
PreToolUse hook injecting `Co-Authored-By: nWave <nwave@nwave.ai>`) silently
degraded to model-composed attribution on `$()`/heredoc commit shapes. This
went undetected for two months precisely because two shipped framework assets
-- `nWave/skills/nw-collaboration-and-handoffs/SKILL.md` (4 "Commit Message
Formats" example blocks: TDD Implementation, Mikado Discovery, Mikado
Implementation, Refactoring Transformation) and `nWave/agents/nw-software-
crafter.md` (1 "Commit message format (both modes)" example block) -- showed
the model an example commit message ending in the literal trailer line,
training every agent that read them to type it by hand. Every nWave-dev
commit "looked attributed" because agents were typing the trailer, not
because the deterministic mechanism fired (ADR-CA-008 line 81: "every
nWave-dev commit 'looked attributed'").

Slices 01-03 of this bugfix fixed the real deterministic mechanism (`des
commit` / `des commit-slice` now attribute themselves correctly, including on
the heredoc/relative-path shape, and the doctor attribution check now reports
DISAGREED instead of an unconditional pass). This slice retires the
model-instruction fallback: while the literal trailer stays in these two
shipped examples, it keeps masking any FUTURE regression of the real
mechanism -- defeating the entire point of the bugfix. Neither file may
contain the literal string `Co-Authored-By: nWave` anywhere once fixed.
"""

from __future__ import annotations

from pathlib import Path


_REPO_ROOT = Path(__file__).resolve().parents[3]
_COLLAB_SKILL = (
    _REPO_ROOT / "nWave" / "skills" / "nw-collaboration-and-handoffs" / "SKILL.md"
)
_CRAFTER_AGENT = _REPO_ROOT / "nWave" / "agents" / "nw-software-crafter.md"

_INSTRUCTION_DRIVEN_TRAILER = "Co-Authored-By: nWave"


def test_collaboration_and_handoffs_skill_does_not_instruct_literal_trailer() -> None:
    text = _COLLAB_SKILL.read_text(encoding="utf-8")
    assert _INSTRUCTION_DRIVEN_TRAILER not in text, (
        "nw-collaboration-and-handoffs/SKILL.md still instructs the model to "
        f"type {_INSTRUCTION_DRIVEN_TRAILER!r} literally in a commit-message "
        "example -- this model-droppable fallback masked the real "
        "attribution defect for two months (ADR-CA-008 lines 68-81). Remove "
        "the trailer line from every 'Commit Message Formats' example block "
        "(TDD Implementation, Mikado Discovery, Mikado Implementation, "
        "Refactoring Transformation); leave the Step-Id line and everything "
        "else untouched."
    )


def test_software_crafter_agent_does_not_instruct_literal_trailer() -> None:
    text = _CRAFTER_AGENT.read_text(encoding="utf-8")
    assert _INSTRUCTION_DRIVEN_TRAILER not in text, (
        "nw-software-crafter.md still instructs the model to type "
        f"{_INSTRUCTION_DRIVEN_TRAILER!r} literally in its 'Commit message "
        "format (both modes)' example -- this model-droppable fallback "
        "masked the real attribution defect for two months (ADR-CA-008 "
        "lines 68-81). Remove the trailer line; leave the Step-Id line and "
        "everything else untouched."
    )


def test_adr_ca_008_still_names_the_masking_effect_fixture_sanity() -> None:
    adr = (
        _REPO_ROOT
        / "docs"
        / "product"
        / "architecture"
        / "ADR-CA-008-heredoc-coverage-via-lifecycle-rewrite.md"
    ).read_text(encoding="utf-8")
    assert "MASKED" in adr
    assert "looked attributed" in adr
