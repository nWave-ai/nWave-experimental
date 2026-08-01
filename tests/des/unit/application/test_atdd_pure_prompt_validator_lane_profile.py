# @feature-f-prefactoring-dispatch-clears-honestly
# @slice-01
"""slice-01 ATs -- the section validator consults LANE_PROFILES, never branches.

Feature `f-prefactoring-dispatch-clears-honestly` (epic
`non-slice-dispatch-exemption-model`, row 1 keystone, walking skeleton).
Mirrors the RC4-a review-profile precedent
(`test_atdd_pure_prompt_validator_role_profiles.py`) -- same driving port
(`AtddPurePromptValidator.validate_prompt`, a `ValidatorPort` implementation),
generalized from a phase-marker profile to a lane-marker DATUM LOOKUP.

Design reference: `docs/feature/f-prefactoring-dispatch-clears-honestly/
feature-delta.md` (`Wave: DESIGN / [REF] Per-Locus Consulting Mechanism`,
slice-01 code block) -- `_required_sections` gains a `<!-- DES-LANE : X -->`
marker lookup: `LANE_PROFILES.get(X)` -> `profile.required_sections`, a
datum consultation, not a hardcoded `if lane == "prefactoring"` branch.

Active-RED: `_required_sections` today has no DES-LANE handling at all, so
every scenario below that depends on the lane-marker being honored fails --
the validator falls through to the full 12-section
`ATDD_PURE_MANDATORY_SECTIONS` regardless of what the prompt's lane marker or
the (currently empty) `LANE_PROFILES` datum says.

AT-3 (the required_sections drift-guard) is folded in HERE, not in a separate
`tests/des/unit/domain/*` file -- per Sentinel's (nw-acceptance-designer-
reviewer) Mandate-13 (no-direct-domain-testing) finding: of `LaneProfile`'s 7
fields, only `required_sections` has a driving-port consumer in slice-01 (this
validator); the drift-guard is relocated behind that SAME port instead of
asserting domain-object shape with no port between. The other fields
(`guard_kind` / `at_requirement` / `feature_readiness` / `annotation_token` /
`skipped_invariants`) are deferred to slice-02 (readiness-gate AT) and
slice-03 (carpaccio-gate AT) -- their real consuming entry points.
"""

from __future__ import annotations

import pytest

from des.application import atdd_pure_prompt_validator
from des.application.atdd_pure_prompt_validator import (
    ATDD_PURE_MANDATORY_SECTIONS,
    AtddPurePromptValidator,
)
from des.domain.expectation_charter_mapping import CharterObligation
from des.domain.lane_profile import AtRequirement, GuardKind, LaneProfile


def _section_block(section: str) -> str:
    """A minimal valid body for ``# {section}`` (mirrors the RC4-a helper)."""
    if section == "DESIGN_CONTEXT":
        return (
            "# DESIGN_CONTEXT\nReviewed against ADR-027 and "
            "docs/feature/x/feature-delta.md (the design the work follows).\n"
        )
    return f"# {section}\nbody for {section}.\n"


def _build_prompt(lane: str | None, sections: tuple[str, ...]) -> str:
    """Build a dispatch prompt carrying an optional DES-LANE marker + sections."""
    parts: list[str] = [
        "<!-- DES-VALIDATION : required -->",
        "<!-- DES-MODE : atdd_pure -->",
    ]
    if lane is not None:
        parts.append(f"<!-- DES-LANE : {lane} -->")
    parts.append("<!-- DES-SLICE : slice-01 -->")
    parts.extend(_section_block(s) for s in sections)
    return "\n".join(parts)


def _validate(prompt: str):
    return AtddPurePromptValidator().validate_prompt(prompt)


# AT-2 (positive) -----------------------------------------------------------


def test_prefactoring_lane_marker_with_datum_sections_is_accepted() -> None:
    """A dispatch carrying `DES-LANE: prefactoring` + exactly the DATUM's
    `required_sections` (10, not 12) is ACCEPTED -- the profile's OWN
    section list is read from `LANE_PROFILES`, not hardcoded in this test, so
    this fails identically whether the datum or the consulting branch is
    still missing.
    """
    from des.domain.lane_profile import LANE_PROFILES

    assert "prefactoring" in LANE_PROFILES, (
        "LANE_PROFILES['prefactoring'] must exist before the validator can "
        "consult it (RED scaffold: registry currently empty)."
    )
    sections = LANE_PROFILES["prefactoring"].required_sections
    prompt = _build_prompt("prefactoring", sections)

    result = _validate(prompt)
    assert result.task_invocation_allowed, (
        "a DES-LANE: prefactoring dispatch carrying exactly the datum's "
        f"required_sections ({sections}) must be ACCEPTED -- the 2 omitted "
        "AT-recording sections (AT_COMPLETION_LEDGER, RECORDING_INTEGRITY) "
        f"must NOT be demanded. errors={result.errors}"
    )


def test_prefactoring_lane_marker_missing_a_datum_required_section_is_rejected() -> (
    None
):
    """The profile's OWN required set is still enforced -- omitting ONE of the
    10 datum-required sections must FAIL, naming it."""
    from des.domain.lane_profile import LANE_PROFILES

    assert "prefactoring" in LANE_PROFILES, (
        "LANE_PROFILES['prefactoring'] must exist before this omission check can run."
    )
    sections = tuple(
        s
        for s in LANE_PROFILES["prefactoring"].required_sections
        if s != "BOUNDARY_RULES"
    )
    prompt = _build_prompt("prefactoring", sections)

    result = _validate(prompt)
    assert not result.task_invocation_allowed, (
        "a prefactoring dispatch missing a section the DATUM requires "
        "(BOUNDARY_RULES) must be REJECTED -- proportional ceremony, not a "
        "free pass."
    )
    assert any("BOUNDARY_RULES" in e for e in result.errors), (
        f"the rejection must name the missing section. errors={result.errors}"
    )


def test_validator_consults_the_datum_at_call_time_not_a_hardcoded_branch() -> None:
    """AT-2's structural claim: the validator LOOKS UP `LANE_PROFILES` at
    call time -- it does not cache/hardcode "prefactoring"'s section list
    independently. Proven by substituting the datum entry the validator
    consults and observing the decision follow the SUBSTITUTED shape, not a
    baked-in one.

    `raising=False`: pre-GREEN, `des.application.atdd_pure_prompt_validator`
    does not import `LANE_PROFILES` at all yet -- the monkeypatch is a no-op
    then, which is the correct RED (nothing to consult -> falls through to
    the full 12, contradicting this test's 3-section expectation).
    """
    custom_profiles = {
        "prefactoring": LaneProfile(
            lane_id="prefactoring",
            required_sections=("DES_METADATA", "AGENT_IDENTITY", "TASK_CONTEXT"),
            guard_kind=GuardKind.GREEN_TO_GREEN,
            feature_readiness=False,
            at_requirement=AtRequirement.EXEMPT,
            skipped_invariants=(),
            annotation_token="prefactoring",
            charter_obligation=CharterObligation.EXEMPT,
        )
    }

    mp = pytest.MonkeyPatch()
    try:
        mp.setattr(
            atdd_pure_prompt_validator, "LANE_PROFILES", custom_profiles, raising=False
        )
        prompt = _build_prompt(
            "prefactoring", ("DES_METADATA", "AGENT_IDENTITY", "TASK_CONTEXT")
        )
        result = _validate(prompt)
    finally:
        mp.undo()

    assert result.task_invocation_allowed, (
        "the validator must read `required_sections` from `LANE_PROFILES` at "
        "call time -- with the datum entry substituted to a 3-section "
        "profile, a prompt carrying exactly those 3 sections must be "
        "ACCEPTED. A hardcoded 'prefactoring' branch (ignoring the datum "
        f"substitution) would still demand the real 10/12. errors={result.errors}"
    )


# AT-3 (REQUIRED drift-guard, relocated here per Mandate 13) -----------------


def test_prefactoring_required_sections_tracks_mandatory_sections_via_validator() -> (
    None
):
    """AT-3 (REQUIRED drift-guard, promoted from DESIGN Open Questions by the
    solution-architect-reviewer MEDIUM finding). Relocated from a direct
    `tests/des/unit/domain/*` import-equality assertion (Sentinel/nw-
    acceptance-designer-reviewer Mandate-13 finding: no-direct-domain-testing)
    onto THIS driving port -- the section validator is the only production
    consumer of `LaneProfile.required_sections` in slice-01, so the drift
    guard now runs behind it instead of asserting domain-object shape with no
    port between.

    `required_sections` for "prefactoring" is a LITERAL tuple in
    `lane_profile.py` (D2: domain must not import the application-layer
    `ATDD_PURE_MANDATORY_SECTIONS` to derive it) -- this is the ONLY safety
    net guarding that literal choice. The oracle below compares the LIVE
    computed set against the datum's OWN set and demands the validator's
    accept/reject decision track that equality: a prompt built from exactly
    the live-computed set is ACCEPTED only while the two stay in sync. If a
    NEW mandatory section is later added upstream without updating the
    prefactoring literal, the datum ends up a proper subset of the live set
    -- the validator (subset-checking) would still ACCEPT such a prompt, but
    the oracle now expects REJECT (sets differ), so the mismatch REDs.
    """
    from des.domain.lane_profile import LANE_PROFILES

    assert "prefactoring" in LANE_PROFILES, (
        "LANE_PROFILES['prefactoring'] must exist before its drift-guard can run "
        "(RED scaffold: registry currently empty)."
    )
    datum_sections = LANE_PROFILES["prefactoring"].required_sections
    live_expected = tuple(
        s
        for s in ATDD_PURE_MANDATORY_SECTIONS
        if s not in {"AT_COMPLETION_LEDGER", "RECORDING_INTEGRITY"}
    )

    prompt = _build_prompt("prefactoring", live_expected)
    result = _validate(prompt)

    in_sync = datum_sections == live_expected
    assert result.task_invocation_allowed == in_sync, (
        "DRIFT DETECTED: LANE_PROFILES['prefactoring'].required_sections "
        f"({datum_sections!r}) vs the live-computed ATDD_PURE_MANDATORY_SECTIONS "
        f"minus the AT-recording omissions ({live_expected!r}) -- "
        f"in_sync={in_sync} but the validator "
        f"{'accepted' if result.task_invocation_allowed else 'rejected'} a prompt "
        "carrying exactly the live-computed set. Fix lane_profile.py's literal "
        f"tuple to restore parity. errors={result.errors}"
    )


# AT-4 (negative -- no leak) --------------------------------------------------


@pytest.mark.parametrize(
    "lane",
    [
        pytest.param(None, id="no-lane-marker-at-all"),
        pytest.param("unknown-lane", id="unrecognized-lane-id"),
        pytest.param(
            "nonexistent-lane", id="a-lane-id-genuinely-absent-from-LANE_PROFILES"
        ),
    ],
)
def test_absent_or_unknown_lane_keeps_full_template_no_leak(lane: str | None) -> None:
    """AT-4 (KPI-2 guardrail): a dispatch with no lane marker, or a lane the
    datum has no entry for, gets the FULL 12-section requirement --
    byte-identical to today. The exemption must never leak into the ordinary
    path via a missing/unknown lookup.

    NOTE (des-dispatch-ssot-renderer Fase-1 blast-radius fix): this
    parametrize set previously included ``"bugfix"`` as its "recognized lane
    not yet in LANE_PROFILES" example. Fase-1 POPULATES `LANE_PROFILES["bugfix"]`
    (see AT-5..AT-8 below), so `"bugfix"` is no longer a genuinely-unknown lane
    -- keeping it here would have silently degraded this case into a
    coincidental-full-12-count assertion (bugfix's own required_sections
    happens to equal the full 12) rather than a real unknown-lane exercise.
    Replaced with `"nonexistent-lane"`, a lane id with no LANE_PROFILES entry
    now or ever.
    """
    from des.domain.lane_profile import LANE_PROFILES

    prompt = _build_prompt(lane, ATDD_PURE_MANDATORY_SECTIONS[:-1])  # omit last section

    result = _validate(prompt)
    assert not result.task_invocation_allowed, (
        f"lane={lane!r} (LANE_PROFILES.get({lane!r}) -> "
        f"{LANE_PROFILES.get(lane) if lane else None}) must NOT exempt any "
        "section -- an unrecognized/absent lane keeps the full 12 required, "
        f"never the lighter prefactoring profile. errors={result.errors}"
    )
    assert any(ATDD_PURE_MANDATORY_SECTIONS[-1] in e for e in result.errors)


def test_full_prefactoring_datum_profile_is_the_only_thing_exempted() -> None:
    """Regression-lock: an ordinary full-12-section dispatch with NO lane
    marker still passes unchanged (mirrors RC4-a's own regression-lock)."""
    prompt = _build_prompt(None, ATDD_PURE_MANDATORY_SECTIONS)
    result = _validate(prompt)
    assert result.task_invocation_allowed, (
        f"the full 12-section template with no lane marker must still pass "
        f"unchanged. errors={result.errors}"
    )


# AT-5..AT-8 (des-dispatch-ssot-renderer Fase-1 -- bugfix lane RECOGNIZED) ---
#
# Design: docs/feature/des-dispatch-ssot-renderer/design/dispatch-ssot-design.md
# Open Review Point B (bugfix section set = full-12, RED_TO_GREEN guard,
# readiness requires lane_justification -- CONFIRMED). Behavior-preserving on
# section COUNT (bugfix's required set IS the full 12, same as today's
# unknown-lane fall-through) but NOW an explicit datum entry the validator
# CONSULTS, not a coincidental fall-through. Scope note (Mandate 13,
# no-direct-domain-testing): only `required_sections` has a driving-port
# consumer at this Fase-1 layer -- `verify_readiness_pre_dispatch.py` keeps
# its OWN pre-existing hardcoded `_BUGFIX_LANE` branch (checked BEFORE it
# ever consults `LANE_PROFILES`) and `carpaccio_format.py`'s lane lookup only
# fires on an `@prefactoring` slice-plan annotation -- so `LANE_PROFILES
# ["bugfix"].guard_kind` / `.at_requirement` / `.skipped_invariants` have NO
# consuming entry point yet. Those fields are deferred to a future slice that
# converges the readiness gate onto the datum (out of Fase-1 scope); this
# file's AT-3 precedent (folding the domain drift-guard behind the ONE real
# consumer) is followed identically for bugfix.


def test_bugfix_lane_marker_with_datum_sections_is_accepted() -> None:
    """A dispatch carrying `DES-LANE: bugfix` + exactly the DATUM's
    `required_sections` is ACCEPTED. Read from `LANE_PROFILES` (never a
    literal duplicated in this test), so this fails identically whether the
    datum entry or the consulting branch is still missing.
    """
    from des.domain.lane_profile import LANE_PROFILES

    assert "bugfix" in LANE_PROFILES, (
        "LANE_PROFILES['bugfix'] must exist before the validator can consult "
        "it (RED scaffold: the bugfix row is not populated yet)."
    )
    sections = LANE_PROFILES["bugfix"].required_sections
    prompt = _build_prompt("bugfix", sections)

    result = _validate(prompt)
    assert result.task_invocation_allowed, (
        "a DES-LANE: bugfix dispatch carrying exactly the datum's "
        f"required_sections ({sections}) must be ACCEPTED. errors={result.errors}"
    )


def test_bugfix_lane_marker_missing_a_datum_required_section_is_rejected() -> None:
    """The bugfix profile's OWN required set is enforced -- omitting ONE of
    its required sections must FAIL, naming it. Bugfix writes code and
    records ATs, so (unlike prefactoring) it drops NOTHING from the full 12 --
    this proves the datum lookup is real, not a permissive no-op."""
    from des.domain.lane_profile import LANE_PROFILES

    assert "bugfix" in LANE_PROFILES, (
        "LANE_PROFILES['bugfix'] must exist before this omission check can run."
    )
    sections = tuple(
        s
        for s in LANE_PROFILES["bugfix"].required_sections
        if s != "RECORDING_INTEGRITY"
    )
    prompt = _build_prompt("bugfix", sections)

    result = _validate(prompt)
    assert not result.task_invocation_allowed, (
        "a bugfix dispatch missing a section the DATUM requires "
        "(RECORDING_INTEGRITY) must be REJECTED -- a bugfix writes code and "
        "records ATs, it does not get a lighter template."
    )
    assert any("RECORDING_INTEGRITY" in e for e in result.errors), (
        f"the rejection must name the missing section. errors={result.errors}"
    )


def test_bugfix_required_sections_equal_the_full_mandatory_set_via_validator() -> None:
    """AT-8 (drift-guard, mirrors AT-3 for the bugfix row): bugfix's
    `required_sections` is a LITERAL tuple in `lane_profile.py` (D2: the
    domain must not import the application-layer
    `ATDD_PURE_MANDATORY_SECTIONS` to derive it). Per the design (`sections:
    full-12`, `drop_sections: []`), bugfix drops NOTHING -- its required set
    must equal `ATDD_PURE_MANDATORY_SECTIONS` verbatim. The oracle compares
    the validator's accept/reject decision against that live-computed
    expectation: a prompt built from exactly `ATDD_PURE_MANDATORY_SECTIONS`
    is ACCEPTED only while the two stay in sync. If bugfix's literal ever
    narrows (a section silently dropped), the datum becomes a proper subset
    of the live set and this REDs.
    """
    from des.domain.lane_profile import LANE_PROFILES

    assert "bugfix" in LANE_PROFILES, (
        "LANE_PROFILES['bugfix'] must exist before its drift-guard can run "
        "(RED scaffold: the bugfix row is not populated yet)."
    )
    datum_sections = LANE_PROFILES["bugfix"].required_sections
    live_expected = ATDD_PURE_MANDATORY_SECTIONS

    prompt = _build_prompt("bugfix", live_expected)
    result = _validate(prompt)

    in_sync = datum_sections == live_expected
    assert result.task_invocation_allowed == in_sync, (
        "DRIFT DETECTED: LANE_PROFILES['bugfix'].required_sections "
        f"({datum_sections!r}) vs ATDD_PURE_MANDATORY_SECTIONS ({live_expected!r}) "
        f"-- in_sync={in_sync} but the validator "
        f"{'accepted' if result.task_invocation_allowed else 'rejected'} a prompt "
        "carrying exactly the live-computed set. Fix lane_profile.py's literal "
        f"tuple to restore parity. errors={result.errors}"
    )


def test_bugfix_and_prefactoring_lanes_both_resolve_via_the_same_datum_lookup() -> None:
    """No hardcoded 'if lane == \"bugfix\"' branch: substituting BOTH datum
    entries at once and observing BOTH decisions follow the substitution
    proves `_required_sections` consults `LANE_PROFILES.get(lane)` generically
    -- one lookup, two lanes, never a per-lane branch.
    """
    custom_profiles = {
        "prefactoring": LaneProfile(
            lane_id="prefactoring",
            required_sections=("DES_METADATA",),
            guard_kind=GuardKind.GREEN_TO_GREEN,
            feature_readiness=False,
            at_requirement=AtRequirement.EXEMPT,
            skipped_invariants=(),
            annotation_token="prefactoring",
            charter_obligation=CharterObligation.EXEMPT,
        ),
        "bugfix": LaneProfile(
            lane_id="bugfix",
            required_sections=("AGENT_IDENTITY", "TASK_CONTEXT"),
            guard_kind=GuardKind.RED_TO_GREEN,
            feature_readiness=True,
            at_requirement=AtRequirement.REQUIRED,
            skipped_invariants=(),
            annotation_token="bugfix",
            charter_obligation=CharterObligation.REQUIRED,
        ),
    }

    mp = pytest.MonkeyPatch()
    try:
        mp.setattr(
            atdd_pure_prompt_validator, "LANE_PROFILES", custom_profiles, raising=False
        )
        prefactoring_result = _validate(
            _build_prompt("prefactoring", ("DES_METADATA",))
        )
        bugfix_result = _validate(
            _build_prompt("bugfix", ("AGENT_IDENTITY", "TASK_CONTEXT"))
        )
    finally:
        mp.undo()

    assert prefactoring_result.task_invocation_allowed, (
        "substituted prefactoring profile (1 section) must be honored. "
        f"errors={prefactoring_result.errors}"
    )
    assert bugfix_result.task_invocation_allowed, (
        "substituted bugfix profile (2 sections) must be honored by the SAME "
        f"lookup mechanism. errors={bugfix_result.errors}"
    )
