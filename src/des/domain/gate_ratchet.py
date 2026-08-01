#!/usr/bin/env python3
"""A gate must not block the write that would resolve its own complaint.

Any gate with a three-state verdict that exits non-zero on the third state
carries this defect. The third state says "I cannot see whether this is bad" --
and a condition that makes it fire is frequently ENVIRONMENTAL rather than
authored: an object store repacked underneath the document, a tool absent from
this box, a network the checkout cannot reach. When that happens the gate closes
the only surface that could record the repair, including the repair to the very
rows it is complaining about.

The observed case, 2026-07-30: ``validate_mikado_tree_coherence.py`` reported 88
unverifiable findings over 68 of 108 nodes and ZERO rejects, every one because
``git gc`` had moved a closure sha into a packfile. The Mikado SSOT was
uncommittable for hours; twelve nodes closed on trunk could not be written down.

WHAT THIS IS NOT
----------------
It is not "make the third state non-blocking". That converts an honest third
state into a silent pass and unblocks the document by making it meaningless. The
findings still print, still carry their names, still count, and the verdict still
reads NOT_VERIFIABLE. Only the EXIT CODE is decided on the delta.

DECIDE ON THE PROPERTY, NOT ON THE COUNT
----------------------------------------
The tempting rule is "block when the total grows". The total is a designation:
a change that drops one unverifiable claim and adds a different one keeps it
flat while adding a claim the gate cannot check -- the silent pass, one level up.
So the decision is on the multiset of finding IDENTITIES: any key whose
occurrence count rose is growth, whoever else shrank. This is strictly stronger
than the count rule (a rising total always implies a rising key) and never
permits anything the count rule would refuse.

REJECTS ARE NEVER RATCHETED
---------------------------
A caller must apply this ONLY to the could-not-verify population. A real
incoherence blocks absolutely, at any count, and must not even reach here --
an allowance printed beside a rejection is an invitation to misread it.

Only dependency: Python.

Relocated from ``scripts/validation/gate_ratchet.py`` (gate-ratchet-skill-
normative, Mikado D86): this decision is gate-agnostic on purpose (it has zero
project imports), and a second gate (``des skill-normative-gate``) needed to
reuse it. ``src/des/`` cannot import ``scripts/`` (dev-only, not shipped), so
the SSOT/DRY-correct move is the same one applied to the git object readers
this decision is normally paired with: relocate here, and leave
``scripts/validation/gate_ratchet.py`` as a thin shim re-exporting this
module's public names -- ``validate_mikado_tree_coherence.py`` and the
``mikado-tree-coherence`` pre-commit hook keep working byte-identically.
"""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from enum import Enum
from typing import TYPE_CHECKING


if TYPE_CHECKING:
    from collections.abc import Iterable


class RatchetOutcome(str, Enum):
    """What the delta between two third-state populations decided."""

    #: Nothing to ratchet: the current run has no third-state finding at all.
    NO_THIRD_STATE = "NO_THIRD_STATE"
    #: The population did not grow. Allowed, LOUDLY -- never called a pass.
    NOT_INCREASED = "NOT_INCREASED"
    #: This change adds at least one claim the gate cannot check. Refused.
    INCREASED = "INCREASED"
    #: The previous population could not be read. Refused -- an allowance
    #: granted by ignorance is worse than the hostage it would release.
    BASELINE_UNAVAILABLE = "BASELINE_UNAVAILABLE"


@dataclass(frozen=True)
class RatchetDecision:
    outcome: RatchetOutcome
    current_total: int
    #: ``-1`` means NOT MEASURED (the baseline could not be read). Zero would
    #: say "there were none before", which is a different -- and false -- claim.
    baseline_total: int
    #: ``(key, how many more times it occurs now)`` for every key that grew.
    introduced: tuple[tuple[str, int], ...]
    #: How the baseline was obtained, in checkable terms, or why it was not.
    provenance: str
    #: A command that shows the author the claim that refused them. Supplied by
    #: the calling gate, because only the gate knows its own affordances -- a
    #: refusal whose HOW is "remove the unverifiable claim" puts the work of
    #: locating it back on the operator, which is the cost this tree keeps
    #: moving onto the system.
    how: str = ""

    @property
    def blocks(self) -> bool:
        return self.outcome in (
            RatchetOutcome.INCREASED,
            RatchetOutcome.BASELINE_UNAVAILABLE,
        )

    def render(self) -> str:
        if self.outcome is RatchetOutcome.NO_THIRD_STATE:
            return ""
        if self.outcome is RatchetOutcome.BASELINE_UNAVAILABLE:
            return "\n".join(
                [
                    "RATCHET CANNOT DECIDE — refusing.",
                    f"  This change is measured against the previous state of the same "
                    f"paths, and that state could not be read: {self.provenance}",
                    f"  So the {self.current_total} finding(s) above cannot be attributed "
                    "to this change or to what came before it.",
                    "  An allowance granted without a baseline is an allowance granted by "
                    "ignorance, which is worse than the refusal.",
                ]
            )
        if self.outcome is RatchetOutcome.INCREASED:
            named = "\n".join(
                f"    + {key}" + (f"  (×{delta} more)" if delta > 1 else "")
                for key, delta in self.introduced
            )
            return "\n".join(
                [
                    f"RATCHET BLOCK — this change introduces {sum(d for _, d in self.introduced)} "
                    "claim(s) the gate cannot check:",
                    named,
                    f"  third-state population: {self.baseline_total} before this change, "
                    f"{self.current_total} now.",
                    f"  baseline: {self.provenance}",
                    "  Pre-existing findings are not what refused this — the new ones "
                    "above are. Make each of them verifiable, or do not claim it.",
                ]
                + ([f"  HOW  {self.how}"] if self.how else [])
            )
        movement = (
            "unchanged"
            if self.current_total == self.baseline_total
            else f"down from {self.baseline_total}"
        )
        return "\n".join(
            [
                f"RATCHET ALLOW — {self.current_total} finding(s) the gate CANNOT CHECK "
                f"remain in this document ({movement}).",
                "  Every one of them is printed above. This is NOT a clean pass: the "
                "document is still not verifiable.",
                "  It is allowed only because this change introduced none of them — the "
                "condition pre-dates it, and refusing here would hold the record hostage "
                "to something this change did not cause.",
                f"  baseline: {self.provenance}",
            ]
        )


def decide_ratchet(
    current: Iterable[str], baseline: Iterable[str], provenance: str
) -> RatchetDecision:
    """Decide on the DELTA between two third-state populations.

    ``current`` and ``baseline`` are iterables of finding identities -- whatever
    string a caller uses to mean "this same complaint about this same subject".
    Compared as MULTISETS: two unverifiable findings on one node are two claims,
    and a reader who deduplicated them would let the second ride in free.
    """
    now = Counter(current)
    before = Counter(baseline)
    current_total = sum(now.values())
    baseline_total = sum(before.values())
    if current_total == 0:
        return RatchetDecision(
            RatchetOutcome.NO_THIRD_STATE, 0, baseline_total, (), provenance
        )
    grew = tuple(
        sorted(
            (key, count - before.get(key, 0))
            for key, count in now.items()
            if count > before.get(key, 0)
        )
    )
    outcome = RatchetOutcome.INCREASED if grew else RatchetOutcome.NOT_INCREASED
    return RatchetDecision(outcome, current_total, baseline_total, grew, provenance)


def undecidable_baseline(current: Iterable[str], reason: str) -> RatchetDecision:
    """No baseline could be read. Fail-closed, and say which reason closed it."""
    now = Counter(current)
    return RatchetDecision(
        RatchetOutcome.BASELINE_UNAVAILABLE,
        sum(now.values()),
        -1,
        (),
        reason,
    )
