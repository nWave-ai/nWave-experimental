"""Typed domain vocabulary for the f-coherence-and-attestation slice-02 ATs.

Mandate-12 (SSOT + Zero Duplication via Types): every domain noun the slice-02
Gherkin names is expressed once here as a typed enum / frozen dataclass, so the
composition methods consume typed parameters (no raw ``str`` where an enum
exists). The DSL emerges from these typed concepts -- the slice-02 scenarios
range over the LOCKED provider/confidence tiers and the LOCKED stable-core
capability set, not over decorator proliferation.

slice-02 REUSES the slice-01 LOCKED token enums + ``CodeFactObservable`` (the
cross-tier Published Language is the SAME SSOT, ``ADR-LA-001`` §2/§5a, ratified
with SF 2026-06-14, kebab-lowercase, byte-locked) -- re-importing them rather
than re-authoring the locked vocabulary (Mandate-12: one body per domain noun).
This module ADDS only the slice-02-specific scenario vocabulary (the
fallback-chain scope + the chain observable).

ADR-LA-001 D6-R1: the paid Tsunami tier was a fabricated precision stub no
production caller ever wired (LA1-L7: a ``binding-resolved`` answer requires a
real ``TransportWitness``, which OSS ships none of). Its vocabulary
(``TsunamiPresence``, ``ChainScope.TSUNAMI_ONLY``, the loud-skip / gate-proceeds
observable fields) is deleted WITH the stub, never frozen here -- the feature
this module backs never seeds Tsunami state.

These types are TEST-LOCAL (they never import production code) -- the ATs drive
the SUT only through composition-root driving ports (Mandate-13).
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

# REUSE the slice-01 LOCKED token vocabulary + the base observable -- one SSOT for
# the cross-tier Published Language (do NOT re-author the locked tokens here).
from .domain_types_coherence_codefact import (  # noqa: F401  (re-exported vocabulary)
    LOCKED_CAPABILITY_IDS,
    LOCKED_CONFIDENCES,
    LOCKED_PROVIDERS,
    LOCKED_REASON_CODES,
    CapabilityId,
    Confidence,
    Provider,
    ReasonCode,
)


# ---------------------------------------------------------------------------
# slice-02 scenario vocabulary -- the fallback chain scope
# ---------------------------------------------------------------------------


class ChainScope(Enum):
    """Which capability class the chain query targets.

    STABLE_CORE -- one of the LOCKED 5-capability stable core; the universal floor
                   always answers it, so the chain NEVER has a "no provider"
                   outcome (degrade to a lower tier, never a refuse).
    """

    STABLE_CORE = "stable-core"


@dataclass(frozen=True)
class ChainObservable:
    """The observable slice of a chain negotiation the slice-02 ATs assert on.

    Port-exposed names only (Mandate-8 universe discipline): the answering
    provider + its declared confidence + whether a usable answer came back.
    NEVER an internal adapter field.

    ``answered``    -- a usable (non-empty) answer came back from some tier.
    ``provider``    -- which tier answered (LOCKED token).
    ``confidence``  -- the answering tier's declared confidence (LOCKED token).
    ``reason_code`` -- the disambiguating reason (LOCKED token, may be None).
    """

    answered: bool
    provider: str | None
    confidence: str | None
    reason_code: str | None
