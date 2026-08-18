"""``CodeFactPort`` — a vendor-neutral driven port for *facts about code* (OSS tier).

ADR-LA-001 (the permanent SSOT, ratified 2026-08-17). This module is the OSS
*implementation* of the port the ADR specifies: a capability protocol + a
frozen 5-capability stable core + the ``{provider, confidence, payload}``
verdict envelope. The disambiguating ``reason_code`` vocabulary
(``live-non-callable`` / ``absent``) is owned by the capability whose payload
schema needs it (e.g. ``never-wired``'s ``never_wired`` bool) — never a
generic envelope field (D9 slice (c), D6-R3).

A consumer NEVER branches on operation names. It asks the registry "is capability
C available at ``contract_version >= floor`` AND ``stability >= required``?" and
then calls :meth:`CodeFactPort.query`. Every answer comes back in a
:class:`CodeFactResult` envelope tagged with which provider produced it and at
what declared confidence — the confidence label IS the loud signal (Invariant 2).

The token *values* (``provider`` / ``confidence`` / capability ids) are CONSUMED
BYTE-IDENTICAL from ADR-LA-001 §2/§5a (kebab-lowercase). They are NOT
re-authored — the ``tests/build/**`` byte-lock guard is the mechanical witness
that this serialization stays byte-identical to the committed
locked-vocabulary fixture (C1, cross-tier byte-lock).

Read-only universe (Principle 12 — a fact port only reads; NO write method).
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import TYPE_CHECKING, Protocol


if TYPE_CHECKING:
    from collections.abc import Mapping


# ---------------------------------------------------------------------------
# LOCKED Published Language (ADR-LA-001 §2 / §5a) — CONSUMED byte-identical.
# kebab-lowercase. Renaming ANY token is the cross-tier-lock drift the
# tests/build/** byte-lock guard catches RED.
#
# ``provider`` is deliberately NOT a closed enum here (D4, open provider
# identity): it is an open, non-empty string — a new provider is a new id,
# never an enum edit. The bundled OSS ids are ``"ast"`` and ``"textsearch"``
# (each adapter's own ``provider``/``provider_id`` class attribute is the
# single source of truth for its token).
# ---------------------------------------------------------------------------


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

#: ADDITIVE capability beyond the LOCKED 5-capability stable core (WS-9b,
#: codefact-similar-responsibility slice-01). NOT a member of
#: ``STABLE_CORE_CAPABILITY_IDS`` (that set is byte-locked — adding to it
#: would be the drift the byte-lock guard catches RED). Given a proposed NEW
#: symbol name (+ optional arity), it returns EXISTING module-level
#: ``def``/``class`` symbols under a scope whose structural fingerprint
#: (name-token Jaccard + parameter arity) overlaps it — RANKED candidates,
#: advisory only (never blocking). The textual floor does NOT cover it (no
#: structural fingerprint from a text scan), so an unparseable/empty scope
#: degrades LOUD to "no similar-responsibility fact" (``absent``), never a
#: fabricated empty candidate list.
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
    """The verdict envelope (ADR-LA-001 §5a).

    ``provider`` is an open, non-empty string identifying which adapter
    answered (bundled ids: ``ast``, ``textsearch`` — D4, open provider
    identity); ``confidence`` ∈ {binding-resolved, approx, noisy} (the ONLY
    cross-seam-readable token, 1:1 with provider). ``payload`` is the
    capability-specific plain data — a non-``None`` payload IS the "a usable
    answer came back" signal; any disambiguating reason a capability needs
    (e.g. ``never-wired``'s ``live-non-callable``/``absent`` split) lives IN
    that payload, never as a generic envelope field (D9 slice (c), D6-R3).

    pure-function shape: plain data out, never a live ``ast`` node.
    """

    provider: str
    confidence: str
    payload: object


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


# ---------------------------------------------------------------------------
# ADR-LA-001 D9 GREEN_TO_GREEN — internal resolution algebra.
#
# ``resolve_through_fold`` IS reachable from the public boundary: this
# GREEN_TO_GREEN slice wires it into ``CodeFactChain.query`` (a thin edge
# unwraps the winning ``Answered.payload`` back to the legacy
# ``CodeFactResult`` shape). Only the explicit ``Resolution`` sum stays
# internal — the shipped envelope is still ``CodeFactResult`` (above),
# unchanged. Publicly exposing ``Resolution`` itself is RED_TO_GREEN(a), out
# of scope here. This is the uniform provider protocol (D2/LA1-L2), the
# explicit ``Resolution`` sum (D3/LA1-L3) and the token-bounded per-query
# trace (D5/LA1-L9) the fold accumulates over an ordered provider tuple.
# ``TRACE_EXEMPLARS_MAX`` / ``TRACE_DETAIL_MAX_CHARS`` are owned here (the
# algebra module, D5).
# ---------------------------------------------------------------------------

TRACE_EXEMPLARS_MAX = 3
TRACE_DETAIL_MAX_CHARS = 200

#: The closed D3 cause set (ADR-LA-001 D3) — every ``Failed``/``failed:<cause>``
#: trace event's cause MUST be one of these; there is no reserve vocabulary.
D3_CAUSES: frozenset[str] = frozenset(
    {
        "unreadable-target",
        "unparseable-source",
        "out-of-scope-language",
        "provider-error",
        "provider-timeout",
    }
)

#: The closed ``TraceEntry.scope`` vocabulary (ADR-LA-001 D5, LA1-L9/L11).
_TRACE_SCOPE_VOCAB: frozenset[str] = frozenset({"complete", "filtered", "unfiltered"})

_CONFIDENCE_VALUES: frozenset[str] = frozenset(c.value for c in Confidence)


@dataclass(frozen=True)
class ManifestEntry:
    """One capability a provider declares it can attempt, at what confidence."""

    capability_id: str
    confidence: str

    def __post_init__(self) -> None:
        if not self.capability_id:
            raise ValueError("ManifestEntry.capability_id must be non-empty")
        if self.confidence not in _CONFIDENCE_VALUES:
            raise ValueError(
                f"ManifestEntry.confidence must be one of {sorted(_CONFIDENCE_VALUES)}"
            )


Manifest = tuple[ManifestEntry, ...]


@dataclass(frozen=True)
class TraceEntry:
    """One provider's bounded contribution to a query's trace (LA1-L9).

    ``event`` is ``attempted`` / ``answered`` / ``failed:<cause>``; a
    non-covering provider contributes no entry at all (LA1-L5 strict
    identity), so there is no ``skipped`` event to represent. The bounds
    (``exemplars`` <= :data:`TRACE_EXEMPLARS_MAX`, ``detail`` <=
    :data:`TRACE_DETAIL_MAX_CHARS` chars, ``fault_count`` nonnegative,
    ``provider_id`` non-empty) are enforced by construction — an
    out-of-bound entry can never exist, never merely be assumed bounded.
    """

    provider_id: str
    event: str
    scope: str
    fault_count: int
    exemplars: tuple[str, ...]
    detail: str

    def __post_init__(self) -> None:
        if not self.provider_id:
            raise ValueError("TraceEntry.provider_id must be non-empty")
        if self.fault_count < 0:
            raise ValueError("TraceEntry.fault_count must be nonnegative")
        if len(self.exemplars) > TRACE_EXEMPLARS_MAX:
            raise ValueError(
                f"TraceEntry.exemplars exceeds TRACE_EXEMPLARS_MAX={TRACE_EXEMPLARS_MAX}"
            )
        if len(self.detail) > TRACE_DETAIL_MAX_CHARS:
            raise ValueError(
                f"TraceEntry.detail exceeds TRACE_DETAIL_MAX_CHARS={TRACE_DETAIL_MAX_CHARS}"
            )
        if self.scope not in _TRACE_SCOPE_VOCAB:
            raise ValueError(
                f"TraceEntry.scope must be one of {sorted(_TRACE_SCOPE_VOCAB)}"
            )
        if self.event not in ("attempted", "answered") and not (
            self.event.startswith("failed:")
            and self.event.removeprefix("failed:") in D3_CAUSES
        ):
            raise ValueError(
                "TraceEntry.event must be 'attempted', 'answered', or "
                f"'failed:<cause>' with cause in {sorted(D3_CAUSES)}"
            )


@dataclass(frozen=True)
class Answered:
    """A terminal, usable answer — the first one absorbs the fold (LA1-L5)."""

    provider_id: str
    confidence: str
    payload: object
    trace: tuple[TraceEntry, ...]


@dataclass(frozen=True)
class Unsupported:
    """No provider in the composed tuple covers this capability at all."""

    capability_id: str
    consulted: tuple[str, ...]
    trace: tuple[TraceEntry, ...]


@dataclass(frozen=True)
class Failed:
    """Every covering provider failed; ``cause`` is deterministic (LA1-L10)."""

    cause: str
    trace: tuple[TraceEntry, ...]


Resolution = Answered | Unsupported | Failed


class CodeFactProvider(Protocol):
    """The uniform provider protocol every tier implements (D2/LA1-L2).

    ``manifest()`` is a static, argument-free coverage claim; ``resolve()``
    is total over the request's observed scope (LA1-L4) — it returns
    ``Failed`` rather than a partial ``Answered`` when it cannot observe the
    whole requested scope.
    """

    provider_id: str

    def manifest(self) -> Manifest:
        """Which capabilities this provider can attempt, at what confidence."""
        ...

    def resolve(
        self, descriptor: CapabilityDescriptor, request: Mapping[str, object]
    ) -> Answered | Failed:
        """Answer ``descriptor`` over ``request``, or fail with a named cause."""
        ...


def _manifest_entry(manifest: Manifest, capability_id: str) -> ManifestEntry | None:
    """The declared entry for ``capability_id`` in ``manifest``, or ``None``."""
    for entry in manifest:
        if entry.capability_id == capability_id:
            return entry
    return None


def _deterministic_cause(trace: tuple[TraceEntry, ...]) -> str:
    """LA1-L10: the cause of the first (highest-declared-confidence) failure.

    Only reached when at least one covering provider was consulted, and
    every covering provider contributes exactly one trace entry (LA1-L9,
    validated atomically in ``resolve_through_fold``) — so ``trace`` is
    non-empty by construction on this path and indexing ``[0]`` never
    crashes on an empty trace.
    """
    return trace[0].event.removeprefix("failed:")


def _provider_error_entry(provider_id: str, detail: str) -> TraceEntry:
    """One bounded ``failed:provider-error`` entry (LA1-L3 totality) — the
    fold's total answer for an unexpected provider ``Exception`` or a
    malformed ``Failed`` trace (empty / multiple / wrong-provider entries):
    the failure is normalized, never lost, never crashes the fold."""
    return TraceEntry(
        provider_id=provider_id,
        event="failed:provider-error",
        scope="complete",
        fault_count=1,
        exemplars=(),
        detail=detail[:TRACE_DETAIL_MAX_CHARS],
    )


def _is_well_formed_answered(
    provider_id: str, outcome: Answered, declared_confidence: str
) -> bool:
    """LA1-L1/L6/L9: a well-formed ``Answered`` is one atomic observation —
    self-tagged with the resolving provider, carrying exactly the
    manifest-declared confidence (no inflation), with exactly one
    correctly-tagged ``answered`` trace entry. A malformed ``Answered`` must
    never be branched on as a success (it is normalized to a failure by the
    caller instead)."""
    return (
        outcome.provider_id == provider_id
        and outcome.confidence == declared_confidence
        and len(outcome.trace) == 1
        and outcome.trace[0].provider_id == provider_id
        and outcome.trace[0].event == "answered"
    )


def _is_well_formed_failed(provider_id: str, outcome: Failed) -> bool:
    """LA1-L1/L9/L10: a well-formed ``Failed`` carries a closed-D3 ``cause``
    and exactly one correctly-tagged ``failed:<cause>`` trace entry whose
    event matches that cause."""
    return (
        outcome.cause in D3_CAUSES
        and len(outcome.trace) == 1
        and outcome.trace[0].provider_id == provider_id
        and outcome.trace[0].event == f"failed:{outcome.cause}"
    )


def resolve_through_fold(
    descriptor: CapabilityDescriptor,
    request: Mapping[str, object],
    providers: tuple[CodeFactProvider, ...],
) -> Resolution:
    """Fold ``providers`` (descending declared confidence) into one ``Resolution``.

    Zero ``isinstance`` / ``getattr`` / arity branching on provider identity
    (LA1-L2): every provider is consulted through the identical
    ``manifest()``/``resolve()`` shape. A non-covering provider contributes no
    trace entry at any position (LA1-L5 strict identity); the first
    ``Answered`` absorbs the fold; a ``Failed`` is recorded and the fold
    continues to the next covering provider (D5). Total over an unexpected
    provider ``Exception`` (LA1-L3): the fold never crashes and never drops
    the failure — one bounded ``failed:provider-error`` entry is appended and
    the fold continues, same as a malformed ``Failed`` trace. Also total over
    a malformed (non-``ManifestEntry``) manifest member and an alien
    ``resolve()`` return value (neither ``Answered`` nor a well-formed
    ``Failed``) — both normalize to the identical one-entry fallback, never
    trusted, never escaping.
    """
    trace: tuple[TraceEntry, ...] = ()
    consulted: list[str] = []
    for provider in providers:
        try:
            manifest_entry = _manifest_entry(provider.manifest(), descriptor.id)
        except Exception as exc:  # LA1-L3 totality: manifest() must not escape either
            consulted.append(provider.provider_id)
            trace = (*trace, _provider_error_entry(provider.provider_id, str(exc)))
            continue
        if manifest_entry is None:
            continue  # LA1-L5 strict identity: a non-covering manifest is noise-free
        if not isinstance(manifest_entry, ManifestEntry):
            # LA1-L1/L9 totality: a malformed manifest member (not a real
            # ManifestEntry — e.g. duck-typed, missing/invalid confidence) is
            # never trusted as a coverage claim. It is normalized to one
            # bounded provider-error entry and the fold falls through, same
            # as a raising manifest() — resolve() is never reached on it.
            consulted.append(provider.provider_id)
            trace = (
                *trace,
                _provider_error_entry(provider.provider_id, "malformed manifest entry"),
            )
            continue
        consulted.append(provider.provider_id)
        try:
            outcome = provider.resolve(descriptor, request)
        except Exception as exc:  # LA1-L3 totality: never crash, never lose the fault
            trace = (*trace, _provider_error_entry(provider.provider_id, str(exc)))
            continue
        if isinstance(outcome, Answered):
            if _is_well_formed_answered(
                provider.provider_id, outcome, manifest_entry.confidence
            ):
                return Answered(
                    provider_id=outcome.provider_id,
                    confidence=outcome.confidence,
                    payload=outcome.payload,
                    trace=(*trace, outcome.trace[0]),
                )
            # LA1-L1/L9: a malformed Answered can never become a success — it
            # is normalized to a failure and the fold continues (D3 totality).
            trace = (*trace, _provider_error_entry(provider.provider_id, ""))
            continue
        if isinstance(outcome, Failed) and _is_well_formed_failed(
            provider.provider_id, outcome
        ):
            trace = (*trace, outcome.trace[0])
        else:
            # LA1-L1/L3/L9 totality: an alien resolve() return — anything
            # that is neither Answered nor a well-formed Failed (None, a
            # bare string, a dict, ...) — is never branched on as either. It
            # is normalized to one bounded provider-error entry and the fold
            # falls through, same fallback as a malformed Failed trace.
            trace = (*trace, _provider_error_entry(provider.provider_id, ""))
    if not consulted:
        return Unsupported(
            capability_id=descriptor.id, consulted=tuple(consulted), trace=trace
        )
    return Failed(cause=_deterministic_cause(trace), trace=trace)


def verify_composition_coverage(providers: tuple[CodeFactProvider, ...]) -> None:
    """LA1-L8 (composition-time coverage totality): refuse to compose unless
    ``union(manifest(p) for p in providers)`` covers
    :data:`STABLE_CORE_CAPABILITY_IDS`. Called by a composition root (e.g.
    :class:`des.adapters.driven.codefact.code_fact_chain.CodeFactChain`) when
    it wires its provider tuple — coverage is *verified*, never inferred from
    "the floor happens to be present".
    """
    provider_ids = [provider.provider_id for provider in providers]
    invalid_ids = sorted(
        {
            provider_id
            for provider_id in provider_ids
            if not provider_id or provider_ids.count(provider_id) > 1
        }
    )
    if invalid_ids:
        raise ValueError(
            "WHAT: this provider composition has blank or duplicate "
            f"provider_id value(s) {invalid_ids}. "
            "WHY: LA1-L9's per-provider trace aggregation requires every "
            "composed provider_id to be non-empty and unique. "
            "HOW: give every composed provider a distinct, non-empty "
            "provider_id."
        )
    try:
        covered = {
            entry.capability_id
            for provider in providers
            for entry in provider.manifest()
        }
    except Exception as exc:  # LA1-L8: a raising manifest() must not escape composition
        raise ValueError(
            "WHAT: this provider composition could not be verified because a "
            f"manifest() call raised: {str(exc)[:TRACE_DETAIL_MAX_CHARS]}. "
            "WHY: LA1-L8 requires union(manifest(p) for p in providers) to be "
            "computable before composition-time coverage can be verified. "
            "HOW: fix the raising provider's manifest() to be a pure, "
            "argument-free coverage claim."
        ) from exc
    missing = STABLE_CORE_CAPABILITY_IDS - covered
    if missing:
        raise ValueError(
            "WHAT: this provider composition does not cover the stable-core "
            f"capability ids {sorted(missing)}. "
            "WHY: LA1-L8 requires union(manifest(p) for p in providers) to "
            "cover STABLE_CORE_CAPABILITY_IDS before a query can be trusted "
            "total for the stable core. "
            "HOW: wire a provider whose manifest declares the missing "
            "capability id(s) — e.g. the universal TextSearch floor."
        )
