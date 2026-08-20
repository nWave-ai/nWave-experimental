"""Regression test: the adversarial design-review question set (S1-S4, T5-T7)
projects into nw-review, is pointed to from nw-design and the two reviewer
agents, and its mechanical stressor-derivation corollary projects into
nw-stress-analysis.

Ale + SF sister, 2026-08-19: an adversarially-refined question set with a
three-value marking rule (MECHANICAL/INSPECTIVE/JUDGEMENT) and a mechanical
stressor-derivation rule (negate declared assumptions) must be discoverable
from every artifact a design review touches, not duplicated prose per file.
"""

from pathlib import Path

import pytest


PROJECT_ROOT = Path(__file__).resolve().parents[3]
NWAVE_DIR = PROJECT_ROOT / "nWave"
SKILLS_DIR = NWAVE_DIR / "skills"
AGENTS_DIR = NWAVE_DIR / "agents"

REVIEW_SKILL = SKILLS_DIR / "nw-review" / "SKILL.md"
STRESS_SKILL = SKILLS_DIR / "nw-stress-analysis" / "SKILL.md"
DESIGN_SKILL = SKILLS_DIR / "nw-design" / "SKILL.md"
SA_REVIEWER = AGENTS_DIR / "nw-solution-architect-reviewer.md"
AD_REVIEWER = AGENTS_DIR / "nw-acceptance-designer-reviewer.md"

QUESTION_IDS = ("S1", "S2", "S3", "S4", "T5", "T6", "T7")
MARKING_VALUES = ("MECHANICAL", "INSPECTIVE", "JUDGEMENT")

STRUCTURAL_NOT_TEMPORAL_FILES = (
    REVIEW_SKILL,
    STRESS_SKILL,
    DESIGN_SKILL,
    SA_REVIEWER,
    AD_REVIEWER,
)


def _text(path: Path) -> str:
    assert path.exists(), f"missing file: {path}"
    return path.read_text(encoding="utf-8")


def test_nw_review_projects_all_seven_question_ids():
    content = _text(REVIEW_SKILL)
    for question_id in QUESTION_IDS:
        assert question_id in content, (
            f"nw-review/SKILL.md: missing design-review question {question_id}"
        )


def test_nw_review_projects_three_value_marking_rule():
    content = _text(REVIEW_SKILL)
    for value in MARKING_VALUES:
        assert value in content, f"nw-review/SKILL.md: missing marking value {value}"
    assert "INCOMPLETE BY CONSTRUCTION" in content, (
        "nw-review/SKILL.md: missing the incompleteness-by-construction clause "
        "for an unexecuted MECHANICAL question"
    )


def test_nw_review_marks_judgement_as_returned_never_verdict():
    content = _text(REVIEW_SKILL)
    assert "JUDGEMENT" in content
    assert "never a verdict" in content, (
        "nw-review/SKILL.md: JUDGEMENT answers must be stated as returned to "
        "the human, never a verdict"
    )


def test_nw_stress_analysis_projects_stressor_derivation_rule():
    content = _text(STRESS_SKILL)
    assert "stressor is the negation of a declared assumption" in content, (
        "nw-stress-analysis/SKILL.md: missing the mechanical stressor-derivation rule"
    )
    assert "economically" in content, (
        "nw-stress-analysis/SKILL.md: missing the irreducibly-human economic "
        "step of the stressor-derivation rule"
    )


def test_nw_design_points_to_review_question_set():
    content = _text(DESIGN_SKILL)
    assert "nw-review" in content.split("## Independent statement review", 1)[-1], (
        "nw-design/SKILL.md: Independent statement review section does not "
        "point to the nw-review design-review question set"
    )


@pytest.mark.parametrize(
    "reviewer_path",
    [SA_REVIEWER, AD_REVIEWER],
    ids=["solution-architect", "acceptance-designer"],
)
def test_reviewer_agents_carry_marking_discipline(reviewer_path: Path):
    content = _text(reviewer_path)
    assert "MECHANICAL" in content, f"{reviewer_path.name}: missing MECHANICAL marking"
    assert "INCOMPLETE BY CONSTRUCTION" in content, (
        f"{reviewer_path.name}: missing incompleteness-by-construction clause"
    )


@pytest.mark.parametrize(
    "path",
    STRUCTURAL_NOT_TEMPORAL_FILES,
    ids=[p.name for p in STRUCTURAL_NOT_TEMPORAL_FILES],
)
def test_question_set_states_structural_not_temporal_limit(path: Path):
    content = _text(path)
    assert "structural incoherence" in content, (
        f"{path.name}: missing the structural-incoherence-not-temporal-holes limit"
    )
    assert "temporal hole" in content or "temporal gap" in content, (
        f"{path.name}: missing the temporal-gap-needs-model-checker limit"
    )
