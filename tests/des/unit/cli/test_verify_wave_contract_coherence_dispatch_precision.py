"""Precision-fix regression: `_inline_restatement` must not flag a common-word
catalog gate_id (e.g. `dispatch`) used in running prose / command-invocation
form alongside another gate_id, while it MUST still flag a genuine structured
gate-stack enumeration that happens to name that same common-word gate_id.

F-COHERENCE-GATE-PRECISION. Defect: WS-3 Fase-2 added the catalog gate_id
`dispatch` (`nWave/gates/_catalog.yaml:371`, the `des dispatch` prompt
generator). `dispatch` collides with the common English word "dispatch",
which DELIVER/DISTILL prose uses constantly as ordinary vocabulary ("the mode
dispatch", "the dispatch markers", "crafter dispatch"). Shape 2 of
`_inline_restatement` ("a single line naming >=2 DISTINCT bare catalog
gate_ids") false-positives on any such line that ALSO mentions a second
catalog gate_id (`verify-wave-dispatch`, `feature-end`, `roadmap`, ...) --
confirmed live at HEAD: both
`tests/des/acceptance/algebra_projections_enforced/steps/
test_slice_04_coherence_hook_distill_deliver.py` Thens
"Deliver prose, as the repository carries it, clears the coherence check" and
"The hook fails the commit while a migrated wave still drifts" are RED today,
diagnostic naming `dispatch`, against the REAL `nWave/skills/nw-deliver/
SKILL.md` prose (e.g. line 41: "the mode dispatch, the per-slice spine +
feature-end cycle, the dispatch markers ...").

This module pins the NEGATIVE fix (the command/common-word collision must
clear) and the GUARD (a genuine gate-stack enumeration using the SAME
common-word gate_id must stay flagged, in all 3 shapes `_inline_restatement`
recognises, plus the full `evaluate_coherence` pipeline) -- the fix narrows
precision, it does NOT blanket-exempt the token "dispatch".
"""

from __future__ import annotations

from pathlib import Path

from des.cli.verify_wave_contract_coherence import (
    GateVerdict,
    _inline_restatement,
    evaluate_coherence,
)


# A local, hermetic catalog -- independent of the real (and mutable)
# nWave/gates/_catalog.yaml -- so these unit tests pin `_inline_restatement`'s
# pure-function behaviour regardless of unrelated catalog edits.
_CATALOG = frozenset({"dispatch", "verify-wave-dispatch", "feature-end", "roadmap"})


# -- NEGATIVE: the fix ---------------------------------------------------------


def test_command_form_and_running_prose_mention_are_not_flagged() -> None:
    """`des dispatch` (command invocation, already exempt) + "the dispatch
    prompt" (bare common-word mention) + a real gate_id mention on the SAME
    line is a command/common-word collision, NOT a gate-stack enumeration.

    FAILS TODAY: Shape 2 counts >=2 distinct bare catalog gate_ids on the line
    ("dispatch" via "the dispatch prompt", "verify-wave-dispatch" via its own
    mention) and flags it -- `_inline_restatement` currently returns
    `"dispatch"` instead of `None`.
    """
    line = (
        "Run `des dispatch` to generate the dispatch prompt that passes "
        "`verify-wave-dispatch`."
    )

    assert _inline_restatement(line, _CATALOG) is None


def test_real_world_running_prose_style_collision_is_not_flagged() -> None:
    """The actual `nw-deliver/SKILL.md` prose style (line 41 verbatim wording):
    two common-word gate_ids (`dispatch`, `feature-end`) named as ordinary
    vocabulary in one descriptive sentence, zero enumeration syntax (no list,
    no "runs X then Y", no YAML gate_id line).

    FAILS TODAY for the same Shape-2 reason -- mirrors the live HEAD failure in
    `test_slice_04_coherence_hook_distill_deliver.py` against the real deliver
    prose (diagnostic names `dispatch`).
    """
    line = (
        "This core holds the mode dispatch, the per-slice spine + feature-end "
        "cycle, the dispatch markers + entry gate + per-slice phase table, "
        "prior-wave reading, the rigor profile, and the output contract."
    )

    assert _inline_restatement(line, _CATALOG) is None


# -- GUARD: the hook stays strong (all 3 shapes, common-word gate_id) ----------


def test_yaml_gate_id_line_still_flagged_even_for_a_common_word_gate_id() -> None:
    """Shape 1 (`gate_id: <id>` YAML-list line) must still FAIL, common word or
    not -- the registry block pasted verbatim into prose is always drift."""
    text = "gate_stack:\n  gate_in:\n    - gate_id: dispatch\n"

    assert _inline_restatement(text, _CATALOG) == "dispatch"


def test_bullet_list_enumeration_still_flagged_even_for_a_common_word_gate_id() -> None:
    """Shape 3 (>=2 consecutive bullet items, each a bare catalog gate_id) must
    still FAIL -- the bullet-list re-enumeration of `gate_stack`."""
    text = "- dispatch\n- verify-wave-dispatch\n"

    assert _inline_restatement(text, _CATALOG) == "dispatch"


def test_genuine_inline_stack_sentence_still_flagged_even_for_a_common_word_gate_id() -> (
    None
):
    """Shape 2's OWN canonical genuine-enumeration example (`_inline_restatement`
    docstring: "the gate-out stack runs `a` then `b`") must still FAIL when `a`
    happens to be the common-word gate_id `dispatch` -- the fix narrows the
    command/common-word MENTION form, it does not blanket-exempt the token."""
    line = (
        "The gate-out stack for this wave runs, in order: `dispatch` then "
        "`verify-wave-dispatch`."
    )

    assert _inline_restatement(line, _CATALOG) == "dispatch"


# -- GUARD: the full pipeline (evaluate_coherence) stays strong ----------------


def test_evaluate_coherence_still_fails_a_genuine_enumeration_with_common_word_id(
    tmp_path: Path,
) -> None:
    """End-to-end: pointer + inline-restatement + both-SSOT + orphan checks all
    still emit FAIL for a genuine gate-stack enumeration naming a common-word
    gate_id (`dispatch` is a REAL entry in the shipped
    `nWave/gates/_catalog.yaml`, so this exercises the real catalog read, not a
    local stand-in), even after the precision fix narrows the false-positive
    command/common-word collision."""
    waves_dir = tmp_path / "waves"
    waves_dir.mkdir()
    (waves_dir / "deliver.yaml").write_text(
        "gate_stack:\n"
        "  gate_in:\n"
        "    - gate_id: dispatch\n"
        "output_contract:\n"
        "  ref_sections:\n"
        "    - id: Persona\n",
        encoding="utf-8",
    )
    prose = tmp_path / "deliver.md"
    prose.write_text(
        "<!-- gates-ref: deliver -->\n"
        "<!-- outputs-ref: deliver -->\n"
        "The gate-out stack for this wave runs, in order: `dispatch` then "
        "`verify-wave-dispatch`.\n",
        encoding="utf-8",
    )

    outcome = evaluate_coherence("deliver", prose, waves_dir)

    assert outcome.verdict is GateVerdict.FAIL
    assert "dispatch" in outcome.diagnostic
