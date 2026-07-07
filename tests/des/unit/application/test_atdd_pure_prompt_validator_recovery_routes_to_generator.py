"""The atdd_pure dispatch guard's recovery guidance ROUTES to the generator.

Charter: docs/product/expectations/fix-dispatch-guard-routes-to-generator/
the-dispatch-guard-tells-you-to-run-des-dispatch.md

DEFECT: when ``AtddPurePromptValidator.validate_prompt`` REJECTS an atdd_pure
dispatch missing a mandatory ``# SECTION``, its ``recovery_guidance`` today
names only the missing section (e.g. "Add TIMEOUT_INSTRUCTION section with
turn budget guidance") -- it never points at ``des dispatch``, the generator
command (`src/des/cli/dispatch.py`-family entry point) that PRODUCES a valid
dispatch by construction. This invites the exact hand-assembly ceremony the
generator exists to remove -- the standing principle this bug violates:
every gate's HOW-to-fix, where a system tool produces the checked artifact,
must INVOKE that tool, never instruct manual repair.

Driving port: the real ``AtddPurePromptValidator.validate_prompt`` (a
``ValidatorPort`` implementation) -- imported and called directly, no mock,
matching the established convention in this directory
(``test_atdd_pure_prompt_validator_role_profiles.py`` /
``test_atdd_pure_prompt_validator_lane_profile.py``).
"""

from __future__ import annotations

from des.application.atdd_pure_prompt_validator import (
    ATDD_PURE_MANDATORY_SECTIONS,
    AtddPurePromptValidator,
)


# The generator command the recovery guidance must route to (evolution-plan
# fix target). Any one of these flags proves the guidance names a concrete,
# runnable invocation -- not just the bare command name.
_GENERATOR_FLAGS = ("--mode", "--phase", "--slice")


def _section_block(section: str) -> str:
    """A minimal valid body for ``# {section}``.

    DESIGN_CONTEXT must carry a real architecture citation (the content gate
    at ``design_context_carries_architecture``) so a "complete" prompt is
    genuinely valid, not accidentally rejected on the content check.
    """
    if section == "DESIGN_CONTEXT":
        return (
            "# DESIGN_CONTEXT\nReviewed against ADR-027 and "
            "docs/feature/x/feature-delta.md (the design the work follows).\n"
        )
    return f"# {section}\nbody for {section}.\n"


def _build_prompt(sections: tuple[str, ...]) -> str:
    """Build an atdd_pure dispatch prompt carrying exactly ``sections``.

    No ``DES-PHASE`` marker -> the validator's fail-closed default applies:
    the full 12-section ``ATDD_PURE_MANDATORY_SECTIONS`` profile is required
    (see ``_required_sections`` in the production module), so this helper's
    "complete" prompt genuinely means complete, not merely complete-for-a-
    lighter profile.
    """
    parts: list[str] = [
        "<!-- DES-VALIDATION : required -->",
        "<!-- DES-MODE : atdd_pure -->",
        "<!-- DES-SLICE : slice-01 -->",
    ]
    parts.extend(_section_block(s) for s in sections)
    return "\n".join(parts)


def _validate(prompt: str):
    return AtddPurePromptValidator().validate_prompt(prompt)


# AT-1 (positive, active-RED today) ------------------------------------------


def test_missing_section_recovery_guidance_routes_to_des_dispatch_generator() -> None:
    """A dispatch missing a mandatory section (TIMEOUT_INSTRUCTION) is REJECTED
    (the check stays intact) AND its recovery guidance names the concrete
    generator invocation (`des dispatch` + a flag) that produces a valid
    dispatch by construction -- not just "add the missing section by hand".
    """
    sections = tuple(
        s for s in ATDD_PURE_MANDATORY_SECTIONS if s != "TIMEOUT_INSTRUCTION"
    )
    prompt = _build_prompt(sections)

    result = _validate(prompt)

    assert not result.task_invocation_allowed, (
        "the check must stay intact: a dispatch missing a mandatory section "
        f"must still be REJECTED. errors={result.errors}"
    )
    assert result.recovery_guidance is not None, (
        f"a rejection must carry recovery guidance -- got None. errors={result.errors}"
    )

    guidance_text = " ".join(result.recovery_guidance)

    assert "des dispatch" in guidance_text, (
        "recovery guidance must name the generator command `des dispatch` -- "
        "the tool that PRODUCES a valid atdd_pure dispatch by construction -- "
        "instead of only instructing manual repair ('add the missing section "
        f"X'). recovery_guidance={result.recovery_guidance!r}"
    )
    assert any(flag in guidance_text for flag in _GENERATOR_FLAGS), (
        "recovery guidance naming `des dispatch` must also name at least one "
        f"of its flags {_GENERATOR_FLAGS} so the invocation is concrete and "
        f"runnable, not a bare command name. "
        f"recovery_guidance={result.recovery_guidance!r}"
    )


# AT-2 (negative, green today, stays green after the fix) --------------------


def test_complete_dispatch_is_not_rejected_and_emits_no_generator_routing_message() -> (
    None
):
    """A COMPLETE atdd_pure dispatch (all 12 mandatory sections present) is
    NOT rejected, and the generator-routing guidance is NOT emitted spuriously
    -- no false steer on a dispatch that is already valid.
    """
    prompt = _build_prompt(ATDD_PURE_MANDATORY_SECTIONS)

    result = _validate(prompt)

    assert result.status == "PASSED", (
        f"a complete atdd_pure dispatch must PASS validation. "
        f"status={result.status} errors={result.errors}"
    )
    assert result.task_invocation_allowed is True, (
        "a complete atdd_pure dispatch must allow task invocation. "
        f"errors={result.errors}"
    )
    assert not result.errors, (
        f"a complete dispatch must carry zero errors. errors={result.errors}"
    )
    assert result.recovery_guidance is None, (
        "a complete, valid dispatch must not emit ANY recovery guidance -- "
        "in particular no spurious `des dispatch` generator-routing message. "
        f"recovery_guidance={result.recovery_guidance!r}"
    )
