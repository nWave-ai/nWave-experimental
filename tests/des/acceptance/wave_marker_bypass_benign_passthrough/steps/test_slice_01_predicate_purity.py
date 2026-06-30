"""AT-6 -- the corrected guard's discriminant reads ONLY the prompt (purity).

Driving port (Mandate-13 driving-port-only, Layer 3 composition): the REAL
``PreToolUseService.validate`` via the production composition root -- the SAME
driving surface as the Tier-A scenarios. AT-6's design intent ("the predicate's
value depends ONLY on the prompt's DES-marker content -- no floor read, no CWD --
and carries_partial_wave_context == True implies is_des_task == False") is
witnessed THROUGH the driving port, NOT at the function boundary:

  * PURITY-vs-floor-identity: a partial-context prompt yields the SAME decision
    under a `design`, `devops`, or `distill` armed floor. If the discriminant
    leaked the floor's wave value into its decision, the action would differ by
    floor; the invariance is the observable purity witness.
  * is_des_task IMPLICATION: a FULLY DES-VALIDATION dispatch (is_des_task) is
    NEVER blocked by the S2 bypass branch under any armed floor -- it is handled
    on the is_des_task path upstream. This pins that carries_partial_wave_context
    excludes the is_des_task case (a complete dispatch is not a partial-context
    bypass).

Mandate-9 note: this feature is @real-io (real floor filesystem + production
composition root) -> Layer 3, so the property is EXAMPLE/parametrize-based across
the floor-wave axis, NOT hypothesis-PBT (OR-reduction precludes PBT at @real-io;
the design's "PBT over generated marker subsets" is realized as the enumerated
floor-invariance property at the driving port -- the canonical layer-3 treatment).

Active-RED scaffold (ADR-025 + ADR-028, atdd_pure -- NOT @skip): at HEAD the OLD
floor-presence guard ALLOWS a partial-markers prompt (has_des_markers True), so
the purity property's expected BLOCK fails RED for every floor wave -- a semantic
AssertionError, never a collection / import / setup error. GREEN once DELIVER
re-points the guard to carries_partial_wave_context.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from .composition_slice_01 import (
    _PROMPT_FULLY_MARKERLESS,
    _PROMPT_PARTIAL_MARKERS,
    GuardComposition,
)


# A fully valid DES dispatch (carries DES-VALIDATION -> is_des_task True). It is
# NOT a partial-context bypass; the S2 branch must never block it under any floor.
_PROMPT_FULL_DES_VALIDATION = (
    "<!-- DES-VALIDATION : required -->\n"
    "<!-- DES-PROJECT-ID : fix-wave-marker-bypass-benign-passthrough -->\n"
    "<!-- DES-STEP-ID : design-1 -->\n"
    "proceed with the complete in-wave dispatch"
)

# The floor-wave identity axis: the discriminant must be INVARIANT across these.
_FLOOR_WAVES = ("design", "devops", "distill")


@pytest.mark.parametrize("floor_wave", _FLOOR_WAVES)
def test_partial_context_blocked_invariant_across_floor_identity(
    tmp_path: Path, floor_wave: str
) -> None:
    """CONTRACT_SHAPE: bounded-change

    AT-6 (purity): a partial-context bypass is BLOCKED regardless of which
    wave the floor names -- the discriminant reads the prompt, not the floor."""
    composition = GuardComposition()
    action = composition.decide_under_floor(
        tmp_path, floor_wave=floor_wave, prompt=_PROMPT_PARTIAL_MARKERS
    )
    assert action == "block", (
        "the corrected guard must BLOCK a partial-context bypass under ANY armed "
        f"floor (here {floor_wave!r}) -- the decision depends ONLY on the prompt's "
        "DES-marker content (carries_partial_wave_context), never on the floor's "
        f"wave identity; the guard returned {action!r}."
    )


@pytest.mark.parametrize("floor_wave", _FLOOR_WAVES)
def test_benign_markerless_allowed_invariant_across_floor_identity(
    tmp_path: Path, floor_wave: str
) -> None:
    """CONTRACT_SHAPE: bounded-change

    AT-6 (purity): a benign markerless prompt is ALLOWED regardless of which
    wave the floor names -- floor identity never flips the benign decision."""
    composition = GuardComposition()
    action = composition.decide_under_floor(
        tmp_path, floor_wave=floor_wave, prompt=_PROMPT_FULLY_MARKERLESS
    )
    assert action == "allow", (
        "a benign fully-markerless prompt must be ALLOWED under ANY armed floor "
        f"(here {floor_wave!r}) -- the discriminant carries no floor-identity "
        f"dependence; the guard returned {action!r}."
    )


@pytest.mark.parametrize("floor_wave", _FLOOR_WAVES)
def test_full_des_validation_not_blocked_by_bypass_branch(
    tmp_path: Path, floor_wave: str
) -> None:
    """CONTRACT_SHAPE: bounded-change

    AT-6 (is_des_task implication): a complete DES-VALIDATION dispatch is NOT a
    partial-context bypass -- the S2 WAVE_MARKER_BYPASS branch never blocks it.

    carries_partial_wave_context excludes the is_des_task case by construction
    (... and not is_des_task). Witnessed on the ABSENCE of the bypass reason, not
    a bare allow: a complete dispatch is is_des_task, so it leaves the
    not-is_des_task block entirely and is routed to completeness validation; it
    may be blocked THERE (a different, legitimate reason), but it is NEVER tagged
    WAVE_MARKER_BYPASS. The property pins that the bypass branch does not claim it.
    """
    composition = GuardComposition()
    reason = composition.reason_under_floor(
        tmp_path, floor_wave=floor_wave, prompt=_PROMPT_FULL_DES_VALIDATION
    )
    assert "WAVE_MARKER_BYPASS" not in reason, (
        "a complete DES-VALIDATION dispatch (is_des_task) is NOT a partial-context "
        "bypass; the WAVE_MARKER_BYPASS branch must never claim it "
        "(carries_partial_wave_context implies not is_des_task); under floor "
        f"{floor_wave!r} the block reason was {reason!r}."
    )
