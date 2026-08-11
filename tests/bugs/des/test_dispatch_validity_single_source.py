"""Regression AT -- fix-dispatch-validity-ssot.

RCA (team-lead dispatch, complete): SSOT VIOLATION, not a one-off bug. At
least THREE independent loci decide whether an atdd_pure dispatch's
``DES-PHASE`` marker is required, each carrying its OWN copy of the
"phase is required unless X" rule:

  1. ``des.cli.dispatch.main`` -- the GENERATOR (``_wave_is_phaseless``,
     ``dispatch.py:678-679``).
  2. ``des.domain.des_marker_parser.classify_atdd_pure_dispatch`` /
     ``atdd_pure_missing_marker`` -- the MARKER classifier
     (``_declared_wave_is_phaseless``, ``des_marker_parser.py:420-434``).
  3. ``des.domain.marker_completeness_policy.MarkerCompletenessPolicy
     ._validate_atdd_pure`` -- the COMPLETENESS policy, reached via
     ``pre_tool_use_service.py:267``, the one that emits
     ``DES_MARKERS_INCOMPLETE``.

On 2026-07-18 loci 1-2 were taught that an AUTHORING wave (discuss / design /
devops / distill) is phaseless BY CONSTRUCTION -- derived from the
``WAVE_DISPATCH_PROFILES`` datum (``runs_tests == False``), never a
hand-written wave list. Locus 3 was NOT taught the same lesson: it still
demands ``DES-PHASE`` unconditionally (only exempting ``PHASELESS_LANES``,
never consulting ``markers.declared_wave`` / ``WAVE_DISPATCH_PROFILES`` at
all). So the SAME correctly-generated DISCUSS dispatch is simultaneously
``classify_atdd_pure_dispatch(...) == "valid"`` (locus 2) and
``MarkerCompletenessPolicy().validate(...).is_valid is False`` with reason
``"DES_MARKERS_INCOMPLETE: DES-PHASE missing"`` (locus 3) -- reproduced live,
2026-07-18::

    uv run des dispatch --mode atdd_pure --project-id probe --slice \
        feature-end --wave discuss --intent x
    # -> parse the stdout prompt, feed the same DesMarkers to both loci

The defect is not the missing branch -- it is that a branch had to be added
in N places at all. This file pins the SSOT PROPERTY (every validity-deciding
locus AGREES on well-formedness) so a future wave/lane/phase axis widening
cannot silently re-diverge the loci one at a time again.

Driving surface (Mandate-16, driving-port-only + P1-P4 in-process active-RED
pattern): ``des.cli.dispatch.main()`` in-process (the REAL generator, mirrors
``test_dispatch_lane_for_non_code_facing_agents.py``'s
``_run_dispatch_main``) renders REAL dispatch prompts; ``DesMarkerParser
().parse()`` turns each into the SAME ``DesMarkers`` instance fed to BOTH
``classify_atdd_pure_dispatch`` and ``MarkerCompletenessPolicy.validate`` --
the two loci under test. No hand-derived "expected valid" shape for the
property test: every prompt is a REAL rendering from production locus 1, so
"well-formed" is never a test-side guess.

Author-only regression test -- no production code touched (per dispatch
instruction). Every assertion is a REAL assertion on production code's
observable behaviour; a failure is a semantic ``AssertionError``, never an
import/collection error (Mandate 7 -- RED-not-BROKEN).

covers: fix-dispatch-validity-ssot
"""

from __future__ import annotations

import contextlib
import io
from pathlib import Path

import pytest

from des.cli import dispatch
from des.domain.des_marker_parser import (
    DesMarkerParser,
    DesMarkers,
    classify_atdd_pure_dispatch,
)
from des.domain.marker_completeness_policy import MarkerCompletenessPolicy
from des.domain.wave_dispatch_profile import WAVE_DISPATCH_PROFILES
from tests.common.delivery_contract_fixture import contract_args


# tests/bugs/des/<this file> -> parents[3] == checkout root (this file is
# directly under tests/bugs/des/, so the path is 4 levels deep: file/des/bugs/tests/root).
_REPO_ROOT = Path(__file__).resolve().parents[3]

_PARSER = DesMarkerParser()
_COMPLETENESS_POLICY = MarkerCompletenessPolicy()

# A representative non-feature-end canonical phase -- used everywhere a
# test-running wave needs a --phase to generate a well-formed dispatch.
# D_REFACTOR_COMMIT is the per-slice COMMIT phase (atdd_pure_phases.py
# COMMIT_GATE_PHASES), deliberately NOT a FEATURE_END_PHASES member, so
# picking it never triggers dispatch.py's feature-end slice auto-correct
# (--slice stays 'slice-01' unchanged).
_REPRESENTATIVE_PHASE = "D_REFACTOR_COMMIT"


def _run_dispatch_main(argv: list[str]) -> tuple[int, str, str]:
    """Drive `des dispatch`'s real `main()` in-process; capture exit/stdio.

    Mirrors ``test_dispatch_lane_for_non_code_facing_agents.py``'s helper of
    the same name -- ``main()`` uses argparse, which raises ``SystemExit``
    for a usage error; caught here so a test body asserts a real, semantic
    ``AssertionError`` on the observed exit code, never an uncaught
    ``SystemExit`` crash.
    """
    stdout_buf, stderr_buf = io.StringIO(), io.StringIO()
    try:
        with (
            contextlib.redirect_stdout(stdout_buf),
            contextlib.redirect_stderr(stderr_buf),
        ):
            exit_code = dispatch.main(argv)
    except SystemExit as exc:
        exit_code = exc.code if isinstance(exc.code, int) else 1
    return exit_code, stdout_buf.getvalue(), stderr_buf.getvalue()


def _generated_markers(argv: list[str]) -> DesMarkers:
    """Generate a REAL dispatch prompt via production locus 1 (the
    generator), then parse it with the SAME ``DesMarkerParser`` production
    locus 2 and locus 3 both consume. Asserts generation itself succeeded --
    a non-zero exit here means the argv was malformed, not a locus-agreement
    finding, and would silently defeat the property test with an empty
    prompt.
    """
    exit_code, stdout, stderr = _run_dispatch_main(
        [*argv, *contract_args(_REPO_ROOT, seed=False)]
    )
    assert exit_code == 0, (
        f"dispatch generation itself must succeed for argv={argv!r} -- a "
        "non-zero exit here is a fixture problem, not the property under "
        f"test. exit_code={exit_code}, stderr={stderr!r}"
    )
    return _PARSER.parse(stdout)


def _loci_verdicts(markers: DesMarkers) -> dict[str, bool]:
    """Query every marker-validity-deciding locus this file pins agreement
    across. Returns {locus_name: is_valid}. Adding a locus here widens the
    SSOT property to cover it automatically -- the parametrized tests below
    iterate this mapping, never a hand-picked pair.
    """
    return {
        "classify_atdd_pure_dispatch": classify_atdd_pure_dispatch(markers) == "valid",
        "MarkerCompletenessPolicy": _COMPLETENESS_POLICY.validate(markers).is_valid,
    }


def _assert_loci_agree(markers: DesMarkers, *, context: str) -> None:
    verdicts = _loci_verdicts(markers)
    distinct = set(verdicts.values())
    assert len(distinct) == 1, (
        f"validity-deciding loci DISAGREE for {context}: {verdicts} -- the "
        "same DesMarkers instance is simultaneously valid to one locus and "
        f"invalid to another. markers={markers!r}"
    )


# ---------------------------------------------------------------------------
# 1. THE LIVE CONTRADICTION -- reproduces the exact repro recipe from the
#    dispatch instruction, byte-for-byte (des dispatch ... --wave discuss).
# ---------------------------------------------------------------------------


def test_live_discuss_dispatch_contradicts_across_loci() -> None:
    """The EXACT reproduction recipe: a des-dispatch-generated DISCUSS
    (authoring-wave) prompt must be classified identically by every
    validity-deciding locus.

    RED today for the right reason: ``classify_atdd_pure_dispatch`` returns
    ``"valid"`` (locus 2, fixed 2026-07-18) while
    ``MarkerCompletenessPolicy().validate(...).is_valid`` is ``False`` with
    reason ``DES_MARKERS_INCOMPLETE: DES-PHASE missing`` (locus 3, never
    taught the wave-phaseless exemption) -- a genuine semantic
    ``AssertionError``, not a crash.
    """
    markers = _generated_markers(
        [
            "--mode",
            "atdd_pure",
            "--project-id",
            "probe",
            "--slice",
            "feature-end",
            "--wave",
            "discuss",
            "--intent",
            "x",
        ]
    )

    assert markers.mode == "atdd_pure"
    assert markers.declared_wave == "discuss"
    assert markers.atdd_pure_phase is None, (
        "a DISCUSS dispatch must legitimately omit DES-PHASE -- if this "
        f"fails the fixture itself has drifted. markers={markers!r}"
    )

    classifier_verdict = classify_atdd_pure_dispatch(markers) == "valid"
    policy_result = _COMPLETENESS_POLICY.validate(markers)

    assert classifier_verdict == policy_result.is_valid, (
        "the SAME generated DISCUSS dispatch is classified 'valid' by "
        f"classify_atdd_pure_dispatch ({classifier_verdict}) and "
        f"{'valid' if policy_result.is_valid else 'invalid'} by "
        f"MarkerCompletenessPolicy (reason={policy_result.reason!r}) -- the "
        "two production loci disagree on the SAME dispatch's well-"
        f"formedness. markers={markers!r}"
    )
    assert policy_result.is_valid, (
        "an authoring-wave dispatch with no DES-PHASE is well-formed by "
        "construction (ATDDPurePhase is DELIVER-carpaccio-scoped) -- "
        f"MarkerCompletenessPolicy must accept it too. reason="
        f"{policy_result.reason!r}"
    )


# ---------------------------------------------------------------------------
# 2. THE SSOT PROPERTY -- for EVERY wave in WAVE_DISPATCH_PROFILES, a
#    well-formed dispatch (no --lane) is accepted identically by every
#    locus. Parametrized off the datum, never a hand-written list.
# ---------------------------------------------------------------------------


_ALL_WAVES: tuple[str, ...] = tuple(sorted(WAVE_DISPATCH_PROFILES))

assert _ALL_WAVES, "WAVE_DISPATCH_PROFILES is empty -- the fixture is vacuous"


def _well_formed_argv_for_wave(wave: str, *, project_id: str) -> list[str]:
    """The minimal well-formed ``des dispatch`` argv for ``wave`` -- omits
    ``--phase`` exactly when the wave is phaseless (mirrors what an
    honest operator following ``dispatch.py``'s own usage message would
    pass), never re-deriving the phase-required RULE by hand: the argv is
    fed to the REAL generator, which is free to refuse it if the rule this
    helper assumes is wrong -- ``_generated_markers`` asserts exit_code == 0.
    """
    argv = [
        "--mode",
        "atdd_pure",
        "--project-id",
        project_id,
        "--slice",
        "slice-01",
        "--wave",
        wave,
    ]
    if WAVE_DISPATCH_PROFILES[wave].runs_tests:
        argv += ["--phase", _REPRESENTATIVE_PHASE]
    return argv


@pytest.mark.parametrize("wave", _ALL_WAVES)
def test_well_formed_dispatch_agrees_across_loci_for_every_wave(wave: str) -> None:
    """A REAL, well-formed dispatch for every wave in the datum must be
    accepted by every validity-deciding locus -- not merely AGREE with each
    other (a shared wrong answer would pass a bare agreement check), but
    agree on VALID, since the generator itself only emits well-formed
    prompts.

    RED today for the authoring waves (discuss/design/devops/distill):
    MarkerCompletenessPolicy demands DES-PHASE unconditionally.
    """
    markers = _generated_markers(
        _well_formed_argv_for_wave(wave, project_id=f"probe-{wave}")
    )

    _assert_loci_agree(markers, context=f"wave={wave!r} (well-formed, no lane)")
    verdicts = _loci_verdicts(markers)
    assert all(verdicts.values()), (
        f"a well-formed, REAL-generated dispatch for wave={wave!r} must be "
        f"valid to every locus -- got {verdicts}. markers={markers!r}"
    )


# ---------------------------------------------------------------------------
# 3. THE SSOT PROPERTY, LANE AXIS -- a representative set of lanes (the
#    phaseless 'charter' lane + the phase-bearing 'bugfix' lane) must also
#    agree across loci, orthogonal to the wave axis exercised above.
# ---------------------------------------------------------------------------


def test_well_formed_charter_lane_dispatch_agrees_across_loci() -> None:
    """The ``charter`` lane (``PHASELESS_LANES``) declares no DES-PHASE --
    already the FIRST case this SSOT split on
    (fix-po-charter-dispatch-marker-lane). Pinned here alongside the wave
    axis so a future regression on EITHER axis is caught by the same file.
    """
    markers = _generated_markers(
        [
            "--mode",
            "atdd_pure",
            "--project-id",
            "probe-charter-lane",
            "--slice",
            "slice-01",
            "--lane",
            "charter",
            "--intent",
            "author the expectation charter",
        ]
    )

    _assert_loci_agree(markers, context="lane=charter (phaseless)")
    verdicts = _loci_verdicts(markers)
    assert all(verdicts.values()), (
        f"a well-formed charter-lane dispatch must be valid to every locus "
        f"-- got {verdicts}. markers={markers!r}"
    )


def test_well_formed_bugfix_lane_dispatch_agrees_across_loci() -> None:
    """The ``bugfix`` lane REQUIRES a phase (it is not in ``PHASELESS_LANES``)
    -- a positive control proving the fix does not accidentally widen the
    phaseless exemption to a phase-bearing lane.
    """
    markers = _generated_markers(
        [
            "--mode",
            "atdd_pure",
            "--project-id",
            "probe-bugfix-lane",
            "--slice",
            "slice-01",
            "--lane",
            "bugfix",
            "--phase",
            _REPRESENTATIVE_PHASE,
            "--defect",
            "some defect",
            "--regression-test",
            "test_some_defect",
        ]
    )

    _assert_loci_agree(markers, context="lane=bugfix (phase-bearing)")
    verdicts = _loci_verdicts(markers)
    assert all(verdicts.values()), (
        f"a well-formed bugfix-lane dispatch must be valid to every locus "
        f"-- got {verdicts}. markers={markers!r}"
    )


# ---------------------------------------------------------------------------
# 4. NEGATIVE -- a DELIVER dispatch missing its phase stays invalid in
#    EVERY locus. Must be RED both BEFORE and AFTER the fix: proves the fix
#    widens the vocabulary for phaseless waves/lanes WITHOUT punching a hole
#    in enforcement for a wave that genuinely runs tests and needs a phase.
# ---------------------------------------------------------------------------


def _hand_built_markers(
    *,
    declared_wave: str | None,
    atdd_pure_phase: str | None,
    lane: str | None = None,
    slice_id: str | None = "slice-01",
    project_id: str = "probe",
) -> DesMarkers:
    """Build a DesMarkers instance directly for the negative controls below
    -- these argv shapes are REFUSED by argparse itself (unrecognised
    --wave choice) or are deliberately incoherent (phaseless wave + explicit
    phase), so they cannot be produced via a REAL `des dispatch` invocation
    the way the positive property tests above are. Mirrors the construction
    style already established by
    tests/bugs/des/test_atdd_pure_phaseless_authoring_wave.py for this exact
    domain pair.
    """
    return DesMarkers(
        is_des_task=True,
        is_orchestrator_mode=False,
        mode="atdd_pure",
        project_id=project_id,
        slice_id=slice_id,
        lane=lane,
        declared_wave=declared_wave,
        atdd_pure_phase=atdd_pure_phase,
    )


@pytest.mark.negative_at
def test_deliver_dispatch_missing_phase_stays_invalid_in_every_locus() -> None:
    markers = _hand_built_markers(declared_wave="deliver", atdd_pure_phase=None)

    _assert_loci_agree(markers, context="wave=deliver, no phase (negative)")
    verdicts = _loci_verdicts(markers)
    assert not any(verdicts.values()), (
        "a DELIVER dispatch missing its phase must be REJECTED by every "
        f"locus -- got {verdicts}. markers={markers!r}"
    )


# ---------------------------------------------------------------------------
# 5. NEGATIVE -- an unrecognised DES-WAVE value falls back to requiring the
#    phase in EVERY locus (fail-closed, GDP-6: no silent-wrong).
# ---------------------------------------------------------------------------


@pytest.mark.negative_at
@pytest.mark.parametrize(
    "unrecognised_wave", ["not-a-real-wave", "DISCUSS", "", "deliverr"]
)
def test_unrecognised_wave_requires_phase_in_every_locus(
    unrecognised_wave: str,
) -> None:
    markers = _hand_built_markers(declared_wave=unrecognised_wave, atdd_pure_phase=None)

    _assert_loci_agree(
        markers, context=f"unrecognised wave={unrecognised_wave!r} (negative)"
    )
    verdicts = _loci_verdicts(markers)
    assert not any(verdicts.values()), (
        f"an unrecognised DES-WAVE value {unrecognised_wave!r} must NOT be "
        "silently treated as phaseless in ANY locus -- fail-closed, every "
        f"locus must still require DES-PHASE. got {verdicts}. "
        f"markers={markers!r}"
    )


# ---------------------------------------------------------------------------
# 6. NEGATIVE -- a phaseless wave carrying an EXPLICIT phase is incoherent
#    (self-contradictory) in EVERY locus. This is the SECOND divergence
#    direction: today MarkerCompletenessPolicy only checks "phase absent",
#    never "phase present but the wave forbids one" -- so it currently
#    accepts this self-contradictory envelope as valid while
#    classify_atdd_pure_dispatch correctly rejects it.
# ---------------------------------------------------------------------------


_AUTHORING_WAVES: tuple[str, ...] = tuple(
    sorted(
        wave
        for wave, profile in WAVE_DISPATCH_PROFILES.items()
        if profile.runs_tests is False
    )
)

assert _AUTHORING_WAVES, "WAVE_DISPATCH_PROFILES has no runs_tests=False row"


@pytest.mark.negative_at
@pytest.mark.parametrize("wave", _AUTHORING_WAVES)
def test_phaseless_wave_with_explicit_phase_stays_invalid_in_every_locus(
    wave: str,
) -> None:
    markers = _hand_built_markers(declared_wave=wave, atdd_pure_phase="A_GREEN")

    _assert_loci_agree(
        markers, context=f"wave={wave!r} (phaseless) + explicit phase (negative)"
    )
    verdicts = _loci_verdicts(markers)
    assert not any(verdicts.values()), (
        f"a phaseless wave={wave!r} dispatch combined with an explicit "
        "DES-PHASE is self-contradictory and must be REJECTED by every "
        f"locus -- got {verdicts}. markers={markers!r}"
    )
