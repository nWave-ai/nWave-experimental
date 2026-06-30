"""AT-10 -- carries_des_validation treats both DES-VALIDATION spellings as
equivalent and reads ONLY the prompt (purity + either-form equivalence).

ADR-001 Amendment 1. Driving port (Mandate-13 driving-port-only, Layer 3
composition): the REAL ``PreToolUseService.validate`` via the production
composition root -- the SAME driving surface as the Tier-A scenarios. AT-10's
design intent ("carries_des_validation depends ONLY on the prompt's DES-VALIDATION
content -- no floor read, no CWD; is_des_task implies carries_des_validation; a
plain-line-only prompt is carries_des_validation True; a neither-form prompt is
carries_des_validation False; and carries_partial_wave_context True implies
carries_des_validation False") is witnessed THROUGH the driving port on the
observable WAVE_MARKER_BYPASS veto surface, NOT at the function boundary:

  * EITHER-FORM EQUIVALENCE: both the HTML-comment and the plain-line DES-VALIDATION
    forms must yield the SAME observable -- the S2 bypass veto does NOT fire (the
    dispatch carries the required marker). If the discriminant recognized only the
    HTML-comment form (the slice-01 defect), the plain-line row would fire the
    bypass; equivalence is the observable witness that carries_des_validation
    subsumes is_des_task.
  * NEITHER-FORM -> BYPASS: a partial dispatch carrying NEITHER form fires the
    bypass veto. This pins carries_partial_wave_context True ==>
    carries_des_validation False (the exclusion's contrapositive).
  * PURITY-vs-floor-identity: each form yields the SAME bypass-veto outcome under a
    `design`, `devops`, or `distill` armed floor -- the discriminant reads the
    prompt, never the floor's wave value.

Mandate-9 note: this feature is @real-io (real floor filesystem + production
composition root) -> Layer 3, so the property is EXAMPLE/parametrize-based across
the (form x floor-wave) axes, NOT hypothesis-PBT (OR-reduction precludes PBT at
@real-io; the design's "PBT over generated marker subsets x both validation forms"
is realized as the enumerated form-x-floor matrix at the driving port -- the
canonical layer-3 treatment).

Active-RED scaffold (ADR-025 + ADR-028, atdd_pure -- NOT @skip): at HEAD the
slice-01 guard keys on ``not is_des_task``, so the PLAIN-LINE rows fire the bypass
veto (is_des_task False) where AT-10 asserts it must NOT -- a semantic
AssertionError for every floor wave. The HTML-comment rows + the neither-form rows
are preservation-GREEN. GREEN once DELIVER re-points the exclusion to
``not carries_des_validation``.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from .composition_slice_03 import MarkerFormComposition


# The required marker in the HTML-comment form (is_des_task True at HEAD).
_PROMPT_HTML_COMMENT_DES_VALIDATION = (
    "<!-- DES-VALIDATION : required -->\n"
    "<!-- DES-PROJECT-ID : fix-wave-marker-bypass-benign-passthrough -->\n"
    "<!-- DES-STEP-ID : design-1 -->\n"
    "proceed with the complete in-wave dispatch (html-comment validated)"
)

# The required marker in the PLAIN-LINE form (is_des_task False, has_des_markers
# True -- the slice-01 false-positive shape the refined predicate must recognize).
_PROMPT_PLAIN_LINE_DES_VALIDATION = (
    "DES-VALIDATION: required\n"
    "DES-PROJECT-ID: fix-wave-marker-bypass-benign-passthrough\n"
    "DES-STEP-ID: design-1\n"
    "proceed with the complete in-wave dispatch (plain-line validated)"
)

# Partial markers carrying NEITHER DES-VALIDATION form -- a genuine bypass.
_PROMPT_NEITHER_VALIDATION_FORM = (
    "DES-PROJECT-ID: fix-wave-marker-bypass-benign-passthrough\n"
    "DES-STEP-ID: design-1\n"
    "proceed with the in-wave work (no DES-VALIDATION in either form)"
)

# The floor-wave identity axis: the discriminant must be INVARIANT across these.
_FLOOR_WAVES = ("design", "devops", "distill")


@pytest.mark.parametrize("floor_wave", _FLOOR_WAVES)
def test_html_comment_validation_not_bypass_blocked(
    tmp_path: Path, floor_wave: str
) -> None:
    """CONTRACT_SHAPE: bounded-change

    AT-10 (either-form, HTML-comment arm): a complete HTML-comment DES-VALIDATION
    dispatch is NOT tagged WAVE_MARKER_BYPASS under any armed floor.

    Preservation arm (is_des_task True ==> carries_des_validation True): GREEN at
    HEAD and post-fix -- the HTML-comment form was always excluded.
    """
    bypass_fired = MarkerFormComposition().bypass_fires_under_floor(
        tmp_path, floor_wave=floor_wave, prompt=_PROMPT_HTML_COMMENT_DES_VALIDATION
    )
    assert not bypass_fired, (
        "a complete HTML-comment DES-VALIDATION dispatch carries the required "
        "marker (is_des_task ==> carries_des_validation) and must NOT be tagged a "
        f"WAVE_MARKER_BYPASS under any armed floor (here {floor_wave!r})."
    )


@pytest.mark.parametrize("floor_wave", _FLOOR_WAVES)
def test_plain_line_validation_not_bypass_blocked(
    tmp_path: Path, floor_wave: str
) -> None:
    """CONTRACT_SHAPE: bounded-change

    AT-10 (either-form, PLAIN-LINE arm): a plain-line DES-VALIDATION dispatch is
    NOT tagged WAVE_MARKER_BYPASS under any armed floor.

    The defect arm (carries_des_validation must recognize the plain-line form):
    RED at HEAD -- the slice-01 ``not is_des_task`` exclusion fires the bypass for
    the plain-line form (is_des_task False). GREEN once the exclusion becomes
    ``not carries_des_validation``. Equivalence with the HTML-comment arm above is
    the observable witness that carries_des_validation subsumes is_des_task.
    """
    bypass_fired = MarkerFormComposition().bypass_fires_under_floor(
        tmp_path, floor_wave=floor_wave, prompt=_PROMPT_PLAIN_LINE_DES_VALIDATION
    )
    assert not bypass_fired, (
        "a plain-line `DES-VALIDATION: required` dispatch carries the required "
        "marker in the OTHER spelling and must be treated EQUIVALENT to the "
        "HTML-comment form -- NOT tagged a WAVE_MARKER_BYPASS under any armed floor "
        f"(here {floor_wave!r}); the refined exclusion uses carries_des_validation "
        "(HTML-comment OR plain-line), not the HTML-comment-only is_des_task."
    )


@pytest.mark.parametrize("floor_wave", _FLOOR_WAVES)
def test_neither_validation_form_is_bypass_blocked(
    tmp_path: Path, floor_wave: str
) -> None:
    """CONTRACT_SHAPE: bounded-change

    AT-10 (exclusion contrapositive): a partial dispatch carrying NEITHER
    DES-VALIDATION form IS tagged WAVE_MARKER_BYPASS under any armed floor.

    Pins carries_partial_wave_context True ==> carries_des_validation False (K1
    survives the refinement). Preservation-GREEN at HEAD and post-fix.
    """
    bypass_fired = MarkerFormComposition().bypass_fires_under_floor(
        tmp_path, floor_wave=floor_wave, prompt=_PROMPT_NEITHER_VALIDATION_FORM
    )
    assert bypass_fired, (
        "a partial-context dispatch carrying NEITHER DES-VALIDATION form has "
        "carries_des_validation False -> carries_partial_wave_context True -> it "
        f"must be BLOCKED as a WAVE_MARKER_BYPASS under any armed floor (here "
        f"{floor_wave!r}); K1 survives the refinement."
    )
