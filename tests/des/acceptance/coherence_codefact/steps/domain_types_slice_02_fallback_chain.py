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
fallback-chain tiers, the Tsunami-presence cases, the chain observable).

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
# slice-02 scenario vocabulary -- the fallback chain tiers + Tsunami presence
# ---------------------------------------------------------------------------


class TsunamiPresence(Enum):
    """Whether the paid-tier Tsunami precision adapter is wired at the chain head.

    ABSENT is the NORMAL case on a target machine (``ADR-LA-001`` C7): Tsunami is
    the paid open-core seam, wired only when its ``probe()`` passes. Its absence
    must degrade LOUD (the chain continues to the next tier), never silent-fail.
    PRESENT is the paid-tier case (a test double of the probe passes): the chain
    head answers ``binding-resolved``.
    """

    ABSENT = "absent"  # paid Tsunami tier not wired -- the normal case
    PRESENT = "present"  # paid Tsunami tier wired (probe passes)


class ChainScope(Enum):
    """Which capability class the chain query targets (C8).

    STABLE_CORE -- one of the LOCKED 5-capability stable core; the universal floor
                   always answers it, so the chain NEVER has a "no provider"
                   outcome (degrade to a lower tier, never a refuse).
    TSUNAMI_ONLY -- a premium capability only the paid Tsunami tier can honor; with
                    Tsunami ABSENT the chain SKIPS it LOUDLY (a
                    ``health.gate.code-fact.*`` ledger event) and the gate PROCEEDS
                    (C8) -- it does NOT block, does NOT fabricate a stable-core
                    answer, does NOT hang.
    """

    STABLE_CORE = "stable-core"
    TSUNAMI_ONLY = "tsunami-only"


@dataclass(frozen=True)
class ChainObservable:
    """The observable slice of a chain negotiation the slice-02 ATs assert on.

    Port-exposed names only (Mandate-8 universe discipline): the answering
    provider + its declared confidence + whether a usable answer came back +
    whether the chain emitted a LOUD skip signal (the
    ``health.gate.code-fact.*`` event) and whether the gate PROCEEDED. NEVER an
    internal adapter field.

    ``answered``        -- a usable (non-empty) answer came back from some tier.
    ``provider``        -- which tier answered (LOCKED token), or None when a
                           Tsunami-only capability was skipped loudly.
    ``confidence``      -- the answering tier's declared confidence (LOCKED token).
    ``reason_code``     -- the disambiguating reason (LOCKED token, may be None).
    ``loud_skip_event`` -- a LOUD ``health.gate.code-fact.*`` skip signal was
                           emitted (the degrade-LOUD observable; True when a tier
                           was skipped because it was absent).
    ``gate_proceeded``  -- the gate continued (did NOT block / hang) after a
                           skip -- the C8 "gate PROCEEDS" observable.
    """

    answered: bool
    provider: str | None
    confidence: str | None
    reason_code: str | None
    loud_skip_event: bool
    gate_proceeded: bool
