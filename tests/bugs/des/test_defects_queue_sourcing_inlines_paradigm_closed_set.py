# @feature-des-refactor-fixer-swarm
"""Regression AT -- the `defects.md` bugfix-queue sourcing instruction must
TEACH the `paradigm=` closed set at the point a row gets WRITTEN, not only at
the point `des refactor` refuses one (GDP-2: proactive affordance at the
authoring surface beats a reactive one at the gate).

RCA (refactor-ux drain, 2026-07-29, incident 2 of the two-incident report):
a real operator reported most of ~20 pending rows in `defects.md` got
refused by `des refactor` for an unrecognized `paradigm=` value, and worked
through them by hand with a background agent instead. Empirical confirmation
in THIS repo's own `defects.md` (`defects.md:154`, `done.md:69,237,297`):
four real rows carry `paradigm=bug` or `paradigm=SSOT/DRY violation` -- the
DEFECT CLASS written into the paradigm field, exactly the anti-pattern this
tree's own `des-command-catalog.md:39` names ("NEVER put the defect CLASS
there"). `select_paradigm_lens` (`src/des/domain/refactor/paradigm_select.py`)
refuses both: neither is a member of `RecognizedParadigm`.

The two sourcing instructions in `00-standing-loops.md` are ASYMMETRIC. The
`techdebt.md` one (`/loop 30m` — source tech-debt findings, ~line 397)
inlines the closed set explicitly: `paradigm=<object-oriented|functional>`.
The `defects.md` one (`/loop 30m` — source the bugfix queue) only says "same
pile-row grammar as `techdebt.md`" -- the closed set is never restated at
THIS authoring point, ~65 lines above in the same file. This is the gap that
produced incident 2's real rows: whoever wrote them saw the grammar shape
but not the paradigm constraint.

Property test only: assert the closed-set tokens are present INSIDE the
`defects.md` sourcing paragraph specifically (not merely somewhere in the
file, which the pre-existing `techdebt.md` paragraph would already satisfy
and which would make this test pass without fixing anything).
"""

from __future__ import annotations

from pathlib import Path


# tests/bugs/des/<this file> -> parents[3] == checkout root (mirrors the
# convention already used by sibling files in this directory, e.g.
# test_coherence_catalog_path_override.py / test_dispatch_lane_for_non_code_
# facing_agents.py).
_REPO_ROOT = Path(__file__).resolve().parents[3]
_STANDING_LOOPS_PATH = (
    _REPO_ROOT / "nWave" / "data" / "orchestrator-affordance" / "00-standing-loops.md"
)

_SOURCING_MARKER = "source the bugfix queue"
_DRAINING_MARKER = "drain the bugfix queue"


def _bugfix_queue_sourcing_paragraph(full_text: str) -> str:
    """The prose span for the `defects.md`-sourcing instruction ONLY -- from
    its own `/loop 30m` marker up to the NEXT loop's marker, so an assertion
    against it cannot be satisfied by the unrelated `techdebt.md` paragraph
    (or the `defects.md`-DRAINING paragraph below it) that happens to share
    the same file.
    """
    start = full_text.index(_SOURCING_MARKER)
    end = full_text.index(_DRAINING_MARKER, start)
    return full_text[start:end]


def test_standing_loops_file_exists_with_the_expected_sourcing_paragraph():
    """Sanity precondition -- if this ever goes missing/renamed the test
    below must fail LOUD with a clear cause, not a silent pass against an
    empty string.
    """
    assert _STANDING_LOOPS_PATH.is_file(), (
        f"expected the standing-loops orchestrator-affordance file at "
        f"{_STANDING_LOOPS_PATH}, but it does not exist"
    )
    full_text = _STANDING_LOOPS_PATH.read_text(encoding="utf-8")
    assert _SOURCING_MARKER in full_text
    assert _DRAINING_MARKER in full_text


def test_bugfix_queue_sourcing_instruction_inlines_the_paradigm_closed_set():
    """Given the `defects.md`-sourcing instruction (the authoring surface a
    human/orchestrator actually writes pile rows from), Then it states the
    `paradigm=` closed set INLINE, at the point of writing -- both
    recognized tokens present in THIS paragraph, not only cross-referenced
    up in the sibling `techdebt.md` paragraph.
    """
    full_text = _STANDING_LOOPS_PATH.read_text(encoding="utf-8")
    paragraph = _bugfix_queue_sourcing_paragraph(full_text)

    assert "object-oriented" in paragraph, (
        "the defects.md sourcing paragraph never inlines the "
        f"'object-oriented' paradigm token: {paragraph!r}"
    )
    assert "functional" in paragraph, (
        "the defects.md sourcing paragraph never inlines the "
        f"'functional' paradigm token: {paragraph!r}"
    )


def test_bugfix_queue_sourcing_instruction_warns_against_the_defect_class_anti_pattern():
    """The empirically observed failure mode is not a missing field -- it is
    the DEFECT CLASS (`bug`, `SSOT/DRY violation`) written into the
    `paradigm=` field instead of a recognized paradigm token. The
    instruction must warn against exactly that substitution at the point of
    writing, mirroring `des-command-catalog.md`'s own "NEVER put the defect
    CLASS there" guidance -- never only downstream in a refusal message.
    """
    full_text = _STANDING_LOOPS_PATH.read_text(encoding="utf-8")
    paragraph = _bugfix_queue_sourcing_paragraph(full_text)

    assert "class" in paragraph.lower(), (
        "the defects.md sourcing paragraph never warns against writing the "
        f"defect CLASS into paradigm=: {paragraph!r}"
    )
