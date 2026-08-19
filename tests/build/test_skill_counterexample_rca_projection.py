"""Projection tests for the counterexample-RCA skill change (2026-08-19).

SF sister's published-language proposal: Change 1 (`nw-design`) and Change 2
(`nw-root-why`) wire a root-cause-first reflex for a refuted invariant/
counterexample into the design-pass entry points; Change 3 (`nw-review`
blocking rule) is deliberately deferred, falsifier-gated on first
recidivism -- not applied.
"""

from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
DESIGN_SKILL = ROOT / "nWave/skills/nw-design/SKILL.md"
ROOT_WHY_SKILL = ROOT / "nWave/skills/nw-root-why/SKILL.md"
REVIEW_SKILL = ROOT / "nWave/skills/nw-review/SKILL.md"


def _text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def test_design_skill_carries_counterexample_discipline_after_required_pass() -> None:
    text = _text(DESIGN_SKILL)
    compact = " ".join(text.split())

    assert "## Counterexample discipline" in text
    assert (
        "first a ROOT-CAUSE question about the\nrepresentation, never a "
        "patch site".replace("\n", " ")
        in compact
    )
    assert "Route the" in compact
    assert "`nw-algebraic-design-protocol`" in compact
    assert "`nw-certainty-by-construction`" in compact
    assert "A theorem that only holds conditionally is the same signal" in compact
    # Placed immediately after "Required Design Pass", before "Handoff" --
    # not appended at end of file, not renumbering the existing 1-9 items.
    required_index = text.index("## Required Design Pass")
    counterexample_index = text.index("## Counterexample discipline")
    handoff_index = text.index("## Handoff")
    assert required_index < counterexample_index < handoff_index
    assert "9. **Human projection**" in text  # unrenumbered


def test_design_skill_carries_independent_statement_review_with_portability() -> None:
    """Ale's requirement: target machines may lack Agda/TLA+ -- the
    discipline must not presuppose a proof assistant or model checker."""
    compact = " ".join(_text(DESIGN_SKILL).split())

    assert "## Independent statement review" in _text(DESIGN_SKILL)
    assert "verify the PROOFS, not the STATEMENTS" in compact
    assert (
        "agree on the same\nmisreading — that is a coherence check, never "
        "corroboration".replace("\n", " ")
        in compact
    )
    assert (
        "This discipline requires no proof assistant or model checker: "
        "property tests in the project's own language, exhaustive finite "
        "checks, or a model checker when one is available all qualify — a "
        "prover is never a prerequisite." in compact
    )


def test_design_skill_never_applies_the_deferred_review_blocking_rule() -> None:
    """Change 3 is deliberately NOT applied -- falsifier-gated, deferred to
    first recidivism."""
    review_text = _text(REVIEW_SKILL)

    assert "adds a law/guard over an" not in review_text
    assert "Counterexample discipline" not in review_text


def test_root_why_skill_carries_design_time_counterexamples_after_overview() -> None:
    text = _text(ROOT_WHY_SKILL)
    compact = " ".join(text.split())

    assert "## Design-time counterexamples" in text
    assert "RCA applies to design-time evidence at par with runtime failures" in compact
    assert "Route the cure through `nw-design`'s" in compact
    assert (
        "a law added over an unchanged representation\nwithout recorded "
        "justification is a symptom patch, not a root-cause fix".replace("\n", " ")
        in compact
    )
    # Portability clause (short form for Change 2, per Ale's requirement).
    assert "no prover is a prerequisite for this RCA question" in compact
    overview_index = text.index("## Overview")
    design_time_index = text.index("## Design-time counterexamples")
    invocation_index = text.index("## Agent Invocation")
    assert overview_index < design_time_index < invocation_index
