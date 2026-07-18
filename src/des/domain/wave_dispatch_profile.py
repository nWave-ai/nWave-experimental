"""WaveDispatchProfile -- the ceremony profile a dispatch owes ITS OWN wave.

Sibling datum to ``lane_profile.LANE_PROFILES``, on the orthogonal axis. The
lane datum answers "which ceremony does this *kind* of work owe?"
(prefactoring vs slice); this one answers "which ceremony does this *wave*
owe?" (DISCUSS vs DELIVER).

ROOT CAUSE this datum closes (measured 2026-07-18): the atdd_pure section
validator keyed ONLY on DES-PHASE and DES-LANE, so a dispatch for an
authoring wave -- which legitimately declares neither -- fell through to the
fail-closed DELIVER default and was held to the full 12 implementation
sections. Two concrete harms, both observed:

  * ``ATDD_PURE_PHASES`` / ``AT_COMPLETION_LEDGER`` / ``RECORDING_INTEGRITY``
    / ``TERMINATING_RUN`` are empty ceremony for a wave that writes a
    document and runs no tests; and
  * ``DESIGN_CONTEXT`` is actively WRONG for DISCUSS. DISCUSS runs BEFORE
    DESIGN, so there is no design to cite -- yet the guard demanded the
    section, and the operator satisfied it by injecting design context into a
    wave whose whole job is to derive value BEFORE any design exists. The
    guard did not merely fail to prevent that inversion; it CAUSED it.

``required_sections`` is a LITERAL tuple per wave (same D2 constraint the
lane datum carries: the domain must not import the application-layer
``ATDD_PURE_MANDATORY_SECTIONS`` to derive it), in the same order as the full
set so a rendered prompt keeps one canonical section order.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class WaveDispatchProfile:
    """One row of the queryable per-wave dispatch-ceremony datum."""

    wave: str
    required_sections: tuple[str, ...]
    cites_design: bool
    runs_tests: bool


# The sections every dispatch owes regardless of wave: who is dispatched, what
# they must read, what the task is, what bounds it, how long they have.
_AUTHORING_BASE: tuple[str, ...] = (
    "DES_METADATA",
    "AGENT_IDENTITY",
    "SKILL_LOADING",
    "TASK_CONTEXT",
    "QUALITY_GATES",
    "BOUNDARY_RULES",
    "TIMEOUT_INSTRUCTION",
)

# An authoring wave DOWNSTREAM of DESIGN cites the design; DISCUSS cannot.
# Insert DESIGN_CONTEXT at its canonical position (after TASK_CONTEXT).
_AUTHORING_WITH_DESIGN: tuple[str, ...] = (
    "DES_METADATA",
    "AGENT_IDENTITY",
    "SKILL_LOADING",
    "TASK_CONTEXT",
    "DESIGN_CONTEXT",
    "QUALITY_GATES",
    "BOUNDARY_RULES",
    "TIMEOUT_INSTRUCTION",
)

# The full 12 -- the DELIVER profile. Spelled literally (D2) and asserted
# equal to ATDD_PURE_MANDATORY_SECTIONS by a contract test, so the two cannot
# drift apart silently.
_DELIVER_SECTIONS: tuple[str, ...] = (
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


# The queryable per-wave datum. Every consulting locus READS this (it never
# hand-branches ``if wave == "discuss"``), so substituting the datum
# substitutes the decision.
WAVE_DISPATCH_PROFILES: dict[str, WaveDispatchProfile] = {
    "discuss": WaveDispatchProfile(
        wave="discuss",
        required_sections=_AUTHORING_BASE,
        cites_design=False,  # DISCUSS precedes DESIGN -- there is nothing to cite
        runs_tests=False,
    ),
    "design": WaveDispatchProfile(
        wave="design",
        required_sections=_AUTHORING_WITH_DESIGN,
        cites_design=True,
        runs_tests=False,
    ),
    "devops": WaveDispatchProfile(
        wave="devops",
        required_sections=_AUTHORING_WITH_DESIGN,
        cites_design=True,
        runs_tests=False,
    ),
    "distill": WaveDispatchProfile(
        wave="distill",
        required_sections=_AUTHORING_WITH_DESIGN,
        cites_design=True,
        runs_tests=False,
    ),
    "deliver": WaveDispatchProfile(
        wave="deliver",
        required_sections=_DELIVER_SECTIONS,
        cites_design=True,
        runs_tests=True,
    ),
    "feature-end": WaveDispatchProfile(
        wave="feature-end",
        required_sections=_DELIVER_SECTIONS,
        cites_design=True,
        runs_tests=True,
    ),
}
