"""GateVerdict -- the general DES gate-verdict vocabulary; GateOutcome -- the
immutable verdict of one walking-skeleton gate evaluation.

`GateVerdict` (PASS / FAIL / NOT_APPLICABLE / UNVERIFIED / INDETERMINATE) is
THE domain verdict representation for DES gate CLIs (ADR-GV-001 D1/D3) and,
per ADR-GV-003 (gate-outcome-record-seam), for durable gate-outcome ledger
records as well -- reused as-is by other substrates rather than forked into
a parallel enum. `GateOutcome` remains the walking-skeleton-specific frozen
observation built on top of it: the verdict, the tier of record, the
deferral reason (fail-mode D), and the D6 facet violation (if any).

Pure domain -- no I/O, no dependency on ports or adapters.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class GateVerdict(str, Enum):
    """The general DES gate-verdict vocabulary (ADR-GV-001 D1/D3), reused
    across DES gate CLIs and durable gate-outcome records (ADR-GV-003) --
    not scoped to any single gate.

    PASS            -- the AT ran green at the tier of record.
    FAIL            -- the AT ran red, a D6 facet was violated, or the
                       feature ships an installer artifact with no
                       `@walking-skeleton` AT.
    NOT_APPLICABLE  -- the feature ships no installer-shipped artifact.
    UNVERIFIED      -- no provisionable tier; a deferral marker was written.
    INDETERMINATE   -- the feature's git delta could not be established (git
                       absent / not a work-tree / base ref unresolvable); a LOUD
                       refusal-to-decide rather than a fabricated pass (slice-03).

    The per-member descriptions above are phrased in the walking-skeleton
    gate's own terms (its first producer); a reuser outside that gate maps
    its own PASS/FAIL/... semantics onto the same five members rather than
    literally re-reading "AT"/"tier of record" for its own domain.
    """

    PASS = "pass"
    FAIL = "fail"
    NOT_APPLICABLE = "not_applicable"
    UNVERIFIED = "unverified"
    INDETERMINATE = "indeterminate"


class GateTier(str, Enum):
    """The fidelity tier the walking-skeleton AT ran at (DESIGN tier ladder)."""

    T0 = "t0"
    T1 = "t1"
    T2 = "t2"
    T3 = "t3"


class FacetViolation(str, Enum):
    """The specific D6 facet a `@walking-skeleton` AT failed.

    ENTRY_POINT_ABSENT  -- an entry point the AT invokes does not physically
                           resolve within the staged prefix (the F-11
                           script-mode "never shipped" class -- D6 facet-1).
    RESOLVED_OUTSIDE    -- `des.__file__` resolved OUTSIDE the staged prefix
                           at AT runtime (src/-shadowed import -- D6 facet-1).
    NO_SUBPROCESS       -- a `@walking-skeleton` AT with zero subprocess
                           invocation of the installed entry point (facet-2).
    NO_TRANSFORM        -- the staged tree lacks the build-transform
                           signature (D6 facet-3).
    """

    ENTRY_POINT_ABSENT = "facet-1-violation:entry-point-absent"
    RESOLVED_OUTSIDE = "facet-1-violation:resolved-outside-prefix"
    NO_SUBPROCESS = "facet-2-violation:no-subprocess"
    NO_TRANSFORM = "facet-3-violation:no-transform-signature"


# Exit codes for the gate CLI (DESIGN / CLI contract).
_EXIT_BY_VERDICT: dict[GateVerdict, int] = {
    GateVerdict.PASS: 0,
    GateVerdict.NOT_APPLICABLE: 0,
    GateVerdict.FAIL: 1,
    GateVerdict.UNVERIFIED: 3,
    GateVerdict.INDETERMINATE: 4,
}

# The facet-specific remediation (GDP-3 HOW) for each D6 facet violation.
_HOW_BY_FACET: dict[FacetViolation, str] = {
    FacetViolation.ENTRY_POINT_ABSENT: (
        "ship the entry point so it resolves within the staged prefix"
    ),
    FacetViolation.RESOLVED_OUTSIDE: (
        "import the installed `des`, not the src/-shadowed one"
    ),
    FacetViolation.NO_SUBPROCESS: (
        "the @walking-skeleton AT must invoke the installed entry point via subprocess"
    ),
    FacetViolation.NO_TRANSFORM: (
        "add the build-transform step so the staged tree carries its signature"
    ),
}

_AT_FAILURE_HOW = (
    "green the @walking-skeleton AT at its tier of record (fix the "
    "implementation until it passes), then re-run"
)


@dataclass(frozen=True)
class GateOutcome:
    """An immutable walking-skeleton gate verdict.

    Frozen: a verdict is an observation, never mutated after construction.
    """

    verdict: GateVerdict
    tier_of_record: GateTier
    reason: str = ""
    facet_violation: FacetViolation | None = None
    diagnostic: str = ""
    how: str = ""

    @property
    def exit_code(self) -> int:
        """The gate CLI exit code corresponding to this verdict."""
        return _EXIT_BY_VERDICT[self.verdict]

    @classmethod
    def passed(cls, tier: GateTier) -> GateOutcome:
        """A PASS outcome at the given tier of record."""
        return cls(verdict=GateVerdict.PASS, tier_of_record=tier)

    @classmethod
    def facet_failure(
        cls, tier: GateTier, facet: FacetViolation, diagnostic: str
    ) -> GateOutcome:
        """A FAIL outcome caused by a D6 facet violation."""
        return cls(
            verdict=GateVerdict.FAIL,
            tier_of_record=tier,
            facet_violation=facet,
            diagnostic=diagnostic,
            how=_HOW_BY_FACET[facet],
        )

    @classmethod
    def at_failure(cls, tier: GateTier, diagnostic: str) -> GateOutcome:
        """A FAIL outcome caused by the walking-skeleton AT running red."""
        return cls(
            verdict=GateVerdict.FAIL,
            tier_of_record=tier,
            diagnostic=diagnostic,
            how=_AT_FAILURE_HOW,
        )

    @classmethod
    def not_applicable(cls, rationale: str) -> GateOutcome:
        """A NOT_APPLICABLE outcome for a justified non-installable feature.

        The sole producer of the NOT_APPLICABLE verdict: a feature that declared
        `walking_skeleton_applicable: false` with a non-empty rationale and whose
        `feature_root` the gate mechanically detected as non-installable.
        """
        return cls(
            verdict=GateVerdict.NOT_APPLICABLE,
            tier_of_record=GateTier.T0,
            diagnostic=rationale,
        )

    @classmethod
    def indeterminate(cls, reason: str) -> GateOutcome:
        """An INDETERMINATE outcome -- a LOUD refusal-to-decide (slice-03).

        The sole producer of the INDETERMINATE verdict: a feature whose git
        delta could not be established (git absent / not a work-tree / base ref
        unresolvable). The gate refuses to decide rather than fabricate a pass;
        the `reason` propagated from the port's `Indeterminate` names the cause.
        """
        return cls(
            verdict=GateVerdict.INDETERMINATE,
            tier_of_record=GateTier.T0,
            diagnostic=reason,
        )


__all__ = ["FacetViolation", "GateOutcome", "GateTier", "GateVerdict"]
