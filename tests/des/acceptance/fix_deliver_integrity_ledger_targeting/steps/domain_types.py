"""Domain types for the deliver-integrity ledger-targeting acceptance.

Mandate-12 SSOT: the domain noun the Gherkin speaks about (a set of slice
identifiers) is expressed once, here, as a typed concept. A SliceSet parses a
comma-separated Gherkin literal into the canonical ordered tuple of slice
identifiers the composition root operates on.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class SliceSet:
    """An ordered, de-duplicated set of `slice-NN` identifiers.

    Parses the comma-separated Gherkin literal (``"slice-01, slice-02"``) into
    the canonical tuple the composition root iterates over when seeding git
    commits and ledger records.
    """

    slices: tuple[str, ...]

    @classmethod
    def parse(cls, literal: str) -> SliceSet:
        seen: list[str] = []
        for token in literal.split(","):
            slice_id = token.strip()
            if slice_id and slice_id not in seen:
                seen.append(slice_id)
        return cls(tuple(seen))

    def __iter__(self):
        return iter(self.slices)
