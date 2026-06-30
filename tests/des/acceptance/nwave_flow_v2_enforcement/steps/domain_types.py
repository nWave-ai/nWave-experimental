"""Typed domain vocabulary for the nwave-flow-v2-enforcement slice-04 ATs.

Mandate-12 (SSOT + Zero Duplication via Types): every domain noun the Gherkin
names is expressed once here as a typed enum, so the composition methods consume
typed parameters (no raw ``str`` where an enum exists) and the DSL emerges from
the type system rather than from decorator proliferation.

These types are TEST-LOCAL (they never import production code) -- the ATs drive
the SUT only through composition-root driving ports (Mandate-13).
"""

from __future__ import annotations

from enum import Enum


class Wave(Enum):
    """The closed nWave wave vocabulary the literal ``/nw-<wave>`` selects."""

    DISCUSS = "discuss"
    DESIGN = "design"
    DEVOPS = "devops"
    DISTILL = "distill"
    DELIVER = "deliver"


class Provenance(Enum):
    """How a wave-active record was armed -- mirrors ``WaveProvenance`` (observable)."""

    COMMAND = "command"  # written deterministically from the literal /nw-<wave>
    INFERRED = "inferred"  # written by the PreToolUse strand-2 fallback


class WaveActiveState(Enum):
    """The observable wave-active store state the floor exposes."""

    ARMED = "armed"  # a record is present on the floor
    ABSENT = "absent"  # NoWaveActive -- the S1 floor, no wave armed


class ChildMarkers(Enum):
    """Whether an in-wave sub-dispatch carries the wave's required DES markers."""

    PRESENT = "present"  # the child carries the in-wave markers -> allowed
    MARKERLESS = "markerless"  # the child dropped its markers -> S2 DENY


class GateDecision(Enum):
    """The observable PreToolUse decision surface (allow vs deny/block)."""

    ALLOW = "allow"
    DENY = "deny"
