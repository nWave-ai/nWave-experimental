"""RC4-a: the atdd_pure dispatch validator requires sections PROPORTIONAL to role.

Root cause (docs/feedback/des-spine-ceremony-cost-attack-plan.md, RC4 dispatch facet):
``ATDD_PURE_MANDATORY_SECTIONS`` is a FLAT 12-section tuple required for EVERY
atdd_pure-marked dispatch, BLIND to the dispatch role. A read-only REVIEW dispatch
(C_REVIEWER_AUDIT / feature-end review) writes no code, runs no TDD phases, appends no
ledger records and runs no terminating suite — yet it is forced to carry
ATDD_PURE_PHASES + QUALITY_GATES + AT_COMPLETION_LEDGER + RECORDING_INTEGRITY +
TERMINATING_RUN, which are empty ceremony for a review. That is the "useless ceremony"
(Ale 2026-06-26: "valore quando serve un processo rigoroso, niente cerimonie inutili").

Cure (Option A): the required-section set is keyed on the dispatch's ``DES-PHASE``
marker. IMPLEMENTATION phases (A_GREEN / D_REFACTOR_COMMIT) keep the full 12 (rigor
where code is written). REVIEW phases (C_REVIEWER_AUDIT and the feature-end review
phase) require only the 7-section CONTEXT/IDENTITY/BOUNDARY profile — the 5
implementation-contract sections are dropped. The hook recognition substrate is the
MARKERS, not the prose sections, so this changes ceremony WITHOUT touching recognition.

A prompt with NO phase marker keeps the full 12 (fail-closed default — an unclassified
dispatch is treated as implementation, never silently downgraded).
"""

from __future__ import annotations

from des.application.atdd_pure_prompt_validator import (
    ATDD_PURE_MANDATORY_SECTIONS,
    AtddPurePromptValidator,
)


# The 5 implementation-contract sections a read-only review does not need.
_IMPLEMENTATION_ONLY_SECTIONS = (
    "ATDD_PURE_PHASES",
    "QUALITY_GATES",
    "AT_COMPLETION_LEDGER",
    "RECORDING_INTEGRITY",
    "TERMINATING_RUN",
)

# The 7-section light REVIEW profile (the full set minus the implementation-only 5).
_REVIEW_PROFILE_SECTIONS = tuple(
    s for s in ATDD_PURE_MANDATORY_SECTIONS if s not in _IMPLEMENTATION_ONLY_SECTIONS
)


def _section_block(section: str) -> str:
    """A minimal valid body for ``# {section}``.

    DESIGN_CONTEXT must carry a real architecture citation (the content gate at
    design_context_carries_architecture) — cite ADR-027 so the body is non-vacuous.
    """
    if section == "DESIGN_CONTEXT":
        return (
            "# DESIGN_CONTEXT\nReviewed against ADR-027 and "
            "docs/feature/x/feature-delta.md (the design the work follows).\n"
        )
    return f"# {section}\nbody for {section}.\n"


def _build_prompt(phase: str | None, sections: tuple[str, ...]) -> str:
    """Build a dispatch prompt carrying an optional DES-PHASE marker + section set."""
    parts: list[str] = ["<!-- DES-VALIDATION : required -->"]
    parts.append("<!-- DES-MODE : atdd_pure -->")
    if phase is not None:
        parts.append(f"<!-- DES-PHASE : {phase} -->")
    parts.append("<!-- DES-SLICE : slice-01 -->")
    parts.extend(_section_block(s) for s in sections)
    return "\n".join(parts)


def _validate(prompt: str):
    return AtddPurePromptValidator().validate_prompt(prompt)


def test_review_phase_allows_light_profile_without_implementation_sections() -> None:
    """A C_REVIEWER_AUDIT dispatch with only the 7 review sections is ALLOWED."""
    prompt = _build_prompt("C_REVIEWER_AUDIT", _REVIEW_PROFILE_SECTIONS)
    result = _validate(prompt)
    assert result.task_invocation_allowed, (
        "a review-phase (C_REVIEWER_AUDIT) dispatch must be allowed with only the "
        "7-section review profile — the 5 implementation-contract sections "
        f"{_IMPLEMENTATION_ONLY_SECTIONS} are empty ceremony for a read-only review. "
        f"errors={result.errors}"
    )


def test_feature_end_review_phase_allows_light_profile() -> None:
    """The feature-end review phase (F_FINAL_REVIEW) also gets the light profile."""
    prompt = _build_prompt("F_FINAL_REVIEW", _REVIEW_PROFILE_SECTIONS)
    result = _validate(prompt)
    assert result.task_invocation_allowed, (
        "the feature-end review phase must get the light review profile too "
        f"(read-only adversarial review). errors={result.errors}"
    )


def test_implementation_phase_still_requires_full_template() -> None:
    """An A_GREEN dispatch missing the implementation-contract sections is REFUSED."""
    prompt = _build_prompt("A_GREEN", _REVIEW_PROFILE_SECTIONS)
    result = _validate(prompt)
    assert not result.task_invocation_allowed, (
        "an implementation-phase (A_GREEN) dispatch must STILL require the full "
        "12-section template — rigor where code is written is preserved. Missing the "
        f"5 implementation sections {_IMPLEMENTATION_ONLY_SECTIONS} must FAIL."
    )
    missing = " ".join(result.errors)
    assert any(s in missing for s in _IMPLEMENTATION_ONLY_SECTIONS), (
        "the A_GREEN refusal must name the missing implementation sections. "
        f"errors={result.errors}"
    )


def test_d_refactor_commit_phase_requires_full_template() -> None:
    """D_REFACTOR_COMMIT (the refactor+commit implementation phase) keeps full rigor."""
    prompt = _build_prompt("D_REFACTOR_COMMIT", _REVIEW_PROFILE_SECTIONS)
    result = _validate(prompt)
    assert not result.task_invocation_allowed, (
        "D_REFACTOR_COMMIT writes code (refactor) — it must keep the full 12-section "
        f"template. errors={result.errors}"
    )


def test_review_phase_still_requires_its_own_context_sections() -> None:
    """The light profile is NOT a free pass: a review missing TASK_CONTEXT FAILS."""
    sections = tuple(s for s in _REVIEW_PROFILE_SECTIONS if s != "TASK_CONTEXT")
    prompt = _build_prompt("C_REVIEWER_AUDIT", sections)
    result = _validate(prompt)
    assert not result.task_invocation_allowed, (
        "a review dispatch missing a section IN its light profile (TASK_CONTEXT) "
        "must still FAIL — proportional ceremony, not zero ceremony. "
        f"errors={result.errors}"
    )
    assert any("TASK_CONTEXT" in e for e in result.errors)


def test_no_phase_marker_keeps_full_template_fail_closed() -> None:
    """No DES-PHASE marker → full 12 required (fail-closed default, no silent downgrade)."""
    prompt = _build_prompt(None, _REVIEW_PROFILE_SECTIONS)
    result = _validate(prompt)
    assert not result.task_invocation_allowed, (
        "a dispatch with NO DES-PHASE marker must keep the full 12-section "
        "requirement — an unclassified dispatch is treated as implementation, never "
        f"silently downgraded to the light profile. errors={result.errors}"
    )


def test_full_implementation_template_still_passes() -> None:
    """Regression-lock: a full 12-section A_GREEN dispatch still PASSES unchanged."""
    prompt = _build_prompt("A_GREEN", ATDD_PURE_MANDATORY_SECTIONS)
    result = _validate(prompt)
    assert result.task_invocation_allowed, (
        f"the full 12-section implementation template must stay valid. "
        f"errors={result.errors}"
    )
