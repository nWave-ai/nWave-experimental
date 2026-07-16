"""Domain types -- des-refactor-fixer-swarm slice-01 acceptance set (Mandate 12).

Typed enums for the Given-side arrangements the slice-01 composition needs.
Step/composition methods consume these typed parameters, never a raw ``str``
(Mandate 12 criterion 2).
"""

from __future__ import annotations

from enum import Enum


class IntegrationTreeState(str, Enum):
    """The integration branch's tree state a merge-back attempt observes (D4/D5)."""

    CLEAN = "clean"
    DIRTY = "dirty"


class DrainOutcome(str, Enum):
    """Whether the agent's work on an item ultimately merges (pile-move gate)."""

    SUCCEEDS = "succeeds"
    FAILS_GREEN_TO_GREEN = "fails_green_to_green"
