"""``CodeFactPort`` — a vendor-neutral driven port for *facts about code* (OSS tier).

ADR-LA-001 (the permanent SSOT, cross-tier Published Language LOCKED with SF
2026-06-14). This module is the OSS *implementation* of the port the ADR specifies:
a capability protocol + a frozen 5-capability stable core + the
``{provider, confidence, reason_code}`` verdict envelope.

A consumer NEVER branches on operation names. It asks the registry "is capability
C available at ``contract_version >= floor`` AND ``stability >= required``?" and
then calls :meth:`CodeFactPort.query`. Every answer comes back in a
:class:`CodeFactResult` envelope tagged with which provider produced it and at
what declared confidence — the confidence label IS the loud signal (Invariant 2).

The token *values* (``provider`` / ``confidence`` / ``reason_code``) and the five
capability ids are CONSUMED BYTE-IDENTICAL from ADR-LA-001 §2/§5a (kebab-lowercase,
ratified with SF). They are NOT re-authored — the ``tests/build/**`` byte-lock
guard is the mechanical witness that this serialization stays byte-identical to
the committed locked-vocabulary fixture (C1, cross-tier byte-lock).

Read-only universe (Principle 12 — a fact port only reads; NO write method).
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Protocol


# ---------------------------------------------------------------------------
# LOCKED Published Language (ADR-LA-001 §2 / §5a) — CONSUMED byte-identical.
# kebab-lowercase. Renaming ANY token is the cross-tier-lock drift the
# tests/build/** byte-lock guard catches RED.
# ---------------------------------------------------------------------------


class Provider(str, Enum):
    """Which adapter produced the answer (ADR-LA-001 §5a; additive field)."""

    TSUNAMI = "tsunami"
    AST = "ast"
    TEXTSEARCH = "textsearch"


class Confidence(str, Enum):
    """The ONLY cross-seam-readable token (ADR-LA-001 §5a; 1:1 down the chain).

    ``binding-resolved`` (Tsunami, precise) > ``approx`` (AstAdapter, structural)
    > ``noisy`` (TextSearchAdapter, textual — the universal floor). Each provider
    declares — never inflates — its own confidence.
    """

    BINDING_RESOLVED = "binding-resolved"
    APPROX = "approx"
    NOISY = "noisy"


class ReasonCode(str, Enum):
    """Disambiguates live-but-non-callable from genuinely-absent (ADR-LA-001 §5a)."""

    LIVE_NON_CALLABLE = "live-non-callable"
    ABSENT = "absent"


class Stability(str, Enum):
    """The capability stability axis of the two-axis floor (ADR-LA-001 §1/§4)."""

    STABLE = "stable"
    SPIKE = "spike"


# The frozen 5-capability stable core (ADR-LA-001 §2), LOCKED byte-identical.
# The other ~10 Tsunami capabilities enter later, per-tier, through the protocol,
# YAGNI — never pre-declared.
CAPABILITY_CALLERS_OF = "query.callers-of"
CAPABILITY_READS_OF = "query.reads-of"
CAPABILITY_NEVER_WIRED = "query.never-wired"
CAPABILITY_ATOMS_IN_FILE = "query.atoms-in-file"
CAPABILITY_ADR_SECTION = "query.adr-section"

STABLE_CORE_CAPABILITY_IDS: frozenset[str] = frozenset(
    {
        CAPABILITY_CALLERS_OF,
        CAPABILITY_READS_OF,
        CAPABILITY_NEVER_WIRED,
        CAPABILITY_ATOMS_IN_FILE,
        CAPABILITY_ADR_SECTION,
    }
)

#: ADDITIVE capability beyond the LOCKED 5-capability stable core (sustainable-test-suite
#: slice-09, DDD-17C). NOT a member of ``STABLE_CORE_CAPABILITY_IDS`` (that set is the
#: byte-locked cross-tier core — adding to it would be the drift the byte-lock guard catches
#: RED). The step-shape corpus capability is an OSS-tier extension the structural ``ast``
#: tier honors: it reports the near-duplicate-step-group / total-step-definition counts over
#: a real AST step-shape corpus, the impure leg behind the existing-base near-duplicate-step
#: ratio. The textual floor does NOT cover it (no structural step shape from a text scan), so
#: an absent/unparseable corpus degrades LOUD to "no step-shape fact" (never a fabricated 0).
CAPABILITY_STEP_SHAPE_CORPUS = "query.step-shape-corpus"

#: ADDITIVE capability beyond the LOCKED 5-capability stable core (WS-9b,
#: codefact-similar-responsibility slice-01). NOT a member of
#: ``STABLE_CORE_CAPABILITY_IDS`` (that set is byte-locked — adding to it
#: would be the drift the byte-lock guard catches RED). Mirrors
#: ``CAPABILITY_STEP_SHAPE_CORPUS``'s additive-capability seam: given a
#: proposed NEW symbol name (+ optional arity), it returns EXISTING
#: module-level ``def``/``class`` symbols under a scope whose structural
#: fingerprint (name-token Jaccard + parameter arity) overlaps it — RANKED
#: candidates, advisory only (never blocking). The textual floor does NOT
#: cover it (no structural fingerprint from a text scan), so an
#: unparseable/empty scope degrades LOUD to "no similar-responsibility fact"
#: (``absent``), never a fabricated empty candidate list.
CAPABILITY_SIMILAR_RESPONSIBILITY = "query.similar-responsibility"


# ---------------------------------------------------------------------------
# Capability descriptor + verdict envelope (ADR-LA-001 §1 / §5a)
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class CapabilityDescriptor:
    """A self-describing capability (ADR-LA-001 §1).

    ``id`` is one of the LOCKED 5-capability stable core; ``stability`` and
    ``contract_version`` are the two-axis floor the composition root negotiates.
    """

    id: str
    stability: str
    contract_version: str
    io_schema: str
    providing_adapter: str


@dataclass(frozen=True)
class CodeFactResult:
    """The verdict envelope (ADR-LA-001 §5a, LOCKED).

    ``provider`` ∈ {tsunami, ast, textsearch}; ``confidence`` ∈
    {binding-resolved, approx, noisy} (the ONLY cross-seam-readable token, 1:1
    with provider); ``reason_code`` ∈ {live-non-callable, absent} (or ``None``
    when not applicable to the capability). ``payload`` is the capability-specific
    plain data — a non-``None`` payload IS the "a usable answer came back" signal.

    pure-function shape: plain data out, never a live ``ast`` node.
    """

    provider: str
    confidence: str
    payload: object
    reason_code: str | None = None


class CodeFactPort(Protocol):
    """The driven port for facts about code — read-only (NO write method).

    One method: :meth:`query`. A consumer asks the registry whether a capability
    is available at the floor, then calls ``query`` with the capability descriptor
    and a request mapping. The answer ALWAYS comes back in a :class:`CodeFactResult`
    envelope (the universal floor guarantees a non-empty answer on any Python-only
    target — there is no "no provider" outcome for a stable-core capability).
    """

    def query(
        self, descriptor: CapabilityDescriptor, request: dict[str, object]
    ) -> CodeFactResult:
        """Answer the capability named by ``descriptor`` over ``request``."""
        ...
