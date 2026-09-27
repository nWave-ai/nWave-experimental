"""The reviewer prompt must be RENDERED from the rubric, not retyped.

Each check fails against a prompt that was hand-copied and then drifted: a
criterion the rubric added and the prompt never gained, a verdict contract the
prompt states differently from the boundary that enforces it, or internal
vocabulary leaking into a surface that must stay source-blind.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path


_K4 = Path(__file__).resolve().parents[3] / "scripts" / "analysis" / "k4"
sys.path.insert(0, str(_K4.parent))
sys.path.insert(0, str(_K4))

import blind_review
import quality_rubric
import render_review_prompt


def test_the_prompt_is_derived_from_the_rubric_not_retyped(monkeypatch) -> None:
    """Fails against a prompt that is a fixed string, however complete it is.

    Asserting that today's prompt names today's criteria cannot fail: the same
    list feeds both sides. The property that CAN fail is derivation -- change
    the rubric, and the rendered prompt must change with it.
    """
    sentinel = quality_rubric.Criterion(
        key="sentinel",
        dimension="a_dimension_no_prompt_would_contain",
        question="Does the rendered prompt follow the rubric it is rendered from?",
        section_1a=(),
        notes="",
    )
    monkeypatch.setattr(
        quality_rubric, "CRITERIA", (*quality_rubric.CRITERIA, sentinel)
    )
    prompt = render_review_prompt.render(Path("/somewhere"))
    assert sentinel.dimension in prompt
    assert sentinel.question in prompt


def test_every_rubric_criterion_reaches_the_prompt() -> None:
    prompt = render_review_prompt.render(Path("/somewhere"))
    for index, criterion in enumerate(quality_rubric.CRITERIA, start=1):
        assert f"{index}. **{criterion.dimension}**" in prompt
        assert criterion.question in prompt


def test_the_prompt_states_the_contract_the_boundary_enforces() -> None:
    prompt = render_review_prompt.render(Path("/somewhere"))
    assert str(sorted(blind_review._VERDICT_TOP_KEYS)) in prompt
    assert f"'1'..'{len(quality_rubric.CRITERIA_KEYS)}'" in prompt


def test_the_prompt_leaks_no_internal_vocabulary() -> None:
    prompt = render_review_prompt.render(Path("/somewhere")).lower()
    for forbidden in ("nwave", "adr", "section 1a", "delegated_1a", "control arm"):
        assert forbidden not in prompt


def test_a_verdict_shaped_as_the_prompt_asks_is_accepted() -> None:
    keys = sorted(quality_rubric.CRITERIA_KEYS, key=int)
    verdict = {
        "criteria": {k: {"score": 1, "evidence": "read it"} for k in keys},
        "total": len(keys),
        "blocking_quality_findings": [],
        "summary": "well formed",
    }
    assert blind_review._validate_one_verdict("id", verdict) == []
    assert json.dumps(verdict)
