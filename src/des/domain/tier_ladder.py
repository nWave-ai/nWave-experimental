"""TierLadder -- the escalation rule mapping environment capability to tier.

Domain logic for feature `walking-skeleton-production-like-gate` (DESIGN /
Tiered Gate Architecture, escalation rule). Pure -- no I/O.

The gate runs the walking-skeleton AT at the highest provisionable tier:

  Docker available  -> T2 (T1 is its prerequisite floor, always run first)
  pip works only    -> T1
  not even T1       -> fail-mode D (no provisionable tier)

slice-01 (the walking skeleton) only exercises the T1 branch: `pip install
--target` against a clean prefix. T2 / fail-mode D land in later slices.
"""

from __future__ import annotations

from enum import Enum

from des.domain.gate_outcome import GateTier


class TierCapability(str, Enum):
    """What the `EnvironmentProbe` reports the host can provision.

    NONE      -- not even T1: no writable tmp / no pip / build incapable.
    PIP_ONLY  -- Python+pip work, no Docker -- T1 is the ceiling.
    DOCKER    -- Docker reachable -- T2 reachable; T1 still the floor.
    """

    NONE = "none"
    PIP_ONLY = "pip_only"
    DOCKER = "docker"


class TierLadder:
    """The escalation rule from `TierCapability` to the tier of record."""

    @staticmethod
    def tier_of_record(capability: TierCapability) -> GateTier | None:
        """The tier the gate runs the walking-skeleton AT at.

        Returns `None` when no tier is provisionable (fail-mode D). DOCKER
        escalates to T2; PIP_ONLY caps at T1; NONE is unprovisionable.
        """
        if capability is TierCapability.DOCKER:
            return GateTier.T2
        if capability is TierCapability.PIP_ONLY:
            return GateTier.T1
        return None


__all__ = ["TierCapability", "TierLadder"]
