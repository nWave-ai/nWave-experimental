"""AtddPurePromptValidator - mode-aware DES prompt validation for atdd_pure.

Transformation T-B (epic F-DES-ATDD-PURE-DISPATCH-LIFECYCLE, F-08 / G-2).

A sibling ``ValidatorPort`` implementation alongside the classic
``TemplateValidator`` (``validator.py``). It validates an ``atdd_pure``
carpaccio-slice dispatch prompt against the ``atdd_pure`` mandatory section
set — the A→G phase block and the AT-completion-ledger contract — NOT the
classic 9-section schema (which demands ``TDD_PHASES`` / ``OUTCOME_RECORDING``
execution-log sections an ``atdd_pure`` dispatch correctly omits).

CREATE NEW (not a ``MandatorySectionChecker`` subclass) is the DESIGN-table
boundary for T-B: the atdd_pure section *set* differs structurally and this
validator runs NO TDD-phase / execution-log validation. Contract shape:
**pure-function** (return-only) — ``prompt -> ValidationResult``, no I/O, no
mutation. ``ValidatorPort`` has no write method, so "validator silently
writes" is non-representable.
"""

from __future__ import annotations

import re
import time

from des.domain.atdd_pure_phases import FEATURE_END_RETURN_PHASE
from des.domain.design_context_content_check import (
    design_context_carries_architecture,
)
from des.domain.lane_profile import LANE_PROFILES
from des.ports.driver_ports.validator_port import ValidationResult, ValidatorPort


# The atdd_pure dispatch mandatory section set — matched verbatim to the T-A
# template in nWave/skills/nw-execute/SKILL.md (the
# ATDD-PURE-DISPATCH-TEMPLATE:BEGIN/:END block). Distinct from the classic
# 9-section set: ATDD_PURE_PHASES replaces TDD_PHASES, AT_COMPLETION_LEDGER
# replaces OUTCOME_RECORDING, plus SKILL_LOADING / DESIGN_CONTEXT /
# TERMINATING_RUN. No DES-STEP-ID, no execution-log sections.
ATDD_PURE_MANDATORY_SECTIONS: tuple[str, ...] = (
    "DES_METADATA",
    "AGENT_IDENTITY",
    "SKILL_LOADING",
    "TASK_CONTEXT",
    "DESIGN_CONTEXT",
    "ATDD_PURE_PHASES",
    "QUALITY_GATES",
    "AT_COMPLETION_LEDGER",
    "RECORDING_INTEGRITY",
    "BOUNDARY_RULES",
    "TERMINATING_RUN",
    "TIMEOUT_INSTRUCTION",
)

# --- RC4-a: required-section set keyed on dispatch ROLE -----------------------
# Root cause (docs/feedback/des-spine-ceremony-cost-attack-plan.md, RC4 dispatch
# facet): ATDD_PURE_MANDATORY_SECTIONS is a FLAT 12 required for EVERY atdd_pure
# dispatch, BLIND to role. A read-only REVIEW dispatch (slice reviewer-audit /
# feature-end deep review) writes no code, runs no TDD phases, appends no ledger
# records and runs no terminating suite — yet is forced to carry the 5
# implementation-contract sections, which are empty ceremony for a review.
#
# Cure (Option A): select the profile from the dispatch's DES-PHASE marker. The
# recognition substrate the hook keys on is the MARKERS (DES-MODE / DES-PHASE /
# DES-SLICE), NOT these prose sections — so dropping ceremony sections for a
# review changes the ceremony WITHOUT touching dispatch recognition.
#
# Key on the RAW marker string, NOT the normalised phase: F_FINAL_REVIEW
# normalises to D_REFACTOR_COMMIT for ROUTING, but as a dispatch ROLE it is the
# read-only feature-end review → light profile. Normalising before role-keying
# would wrongly hand the feature-end review the full implementation template.
_REVIEW_DISPATCH_PHASES: frozenset[str] = frozenset(
    {"C_REVIEWER_AUDIT", FEATURE_END_RETURN_PHASE}
)

# The 5 implementation-contract sections a read-only review does not need.
_IMPLEMENTATION_ONLY_SECTIONS: frozenset[str] = frozenset(
    {
        "ATDD_PURE_PHASES",
        "QUALITY_GATES",
        "AT_COMPLETION_LEDGER",
        "RECORDING_INTEGRITY",
        "TERMINATING_RUN",
    }
)

# The 7-section light REVIEW profile = the full set MINUS the implementation-only
# 5. DERIVED from ATDD_PURE_MANDATORY_SECTIONS (ADD-not-mutate: the full tuple
# stays the exported SSOT) so section order is preserved and the two never drift.
_REVIEW_PROFILE_SECTIONS: tuple[str, ...] = tuple(
    s for s in ATDD_PURE_MANDATORY_SECTIONS if s not in _IMPLEMENTATION_ONLY_SECTIONS
)

# Raw DES-PHASE marker (first match). Deliberately keys on the RAW declared phase
# string — see the role-vs-routing note above — keeping the validator a pure
# function with no I/O.
_DES_PHASE_MARKER = re.compile(r"<!--\s*DES-PHASE\s*:\s*(\S+)\s*-->")

# Raw DES-LANE marker (first match). A dispatch may declare a non-slice lane
# (``prefactoring`` today) whose ceremony profile is read from the LANE_PROFILES
# datum — the section validator CONSULTS the datum, it never hardcodes a lane
# branch, so substituting the datum substitutes the decision (the AT-2 structural
# guarantee).
_DES_LANE_MARKER = re.compile(r"<!--\s*DES-LANE\s*:\s*(\S+)\s*-->")


def _required_sections(prompt: str) -> tuple[str, ...]:
    """Select the required-section profile for ``prompt`` by its dispatch role.

    Reads the RAW ``<!-- DES-PHASE : X -->`` marker (first match, un-normalised):
      * a REVIEW phase (``C_REVIEWER_AUDIT`` / the feature-end review return
        phase ``F_FINAL_REVIEW``) → the 7-section light REVIEW profile;
      * else a recognized ``<!-- DES-LANE : X -->`` whose entry EXISTS in the
        LANE_PROFILES datum → that lane's ``required_sections`` (a datum lookup,
        never a hardcoded lane branch);
      * any other phase/lane, OR NO marker at all → the full 12 (fail-closed
        default: an unclassified or unknown-lane dispatch is treated as
        implementation, never silently downgraded to a lighter profile).
    """
    match = _DES_PHASE_MARKER.search(prompt)
    if match is not None and match.group(1) in _REVIEW_DISPATCH_PHASES:
        return _REVIEW_PROFILE_SECTIONS
    lane_match = _DES_LANE_MARKER.search(prompt)
    if lane_match is not None:
        profile = LANE_PROFILES.get(lane_match.group(1))
        if profile is not None:
            return profile.required_sections
    return ATDD_PURE_MANDATORY_SECTIONS


# The generator command that PRODUCES a valid atdd_pure dispatch by
# construction -- see docs/product/expectations/fix-dispatch-guard-routes-to-
# generator/the-dispatch-guard-tells-you-to-run-des-dispatch.md. A rejection's
# recovery guidance must route HERE first, never to manual section repair.
_GENERATOR_INVOCATION = (
    "des dispatch --mode atdd_pure --project-id <id> --slice <slice> "
    "--phase <phase> [--lane <lane>] --intent '<task>'"
)


def _generator_routed_guidance(missing_section_context: str) -> str:
    """Recovery guidance that ROUTES to the ``des dispatch`` generator.

    The primary remedy is never "hand-add the section" -- it is "regenerate
    via the tool that cannot omit a mandatory section". The specific
    missing-section name is kept as secondary context so nothing is lost.
    """
    return (
        f"Do not hand-add sections -- run `{_GENERATOR_INVOCATION}` to "
        "generate a valid atdd_pure dispatch by construction (this dispatch "
        f"is missing {missing_section_context})."
    )


_RECOVERY_GUIDANCE = {
    "DES_METADATA": _generator_routed_guidance(
        "DES_METADATA -- slice / feature / phase"
    ),
    "AGENT_IDENTITY": _generator_routed_guidance(
        "AGENT_IDENTITY -- the dispatched agent"
    ),
    "SKILL_LOADING": _generator_routed_guidance(
        "SKILL_LOADING -- the skills to load at phase entry"
    ),
    "TASK_CONTEXT": _generator_routed_guidance("TASK_CONTEXT -- the slice and its ATs"),
    "DESIGN_CONTEXT": _generator_routed_guidance(
        "DESIGN_CONTEXT -- relevant design decisions"
    ),
    "ATDD_PURE_PHASES": _generator_routed_guidance(
        "ATDD_PURE_PHASES -- the A-G ATDD-pure phases"
    ),
    "QUALITY_GATES": _generator_routed_guidance(
        "QUALITY_GATES -- the slice quality criteria"
    ),
    "AT_COMPLETION_LEDGER": _generator_routed_guidance(
        "AT_COMPLETION_LEDGER -- the ledger recording contract"
    ),
    "RECORDING_INTEGRITY": _generator_routed_guidance(
        "RECORDING_INTEGRITY -- anti-fraud rules for AT outcomes"
    ),
    "BOUNDARY_RULES": _generator_routed_guidance(
        "BOUNDARY_RULES -- the slice-scoped boundary"
    ),
    "TERMINATING_RUN": _generator_routed_guidance(
        "TERMINATING_RUN -- the terminating-test-run instruction"
    ),
    "TIMEOUT_INSTRUCTION": _generator_routed_guidance(
        "TIMEOUT_INSTRUCTION -- turn budget guidance"
    ),
}


def _extract_section_body(prompt: str, section: str) -> str:
    """Return the body of ``# {section}`` — text after its heading line up to
    the next ``# {SECTION}`` mandatory-section header (or end of prompt).

    The mandatory-section set is the SSOT for what counts as a "next header", so
    a ``#``-prefixed line *inside* a body (e.g. a comment or markdown) does not
    prematurely terminate the section. Returns "" when the heading is absent.
    """
    heading = f"# {section}"
    start = prompt.find(heading)
    if start == -1:
        return ""
    body_start = start + len(heading)
    next_headers = (
        f"# {other}" for other in ATDD_PURE_MANDATORY_SECTIONS if other != section
    )
    end = len(prompt)
    for header in next_headers:
        pos = prompt.find(header, body_start)
        if pos != -1 and pos < end:
            end = pos
    return prompt[body_start:end]


class AtddPurePromptValidator(ValidatorPort):
    """Validates an atdd_pure carpaccio-slice dispatch prompt.

    Pure-function ``ValidatorPort`` implementation: ``validate_prompt`` reads
    the prompt text and returns a ``ValidationResult``. No I/O, no mutation.
    """

    def validate_prompt(self, prompt: str) -> ValidationResult:
        """Validate an atdd_pure dispatch prompt against the atdd_pure schema.

        Args:
            prompt: The full dispatch prompt text.

        Returns:
            ValidationResult — ``task_invocation_allowed`` is True only when
            every atdd_pure mandatory section is present.
        """
        start_time = time.perf_counter()

        # RC4-a: iterate the ROLE-selected profile (review = 7, else full 12), so
        # a review dispatch is neither blocked on nor told to add the 5 dropped
        # implementation-contract sections.
        required_sections = _required_sections(prompt)

        errors = [
            f"MISSING: Mandatory section '{section}' not found"
            for section in required_sections
            if f"# {section}" not in prompt
        ]

        recovery_guidance = [
            f"FIX: {_RECOVERY_GUIDANCE[section]}"
            for section in required_sections
            if f"# {section}" not in prompt and section in _RECOVERY_GUIDANCE
        ]

        # DESIGN_CONTEXT content-presence gate (DDD-1, #63 INPUT-b). The header
        # check above proves the heading is present; this proves its BODY carries
        # a real architecture citation. A header with an empty/placeholder/
        # citation-free body is refused so the crafter never runs without the
        # design it must follow (the root of architectural drift).
        if "# DESIGN_CONTEXT" in prompt:
            body = _extract_section_body(prompt, "DESIGN_CONTEXT")
            if not design_context_carries_architecture(body):
                errors.append(
                    "DESIGN_CONTEXT carries no architecture citation "
                    "(empty, placeholder, or citation-free body)"
                )
                recovery_guidance.append(
                    "FIX: Cite a real design artifact in DESIGN_CONTEXT "
                    "(a DDD / ADR / SYS id, a feature-delta.md path, or brief.md)"
                )

        duration_ms = (time.perf_counter() - start_time) * 1000

        return ValidationResult(
            status="PASSED" if not errors else "FAILED",
            errors=errors,
            task_invocation_allowed=not errors,
            duration_ms=duration_ms,
            recovery_guidance=recovery_guidance or None,
        )
