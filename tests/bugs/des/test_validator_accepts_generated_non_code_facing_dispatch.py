"""Regression AT -- fix-validator-refuses-own-generated-dispatch.

DEFECT, reproduced verbatim on this checkout (generator -> validator
round-trip, measured):

    A_GREEN             -> nw-software-crafter          -> PASSED
    C_REVIEWER_AUDIT    -> nw-user-examiner             -> PASSED
    D_REFACTOR_COMMIT   -> nw-software-crafter          -> PASSED
    D_DISTILL           -> nw-acceptance-designer       -> PASSED
    FEATURE_END_EXAMINE -> nw-user-examiner             -> FAILED  <-- the bug
    F_FINAL_REVIEW      -> nw-software-crafter-reviewer -> PASSED

``des dispatch --phase FEATURE_END_EXAMINE`` generates a CORRECT examiner
envelope (``Agent: nw-user-examiner``) whose ``DESIGN_CONTEXT`` body is
citation-free BY DESIGN::

    N/A -- this dispatch is non-code-facing; no source, design, or
    acceptance-test access by construction.

The PreToolUse validator ``des.application.atdd_pure_prompt_validator`` then
REFUSES that very envelope with::

    DESIGN_CONTEXT carries no architecture citation (empty, placeholder, or
    citation-free body)

The system refuses its OWN generator's output -- the generator and the
validator disagree about which dispatch faces are non-code-facing.

RCA (confirmed, file:line on this checkout):

  * ``atdd_pure_prompt_validator._is_non_code_facing_dispatch`` (:116-139)
    recognises exactly ONE examiner face -- the HARDCODED string literal
    ``"C_REVIEWER_AUDIT"`` (:136) -- plus the ``PHASELESS_LANES`` lane face.
    ``FEATURE_END_EXAMINE`` is the SECOND phase routing to the examiner
    (``dispatch._PHASE_AGENTS``, :171) and is therefore never exempted from
    the ``DESIGN_CONTEXT`` content-presence gate (:314).
  * The class: the exemption predicate carries a PRIVATE, hand-maintained
    copy of "which phases are non-code-facing", while the generator derives
    the same fact from ``_PHASE_AGENTS`` x ``_NON_CODE_FACING_AGENTS``. Two
    representations of one concept -> they drifted the moment a second
    examiner phase was added.

The fix this AT pins (crafter's job, NOT implemented here): make the
validator's non-code-facing predicate DERIVE its phase set from the same
generator SSOT (``_PHASE_AGENTS`` filtered by ``_NON_CODE_FACING_AGENTS``)
instead of matching one hardcoded phase literal, so a future phase mapped to
a non-code-facing agent is exempted automatically. Buying acceptance by
handing the examiner a design citation instead is EXPLICITLY refused by the
uncontaminated-envelope leg below.

Driving surface (Mandate 2/16, driving-port-only, default IN-PROCESS): every
leg drives the REAL ``des dispatch`` CLI entry in-process via
``tests.common.in_process_cli.run_cli_in_process`` (the in-process analogue
of ``python -m des.cli.__main__ dispatch ...``) against THIS checkout's real
dispatch SSOT, and feeds its RAW stdout envelope into the REAL
``AtddPurePromptValidator``. Round-trip, never shape: a test asserting "the
phase string appears in the validator" would pass against a predicate wired
wrong -- only generator-in / verdict-out can tell.

COVERAGE DERIVED FROM THE LIVE SYSTEM ON BOTH AXES (the ruled requirement):
the non-code-facing face matrix is computed as

    {phase for phase, agent in dispatch._PHASE_AGENTS.items()
           if agent in dispatch._NON_CODE_FACING_AGENTS}   # phase faces
    | PHASELESS_LANES                                       # lane faces

and the full round-trip is parametrized over
``dispatch._canonical_phase_values()``. Adding a future phase that maps to a
non-code-facing agent enters this test's coverage AUTOMATICALLY, with no edit
here -- that is what makes the CLASS impossible rather than this instance
fixed. The only frozen literals are non-shrinking FLOORS (vacuity witnesses):
they can never narrow coverage, only prove the derivation did not silently
collapse to the empty set (which would make every parametrized leg pass
vacuously).

RED-for-right-reason (current state, real semantic ``AssertionError``, never
an import/collection error):
  * ``test_generated_non_code_facing_dispatch_is_accepted_by_validator`` is
    RED for the ``FEATURE_END_EXAMINE`` face; GREEN for ``C_REVIEWER_AUDIT``
    and the ``charter`` lane face;
  * ``test_generated_dispatch_is_accepted_by_validator_for_every_phase`` is
    RED for the ``FEATURE_END_EXAMINE`` row only; the other 5 rows are GREEN;
  * every vacuity witness, the stripped-citation refusal legs and the
    uncontaminated-envelope legs are GREEN today and MUST stay GREEN after
    the fix (they are what stops the fix being bought by disarming the gate
    or by feeding the examiner design information she must not have).

covers: fix-validator-refuses-own-generated-dispatch
"""

from __future__ import annotations

from pathlib import Path

import pytest

from des.application.atdd_pure_prompt_validator import (
    AtddPurePromptValidator,
    _extract_section_body,
)
from des.cli import dispatch
from des.domain.atdd_pure_phases import FEATURE_END_PHASES
from des.domain.design_context_content_check import (
    design_context_carries_architecture,
)
from des.domain.lane_profile import PHASELESS_LANES
from tests.common.delivery_contract_fixture import contract_args
from tests.common.in_process_cli import run_cli_in_process


# tests/bugs/des/<this file> -> parents[3] == checkout root (mirrors the
# established convention in every sibling test_dispatch_*.py file).
_REPO_ROOT = Path(__file__).resolve().parents[3]

#: The exact refusal the validator emits for a citation-free DESIGN_CONTEXT --
#: the message the defect report quotes verbatim. Used BOTH to prove the
#: refusal is gone for a non-code-facing envelope AND to prove the SAME gate
#: still bites a code-facing one.
_CITATION_REFUSAL = (
    "DESIGN_CONTEXT carries no architecture citation "
    "(empty, placeholder, or citation-free body)"
)


# ---------------------------------------------------------------------------
# Coverage DERIVED from the live system -- axis 1: which dispatch faces are
# non-code-facing. Computed from the GENERATOR's own maps, never a frozen
# literal list of phases.
# ---------------------------------------------------------------------------

#: Phase faces: every phase the generator routes to a non-code-facing agent.
_NON_CODE_FACING_PHASES: frozenset[str] = frozenset(
    phase
    for phase, agent in dispatch._PHASE_AGENTS.items()
    if agent in dispatch._NON_CODE_FACING_AGENTS
)

#: Lane faces: the domain SSOT's phaseless lanes (a phaseless dispatch declares
#: DES-LANE and no DES-PHASE -- the second, orthogonal non-code-facing face).
_NON_CODE_FACING_FACES: tuple[str, ...] = tuple(
    sorted(_NON_CODE_FACING_PHASES | PHASELESS_LANES)
)

#: Non-shrinking FLOOR (vacuity witness only -- never an upper bound). If the
#: derivation above silently collapsed, every parametrized leg would pass
#: vacuously; this floor makes that collapse fail loudly instead.
_NON_CODE_FACING_FLOOR: frozenset[str] = frozenset(
    {"C_REVIEWER_AUDIT", "FEATURE_END_EXAMINE", "charter"}
)

#: Coverage DERIVED from the live system -- axis 2: the code-facing phases,
#: computed by asking the generator's OWN resolver who receives each generable
#: phase. These are the phases whose DESIGN_CONTEXT citation must remain
#: MANDATORY after the fix.
_CODE_FACING_PHASES: tuple[str, ...] = tuple(
    sorted(
        phase
        for phase in dispatch._canonical_phase_values()
        if dispatch._resolve_agent(phase, None, None)
        not in dispatch._NON_CODE_FACING_AGENTS
    )
)


def _run_dispatch(argv: list[str]) -> tuple[int, str, str]:
    """Drive the REAL `des dispatch` CLI in-process (Layer-2 default)."""
    return run_cli_in_process(["dispatch", *argv], cwd=_REPO_ROOT)


def _phase_argv(*, phase: str, project_id: str) -> list[str]:
    """Dispatch argv for a PHASE face, choosing the only coherent slice scope
    (feature-end for a FEATURE_END_PHASES member, slice-01 otherwise)."""
    slice_id = "feature-end" if phase in FEATURE_END_PHASES else "slice-01"
    return [
        "--mode",
        "atdd_pure",
        "--project-id",
        project_id,
        "--slice",
        slice_id,
        "--phase",
        phase,
        "--intent",
        "x",
        *contract_args(_REPO_ROOT, seed=False),
    ]


def _lane_argv(*, lane: str, project_id: str) -> list[str]:
    """Dispatch argv for a phaseless LANE face (declares --lane, no --phase)."""
    return [
        "--mode",
        "atdd_pure",
        "--project-id",
        project_id,
        "--slice",
        "slice-01",
        "--lane",
        lane,
        "--intent",
        "x",
        *contract_args(_REPO_ROOT, seed=False),
    ]


def _face_argv(*, face: str, project_id: str) -> list[str]:
    """Argv for a derived non-code-facing FACE -- lane-shaped when the face is
    a phaseless lane, phase-shaped otherwise. Derived dispatch, so a future
    face of either kind is driven correctly with no edit here."""
    if face in PHASELESS_LANES:
        return _lane_argv(lane=face, project_id=project_id)
    return _phase_argv(phase=face, project_id=project_id)


def _generate_envelope(argv: list[str], *, description: str) -> str:
    """Generate a real dispatch envelope, asserting generation itself worked --
    so a generation failure never masquerades as a validation verdict."""
    exit_code, stdout, stderr = _run_dispatch(argv)
    assert exit_code == 0, (
        f"dispatch generation must succeed for {description} before its "
        f"envelope can be validated -- exit_code={exit_code}, stderr={stderr!r}"
    )
    assert stdout.strip(), (
        f"dispatch generation for {description} must emit a usable envelope -- "
        f"got empty stdout (stderr={stderr!r})"
    )
    return stdout


def _validate(envelope: str):
    """Feed a generated envelope through the REAL PreToolUse validator."""
    return AtddPurePromptValidator().validate_prompt(envelope)


def _replace_design_context_body(envelope: str, new_body: str) -> str:
    """Return `envelope` with its DESIGN_CONTEXT body swapped for `new_body`.

    Used ONLY by the stripped-citation negative legs, and the replacement text
    is harvested LIVE from a real non-code-facing envelope -- so the "stripped"
    case is built from the generator's own output, never hand-written prose.
    """
    heading = "# DESIGN_CONTEXT"
    start = envelope.find(heading)
    assert start != -1, (
        "fixture problem: the envelope carries no '# DESIGN_CONTEXT' heading, "
        "so there is no citation to strip -- this leg would be vacuous"
    )
    body_start = start + len(heading)
    old_body = _extract_section_body(envelope, "DESIGN_CONTEXT")
    return envelope[:body_start] + new_body + envelope[body_start + len(old_body) :]


def _citation_free_body() -> str:
    """The citation-free DESIGN_CONTEXT body the generator itself writes for a
    non-code-facing dispatch, harvested LIVE from a real charter-lane envelope
    (the face that is ALREADY exempt today, so this harvest is stable both
    before and after the fix)."""
    envelope = _generate_envelope(
        _lane_argv(lane="charter", project_id="probe-harvest-citation-free"),
        description="charter lane (citation-free body harvest)",
    )
    body = _extract_section_body(envelope, "DESIGN_CONTEXT")
    assert body.strip(), "fixture problem: harvested DESIGN_CONTEXT body is empty"
    assert not design_context_carries_architecture(body), (
        "fixture problem: the harvested body must be citation-FREE, else the "
        f"stripped-citation legs are vacuous -- got body={body!r}"
    )
    return body


# ---------------------------------------------------------------------------
# Vacuity witnesses -- prove the two derivations did not silently collapse.
# Floors only: they can NEVER narrow coverage, only fail loudly on collapse.
# ---------------------------------------------------------------------------


def test_derived_non_code_facing_face_set_is_not_vacuous() -> None:
    """The non-code-facing face matrix is DERIVED from the generator's live
    ``_PHASE_AGENTS`` x ``_NON_CODE_FACING_AGENTS`` maps unioned with the
    domain ``PHASELESS_LANES`` SSOT. If that derivation ever returned the empty
    set (a renamed map, a moved constant), every parametrized leg below would
    pass VACUOUSLY. This floor makes that collapse fail loudly by name.

    Deliberately a FLOOR (subset assertion), never an equality: a future phase
    routed to a non-code-facing agent must widen coverage automatically, with
    no edit here.
    """
    # covers: fix-validator-refuses-own-generated-dispatch
    missing = _NON_CODE_FACING_FLOOR - set(_NON_CODE_FACING_FACES)
    assert not missing, (
        f"the derived non-code-facing face matrix is missing {sorted(missing)!r} "
        "-- the derivation from dispatch._PHASE_AGENTS / "
        "dispatch._NON_CODE_FACING_AGENTS / PHASELESS_LANES has collapsed or "
        f"drifted. Derived faces were {_NON_CODE_FACING_FACES!r}. Without "
        "these faces every round-trip leg in this file passes vacuously."
    )


def test_derived_code_facing_phase_set_is_not_vacuous() -> None:
    """Symmetric floor for the OTHER derived axis: the code-facing phases whose
    DESIGN_CONTEXT citation must stay MANDATORY. If this collapsed, the
    anti-toothless legs (a stripped citation is still refused) would pass
    vacuously and the fix could disarm the gate wholesale unnoticed.
    """
    # covers: fix-validator-refuses-own-generated-dispatch
    floor = {"A_GREEN", "D_REFACTOR_COMMIT"}
    missing = floor - set(_CODE_FACING_PHASES)
    assert not missing, (
        f"the derived code-facing phase set is missing {sorted(missing)!r} -- "
        f"derived phases were {_CODE_FACING_PHASES!r}. Without them the "
        "gate-still-bites legs in this file pass vacuously."
    )
    overlap = set(_CODE_FACING_PHASES) & set(_NON_CODE_FACING_FACES)
    assert not overlap, (
        f"phases {sorted(overlap)!r} are derived as BOTH code-facing and "
        "non-code-facing -- the two derivations contradict each other, so "
        "neither axis can be trusted."
    )


# ---------------------------------------------------------------------------
# THE BUG -- round-trip acceptance of every derived non-code-facing face.
# RED today for FEATURE_END_EXAMINE; GREEN for C_REVIEWER_AUDIT and charter.
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("face", _NON_CODE_FACING_FACES)
def test_generated_non_code_facing_dispatch_is_accepted_by_validator(
    face: str,
) -> None:
    """ROUND-TRIP: the REAL generator's output for EVERY derived non-code-facing
    dispatch face must be ACCEPTED by the REAL PreToolUse validator.

    The system must never refuse its own generator's output. The faces are
    derived from the live generator maps, so a future phase routed to a
    non-code-facing agent is covered here automatically.

    RED today for ``FEATURE_END_EXAMINE`` -- the validator's exemption
    predicate hardcodes the single literal ``"C_REVIEWER_AUDIT"``.
    """
    # covers: fix-validator-refuses-own-generated-dispatch
    envelope = _generate_envelope(
        _face_argv(face=face, project_id=f"probe-face-{face.lower()}"),
        description=f"non-code-facing face {face!r}",
    )
    result = _validate(envelope)

    assert result.status == "PASSED", (
        f"the validator REFUSED the generator's OWN output for the "
        f"non-code-facing dispatch face {face!r} -- the system refuses a "
        "dispatch it just produced. This face routes to a non-code-facing "
        "agent (dispatch._NON_CODE_FACING_AGENTS) whose DESIGN_CONTEXT is "
        "citation-free BY CONSTRUCTION, so the DESIGN_CONTEXT content gate "
        "must exempt it. status="
        f"{result.status}, errors={result.errors!r}, "
        f"recovery_guidance={result.recovery_guidance!r}"
    )
    assert result.task_invocation_allowed, (
        f"a non-code-facing dispatch ({face!r}) the generator produced must be "
        "invocable -- task_invocation_allowed was False with "
        f"errors={result.errors!r}"
    )
    assert _CITATION_REFUSAL not in result.errors, (
        f"the citation refusal must not fire for the non-code-facing face "
        f"{face!r} -- got errors={result.errors!r}"
    )


@pytest.mark.parametrize("phase", sorted(dispatch._canonical_phase_values()))
def test_generated_dispatch_is_accepted_by_validator_for_every_phase(
    phase: str,
) -> None:
    """ROUND-TRIP over EVERY generable phase, sourced from the production SSOT
    ``dispatch._canonical_phase_values()`` (the SAME set argparse's ``--phase``
    choices resolve from). Whatever the generator can emit, the validator must
    accept: generator and validator are two readers of one contract.

    RED today for the ``FEATURE_END_EXAMINE`` row ONLY; the other five rows are
    already GREEN and must stay GREEN (no-overcorrection).
    """
    # covers: fix-validator-refuses-own-generated-dispatch
    envelope = _generate_envelope(
        _phase_argv(phase=phase, project_id=f"probe-phase-{phase.lower()}"),
        description=f"phase {phase!r}",
    )
    result = _validate(envelope)

    assert result.status == "PASSED", (
        f"`des dispatch --phase {phase}` produced an envelope its own "
        f"PreToolUse validator REFUSES. status={result.status}, "
        f"errors={result.errors!r}, recovery_guidance="
        f"{result.recovery_guidance!r}"
    )


# ---------------------------------------------------------------------------
# ANTI-TOOTHLESS legs -- the gate must still BITE after the fix.
# ---------------------------------------------------------------------------


@pytest.mark.negative_at
@pytest.mark.parametrize("phase", _CODE_FACING_PHASES)
def test_code_facing_dispatch_stripped_of_its_citation_is_still_refused(
    phase: str,
) -> None:
    """NEGATIVE AT (the gate must still bite): a CODE-FACING dispatch whose
    DESIGN_CONTEXT citation has been stripped must STILL be REFUSED with the
    same citation error.

    Both sides are built from the generator's OWN output -- the case is a real
    code-facing envelope, and the citation-free replacement body is harvested
    live from a real non-code-facing envelope. No hand-written prompt.

    This is what stops the fix being bought by disarming the DESIGN_CONTEXT
    content gate wholesale, or by keying the exemption on the BODY TEXT (which
    would exempt any code-facing dispatch that simply omitted its citation)
    instead of on the dispatch FACE. GREEN today; must stay GREEN.
    """
    # covers: fix-validator-refuses-own-generated-dispatch
    pristine = _generate_envelope(
        _phase_argv(phase=phase, project_id=f"probe-strip-{phase.lower()}"),
        description=f"code-facing phase {phase!r}",
    )
    pristine_body = _extract_section_body(pristine, "DESIGN_CONTEXT")
    assert design_context_carries_architecture(pristine_body), (
        f"fixture problem: the pristine {phase!r} envelope must carry a real "
        "citation for the strip to mean anything -- got body="
        f"{pristine_body!r}"
    )
    assert _validate(pristine).status == "PASSED", (
        f"fixture problem: the pristine {phase!r} envelope must be accepted "
        "before its stripped twin's refusal is meaningful"
    )

    stripped = _replace_design_context_body(pristine, _citation_free_body())
    result = _validate(stripped)

    assert result.status == "FAILED", (
        f"NEGATIVE AT: a CODE-FACING dispatch ({phase!r}) stripped of its "
        "DESIGN_CONTEXT citation must STILL be refused -- the gate has gone "
        "toothless. Exempting the examiner must never exempt the crafter. "
        f"status={result.status}, errors={result.errors!r}"
    )
    assert _CITATION_REFUSAL in result.errors, (
        f"the stripped code-facing dispatch ({phase!r}) must be refused with "
        f"the SAME citation error {_CITATION_REFUSAL!r} -- got "
        f"errors={result.errors!r}"
    )
    assert not result.task_invocation_allowed, (
        f"a code-facing dispatch ({phase!r}) with no design citation must not "
        "be invocable"
    )


@pytest.mark.negative_at
@pytest.mark.parametrize("face", _NON_CODE_FACING_FACES)
def test_accepted_non_code_facing_envelope_carries_no_design_citation(
    face: str,
) -> None:
    """NEGATIVE AT (uncontaminated envelope): the non-code-facing envelope the
    validator accepts must carry NO design/architecture citation.

    Acceptance must be bought by FIXING THE CHECK, never by feeding the
    examiner the design information her spec forbids her by construction. If a
    future "fix" made ``des dispatch --phase FEATURE_END_EXAMINE`` emit a real
    ``Design reference: docs/feature/.../feature-delta.md``, the round-trip leg
    above would go green while destroying the examiner's entire epistemic value
    -- this leg refuses that trade. GREEN today; must stay GREEN.
    """
    # covers: fix-validator-refuses-own-generated-dispatch
    envelope = _generate_envelope(
        _face_argv(face=face, project_id=f"probe-clean-{face.lower()}"),
        description=f"non-code-facing face {face!r}",
    )
    body = _extract_section_body(envelope, "DESIGN_CONTEXT")

    assert body.strip(), (
        f"the non-code-facing envelope ({face!r}) must still carry an explicit "
        "DESIGN_CONTEXT body stating WHY there is no citation -- an empty body "
        "is indistinguishable from a forgotten one"
    )
    assert not design_context_carries_architecture(body), (
        f"NEGATIVE AT: the accepted non-code-facing envelope ({face!r}) must "
        "carry NO architecture citation -- acceptance must come from fixing "
        "the validator's face recognition, NOT from handing a non-code-facing "
        "agent the design/source access her spec forbids by construction. "
        f"DESIGN_CONTEXT body={body!r}"
    )
