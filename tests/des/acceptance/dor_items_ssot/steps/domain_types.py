"""Typed domain vocabulary for the dor-items-ssot acceptance suite (Mandate-12).

Every domain noun the slice-01 Gherkin names is expressed once here as a type:
the canonical readiness item-set, an individual readiness item, the separate
hard gate, and the read outcome the reviewer observes. Step methods consume
these typed values and delegate to the composition service -- no business logic
and no raw ``str`` where a domain concept already has a type.

The canonical 9-item list is a FIXED closed contract (AD-55 ratified
canonical=9). It is pinned here as the specification the slice-01 ATs assert
the SSOT-backed reader surfaces -- a finite, enumerable domain (falsifier-gate:
parametrize / pinned literal, NOT PBT).
"""

from __future__ import annotations

from dataclasses import dataclass


# The canonical nine Definition-of-Ready readiness items, in id order. This is
# the specification the SSOT (`nWave/data/dor-items.yaml`) must carry and the
# reader must surface -- transcribed from the canonical home
# (`nw-product-owner.md`, heading "## DoR Checklist (9-Item Hard Gate)"). Item 9
# (Outcome-KPIs) is the live-hole closure: the loaded skill drops it today.
CANONICAL_READINESS_ITEMS: tuple[str, ...] = (
    "Problem statement clear, domain language",
    "User/persona with specific characteristics",
    "3+ domain examples with real data",
    "UAT in Given/When/Then (3-7 scenarios)",
    "AC derived from UAT",
    "Right-sized (1-3 days, 3-7 scenarios)",
    "Technical notes: constraints/dependencies",
    "Dependencies resolved or tracked",
    "Outcome KPIs defined with measurable targets and a stated baseline (current-state value the target is measured against)",
)

CANONICAL_READINESS_ITEM_COUNT: int = 9

# The job-traceability gate is a SEPARATE hard gate ABOVE the enumerated nine
# (DISCUSS D-5 / DESIGN DDD-3) -- it is NOT readiness item ten.
JOB_TRACEABILITY_GATE: str = "job-traceability"


@dataclass(frozen=True)
class ReadinessItem:
    """One enumerated Definition-of-Ready readiness item the reviewer checks."""

    name: str


@dataclass(frozen=True)
class CanonicalReadinessSet:
    """The complete set a reviewer reads from the one authoritative place.

    Port-exposed observable shape only (Mandate 8): the enumerated readiness
    items the reviewer sees and the separately-listed hard gates -- never an
    internal loader struct.
    """

    items: tuple[ReadinessItem, ...]
    separate_hard_gates: tuple[str, ...]

    @property
    def item_names(self) -> tuple[str, ...]:
        return tuple(item.name for item in self.items)
