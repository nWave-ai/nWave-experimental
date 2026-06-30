"""Typed domain vocabulary for the fix-verify-wave-dispatch-exemption-ssot ATs.

Mandate-12 (SSOT via Types): every domain noun the slice-01 Gherkin names is a
typed enum here, so composition methods consume typed parameters (no raw ``str``
where an enum exists). These types are TEST-LOCAL: they never import production
code. The ATs drive the SUT only through composition-root driving ports
(Mandate-13): the in-tree ``des.cli.verify_wave_dispatch`` gate (Layer-3
subprocess) and the pure ``decide_dispatch`` policy, AND -- for the AC-5 SSOT
agreement property -- the real PreToolUse AT-3 service (Layer-3 composition).

The two checks' observable surfaces:
  * verify-wave-dispatch -> the process EXIT CODE (0 ALLOW / 1 BLOCK / 2 malformed)
    plus the one JSON verdict line on stdout.
  * PreToolUse AT-3      -> a ``HookDecision`` whose ``action`` ("allow"|"block")
    projects onto the SAME ALLOW/BLOCK binary.

The Universe the ATs track is those port-exposed names (exit code / verdict
token / HookDecision.action), never the policy's internal regex objects.
"""

from __future__ import annotations

from enum import Enum


class Verdict(Enum):
    """The observable dispatch-exemption verdict, shared across BOTH checks.

    verify-wave-dispatch projects it onto the process EXIT CODE (0/1); PreToolUse
    AT-3 projects it onto ``HookDecision.action`` ("allow"|"block"). The two checks
    MUST agree on this binary for the collision case (AC-5). MALFORMED (2) is the
    verify-wave-dispatch argparse failure, irrelevant to the reconcile but kept so
    a non-{0,1} exit at HEAD reads as a clean verdict mismatch, never a crash.
    """

    ALLOW = 0
    BLOCK = 1
    MALFORMED = 2


class WaveOwner(Enum):
    """A wave-OWNER subagent the guard gates (DDD-8 wave->owner map).

    Each value is the exact ``subagent_type`` the orchestrator dispatches. The
    DISTILL owner (acceptance-designer) is the collision-case probe: under an
    active distill floor, a non-entering partial-marker dispatch of it is exactly
    what PreToolUse AT-3 blocks.
    """

    ACCEPTANCE_DESIGNER = "nw-acceptance-designer"  # DISTILL
    SOLUTION_ARCHITECT = "nw-solution-architect"  # DESIGN
    PRODUCT_OWNER = "nw-product-owner"  # DISCUSS


# A representative reviewer subagent_type -- never in WAVE_OWNERS, always exempt.
REVIEWER_TYPE = "nw-solution-architect-reviewer"


class FloorState(Enum):
    """Whether a wave-active floor is armed on disk + its entry_pending flag.

    The collision case AT-3 blocks requires an ACTIVE floor whose ``entry_pending``
    is cleared (a non-entering in-wave dispatch). The legit-entry ALLOW carries
    ``entry_pending=True`` (the COMMAND arm wrote it) OR no floor at all.
    """

    ABSENT = "absent"  # no .nwave/wave-active/active.json -> no floor
    ACTIVE_NON_ENTERING = "active_non_entering"  # floor armed, entry_pending=False
    ACTIVE_ENTERING = "active_entering"  # floor armed, entry_pending=True


class DispatchMarker(Enum):
    """The wave-marker shape the dispatch prompt carries (drives carries_partial).

    PARTIAL_WAVE_ONLY = a ``<!-- DES-WAVE: <wave> -->`` marker but NO
    ``DES-VALIDATION`` marker -> ``carries_partial_wave_context=True`` (the AT-3
    collision discriminant). FULL_VALIDATED additionally carries DES-VALIDATION
    (a complete dispatch -- not partial). NONE = no marker at all.
    """

    NONE = "none"
    PARTIAL_WAVE_ONLY = "partial_wave_only"
    FULL_VALIDATED = "full_validated"


class SkipAuthorization(Enum):
    """The off-spine skip-authorization state a marker-less dispatch may carry (AC-4).

    FORM-only (DDD-9): the guard verifies a witness FORM (canonical heading +
    non-empty rationale) or a non-expired session pre-grant.
    """

    NONE = "none"  # no witness, no grant -> BLOCK
    FORM_VALID_WITNESS = "form_valid_witness"  # heading + non-empty rationale -> ALLOW
    VALID_PRE_GRANT = "valid_pre_grant"  # non-expired session grant -> ALLOW
    EXPIRED_PRE_GRANT = (
        "expired_pre_grant"  # TTL-elapsed grant -> reads absent -> BLOCK
    )
