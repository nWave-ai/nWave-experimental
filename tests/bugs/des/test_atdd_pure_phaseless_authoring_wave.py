"""Regression AT -- fix-dispatch-guard-blind-to-authoring-wave.

RCA (Rex, complete): ``classify_atdd_pure_dispatch`` and
``atdd_pure_missing_marker`` (``src/des/domain/des_marker_parser.py``) demand
``DES-PHASE`` unconditionally, exempting ONLY a ``markers.lane in
PHASELESS_LANES`` dispatch (the ``charter`` lane). Neither function ever
consults ``markers.declared_wave`` -- which EXISTS and IS populated from the
``DES-WAVE`` marker at parse time (``des_marker_parser.py:337-338,370``). An
AUTHORING wave (discuss / design / devops / distill) is phaseless BY
CONSTRUCTION, exactly as the ``charter`` lane is: ``ATDDPurePhase`` stays
DELIVER-carpaccio-scoped (``atdd_pure_phases.py`` docstring), so a discuss/
design/devops/distill dispatch legitimately declares no ``DES-PHASE`` at
all -- yet today's guard treats that honest omission as defective, naming
``des-phase`` as missing.

Reproduced live (``des dispatch --mode atdd_pure --project-id probe --slice
feature-end --wave discuss --intent x``): the generated envelope carries
``DES-WAVE: discuss`` and no ``DES-PHASE`` marker (correct, by construction);
feeding the parsed markers to the production classifier yields
``classify_atdd_pure_dispatch == "defective"`` /
``atdd_pure_missing_marker == "des-phase"`` -- a false rejection of a
correctly-shaped dispatch.

The queryable per-wave datum the fix reads already exists:
``WAVE_DISPATCH_PROFILES`` (``src/des/domain/wave_dispatch_profile.py``),
keyed by wave name, each row carrying ``runs_tests: bool``
(``False`` for discuss/design/devops/distill, ``True`` for deliver/
feature-end). The correct fix reads ``markers.declared_wave`` +
``WAVE_DISPATCH_PROFILES[...].runs_tests`` -- never a hand-written wave
list, so the exemption cannot silently go stale as the wave vocabulary
grows.

CRITICAL CONSTRAINT (per dispatch instruction, preserved here as a comment
so a future reader does not "fix" this test into a standing violation):
this file never asserts anything about ``markers.wave`` (the ACTIVE/floor
wave, sourced ONLY by ``WaveActiveReader``, never by the parser -- S22.7
asymmetric-authority invariant: a ``DES-WAVE`` declaration ARMS
enforcement, it never AUTHORIZES). ``markers.declared_wave`` is a pure
prompt-parse value; the S2a legitimacy check (``declared_wave == wave``,
``pre_tool_use_service.py:219``) lives elsewhere and is untouched by this
fix.

Driving surface (Mandate-16, driving-port-only): the two domain functions
under diagnosis, called directly against hand-built ``DesMarkers`` instances
-- the same construction style already established by
``tests/des/unit/domain/test_des_marker_parser.py`` for this exact pure
domain pair. No I/O, no subprocess: ``classify_atdd_pure_dispatch`` /
``atdd_pure_missing_marker`` are pure functions over a frozen dataclass.

Author-only regression test -- no production code touched (per dispatch
instruction). Every assertion is a REAL assertion on production code's
observable behaviour; a failure is a semantic ``AssertionError``, never an
import/collection error (Mandate 7 -- RED-not-BROKEN).

covers: fix-dispatch-guard-blind-to-authoring-wave
"""

from __future__ import annotations

import pytest

from des.cli.dispatch import _canonical_phase_values
from des.domain.des_marker_parser import (
    DesMarkers,
    atdd_pure_missing_marker,
    classify_atdd_pure_dispatch,
)
from des.domain.wave_dispatch_profile import WAVE_DISPATCH_PROFILES


def _markers(
    *,
    declared_wave: str | None,
    atdd_pure_phase: str | None = None,
    slice_id: str | None = "slice-01",
) -> DesMarkers:
    """Build the minimal ``DesMarkers`` shape the two functions under test
    consult: ``mode``, ``slice_id``, ``lane``, ``atdd_pure_phase``, and
    (once fixed) ``declared_wave``. ``lane`` stays ``None`` throughout --
    this file's whole point is the WAVE axis, orthogonal to the existing
    ``PHASELESS_LANES`` (lane) axis fixed by
    ``fix-po-charter-dispatch-marker-lane``.
    """
    return DesMarkers(
        is_des_task=True,
        is_orchestrator_mode=False,
        mode="atdd_pure",
        slice_id=slice_id,
        lane=None,
        declared_wave=declared_wave,
        atdd_pure_phase=atdd_pure_phase,
    )


# The closed set of AUTHORING waves (``runs_tests is False``) -- derived from
# the SAME queryable datum the fix must read, never a hand-written literal
# list. If the wave vocabulary grows a new authoring wave, this parametrize
# grows with it automatically.
_AUTHORING_WAVES: tuple[str, ...] = tuple(
    sorted(
        wave
        for wave, profile in WAVE_DISPATCH_PROFILES.items()
        if profile.runs_tests is False
    )
)

# The closed set of TEST-RUNNING waves (``runs_tests is True``) -- the
# complement, used by the negative controls below.
_TEST_RUNNING_WAVES: tuple[str, ...] = tuple(
    sorted(
        wave
        for wave, profile in WAVE_DISPATCH_PROFILES.items()
        if profile.runs_tests is True
    )
)


# Sanity on the fixture itself: an empty parametrize set would make every
# test below vacuously pass (verified:true-on-zero family). Both sides of
# the WAVE_DISPATCH_PROFILES partition must be non-empty for this file's
# assertions to mean anything.
assert _AUTHORING_WAVES, "WAVE_DISPATCH_PROFILES has no runs_tests=False row"
assert _TEST_RUNNING_WAVES, "WAVE_DISPATCH_PROFILES has no runs_tests=True row"


# ---------------------------------------------------------------------------
# 1. POSITIVE -- an authoring-wave dispatch with NO phase is valid.
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("wave", _AUTHORING_WAVES)
def test_authoring_wave_dispatch_without_phase_is_classified_valid(
    wave: str,
) -> None:
    """A discuss/design/devops/distill dispatch legitimately declares NO
    ``DES-PHASE`` marker -- ``ATDDPurePhase`` is DELIVER-carpaccio-scoped by
    construction, exactly as the ``charter`` LANE already declares none.

    RED today for the right reason: ``classify_atdd_pure_dispatch`` never
    consults ``declared_wave``, so it falls into the unconditional
    ``atdd_pure_phase is None -> "defective"`` branch for every wave here.
    """
    markers = _markers(declared_wave=wave, atdd_pure_phase=None)

    assert classify_atdd_pure_dispatch(markers) == "valid", (
        f"a {wave!r}-wave dispatch with no DES-PHASE must classify 'valid' "
        "-- the wave is phaseless by construction, mirroring the "
        f"PHASELESS_LANES relaxation. markers={markers!r}"
    )
    assert atdd_pure_missing_marker(markers) is None, (
        f"a {wave!r}-wave dispatch with no DES-PHASE must name NO missing "
        f"marker (the omission is honest, not defective). markers={markers!r}"
    )


# ---------------------------------------------------------------------------
# 2. NEGATIVE control -- a DELIVER-family dispatch with no phase stays
#    defective. Must be GREEN both BEFORE and AFTER the fix: proves the fix
#    widens the vocabulary for authoring waves WITHOUT punching a hole in
#    enforcement for the waves that genuinely run tests and need a phase.
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("wave", _TEST_RUNNING_WAVES)
def test_test_running_wave_dispatch_without_phase_stays_defective(
    wave: str,
) -> None:
    """deliver / feature-end run the carpaccio phase machinery -- a missing
    ``DES-PHASE`` there is a genuine defect, never an honest omission. This
    positive control must not regress when the authoring-wave exemption is
    added.
    """
    markers = _markers(declared_wave=wave, atdd_pure_phase=None)

    assert classify_atdd_pure_dispatch(markers) == "defective", (
        f"a {wave!r}-wave dispatch (runs_tests=True) with no DES-PHASE must "
        f"stay 'defective' -- the authoring-wave exemption must not widen "
        f"to cover a test-running wave. markers={markers!r}"
    )
    assert atdd_pure_missing_marker(markers) == "des-phase", (
        f"a {wave!r}-wave dispatch missing DES-PHASE must name 'des-phase' "
        f"as the missing marker. markers={markers!r}"
    )


# ---------------------------------------------------------------------------
# 3. NEGATIVE control -- an UNRECOGNISED wave value falls back to requiring
#    the phase. Fail-closed: exercises the `.get() is None` branch the fix
#    must add, proving the widened vocabulary lookup is not silently
#    permissive for a typo'd / out-of-vocabulary DES-WAVE value.
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "unrecognised_wave",
    ["not-a-real-wave", "DISCUSS", "", "deliverr"],
)
def test_unrecognised_wave_falls_back_to_requiring_phase(
    unrecognised_wave: str,
) -> None:
    """A ``DES-WAVE`` value outside ``WAVE_DISPATCH_PROFILES`` (a typo, an
    out-of-vocabulary token, an empty string) must NOT be silently treated
    as an authoring wave -- ``WAVE_DISPATCH_PROFILES.get(declared_wave)``
    returns ``None`` for all four inputs above, and the fix must fall
    through to the SAME phase-required behaviour a dispatch with no
    declared wave at all gets today (fail-closed, GDP-6: no silent-wrong).
    """
    markers = _markers(declared_wave=unrecognised_wave, atdd_pure_phase=None)

    assert classify_atdd_pure_dispatch(markers) == "defective", (
        f"an unrecognised DES-WAVE value {unrecognised_wave!r} must NOT be "
        "silently treated as an authoring-wave exemption -- fail-closed, it "
        f"must still require DES-PHASE. markers={markers!r}"
    )
    assert atdd_pure_missing_marker(markers) == "des-phase", (
        f"an unrecognised DES-WAVE value {unrecognised_wave!r} missing "
        f"DES-PHASE must name 'des-phase' as the missing marker. "
        f"markers={markers!r}"
    )


# ---------------------------------------------------------------------------
# 4. NEGATIVE -- a phaseless wave WITH an explicit phase is incoherent
#    (symmetric to the existing PHASELESS_LANES + explicit-phase
#    incoherence, `lane_profile.py` / `classify_atdd_pure_dispatch` line
#    450-451). A fix that only ADDS the "no phase -> valid" exemption
#    without also closing this inverse leaves a self-contradictory
#    envelope classified 'valid'.
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("wave", _AUTHORING_WAVES)
def test_authoring_wave_combined_with_explicit_phase_is_defective(
    wave: str,
) -> None:
    """An authoring-wave dispatch (``discuss``/``design``/``devops``/
    ``distill``) that ALSO carries an explicit ``DES-PHASE`` is
    self-contradictory -- ``ATDDPurePhase`` values name DELIVER-carpaccio
    states (``A_GREEN``, ``D_REFACTOR_COMMIT``, ...), meaningless for a wave
    that runs no phase machinery at all.

    RED today for the right reason (a NEW gap, not merely the mirror of
    test 1): today's ``classify_atdd_pure_dispatch`` never reads
    ``declared_wave``, so a ``discuss`` + ``A_GREEN`` combination sails
    through the existing phase/scope XOR check as coherent (``A_GREEN`` is
    not a feature-end phase, ``slice_id="slice-01"`` is not the feature-end
    scope) and is classified 'valid' -- a fix that ONLY adds the positive
    exemption (test 1) without this symmetric guard would ship a
    self-contradictory envelope as accepted.
    """
    markers = _markers(declared_wave=wave, atdd_pure_phase="A_GREEN")

    assert classify_atdd_pure_dispatch(markers) == "defective", (
        f"a {wave!r}-wave dispatch (phaseless by construction) combined "
        "with an explicit DES-PHASE must be 'defective' -- symmetric to "
        f"the PHASELESS_LANES + explicit-phase incoherence. markers={markers!r}"
    )


@pytest.mark.parametrize("phase_value", list(_canonical_phase_values()))
def test_representative_authoring_wave_rejects_every_canonical_phase(
    phase_value: str,
) -> None:
    """The class-level check (catches the CLASS, not one phase token, mirror
    of ``test_dispatch_refuses_phaseless_lane_combined_with_explicit_phase``
    in ``test_dispatch_lane_for_non_code_facing_agents.py``): a single
    representative authoring wave (``discuss``) rejects EVERY canonical
    ``ATDDPurePhase`` value, not just ``A_GREEN``.
    """
    markers = _markers(declared_wave="discuss", atdd_pure_phase=phase_value)

    assert classify_atdd_pure_dispatch(markers) == "defective", (
        f"a discuss-wave dispatch combined with explicit DES-PHASE "
        f"{phase_value!r} must be 'defective'. markers={markers!r}"
    )
