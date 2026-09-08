"""``CodeFactChain`` — the provider-chain negotiation (ADR-LA-001 §5).

Walks the fallback chain ``Ast -> TextSearch`` top-down and returns the first
provider that *covers* the capability at the floor, tagging the answer
``{provider, confidence, reason_code}``. For a stable-core capability there is
NO "no provider" outcome — the universal :class:`TextSearchAdapter` floor
always answers (ADR-LA-001 §5).

* the :class:`AstAdapter` (``approx``) — the structural tier, always present on a
  parseable target.
* the :class:`TextSearchAdapter` (``noisy``) — the universal pure-Python floor,
  always present.

ADR-LA-001 D6-R1 / D9 RED_TO_GREEN(b): the paid ``TsunamiAdapter`` stub (a
fabricated ``binding-resolved`` precision tier no production caller ever
wired) and its ``tsunami_present`` ctor flag, ``tsunami-absent`` skip event,
and mutable ``_health_events``/``health_events()`` side channel are DELETED —
they are unrepresentable in OSS (LA1-L7: a ``binding-resolved`` answer
requires a real ``TransportWitness``). The per-query, immutable
``Resolution.trace`` (D5, LA1-L9) is the ONLY diagnostic projection left; a
caller reads scan-scope honesty (``complete`` / ``filtered`` / ``unfiltered``)
directly off the answering ``TraceEntry.scope``, never off a side channel.

The chain holds no mutable state: :meth:`resolve` is a pure fold over its
composed provider tuple, so long-lived and concurrent reuse is safe by
construction (D5).

The chain is the seam a code-fact gate re-derives a fact THROUGH (one honest
provider) instead of a per-gate hand-rolled ``import ast`` — so a gate's answer is
tagged with which provider produced it and at what declared confidence, never a
hallucinated claim.
"""

from __future__ import annotations

import dataclasses
from typing import TYPE_CHECKING

from des.adapters.driven.codefact.ast_code_fact_adapter import AstAdapter
from des.adapters.driven.codefact.graphify_code_fact_adapter import GraphifyAdapter
from des.adapters.driven.codefact.text_search_code_fact_adapter import TextSearchAdapter
from des.ports.code_fact_port import (
    Answered,
    resolve_through_fold,
    verify_composition_coverage,
)


if TYPE_CHECKING:
    from pathlib import Path

    from des.ports.code_fact_port import (
        CapabilityDescriptor,
        CodeFactResult,
        Resolution,
    )


class CodeFactChain:
    """The composition that walks the provider chain and tags the answer.

    Constructed with the ``root`` of the tree to query. The chain wires
    ``Graphify -> Ast -> TextSearch`` in descending precision and returns
    the first provider that *covers* the capability — a pure, stateless
    fold (D5); no mutable per-instance diagnostic channel, only the
    per-query ``Resolution.trace``.

    ``GraphifyAdapter`` (ADR-LA-001 D4/LA1-L7 — the "future precise
    provider" the ADR itself anticipated) is a WIRING decision, not a port
    change: it is only ever a member of ``self._providers`` when a real,
    parseable ``graphify-out`` pair was found under ``root`` at
    construction time (``has_data``) — absent ⇒ not in the tuple at all,
    the OSS normal case, never a phantom tier that always fails.

    This wires the PREFIX of ADR-LA-001's canonical reference chain,
    ``Tsunami -> Graphify -> Ast -> TextSearch``, that has a real provider
    today. ``Tsunami``'s slot is declared in the ADR amendment, not wired
    here — D6-R1's lesson stands (no fabricated ``binding-resolved`` stub);
    a future real Tsunami integration prepends above ``GraphifyAdapter`` the
    same way this adapter itself was added: a real ``TransportWitness``, a
    wiring change, no port/fold change.
    """

    def __init__(self, root: Path | str) -> None:
        self._graphify = GraphifyAdapter(root=root)
        self._ast = AstAdapter(root=root)
        self._floor = TextSearchAdapter(root=root)
        providers: list = []
        if self._graphify.has_data:
            providers.append(self._graphify)
        providers.append(self._ast)
        providers.append(self._floor)
        self._providers = tuple(providers)
        verify_composition_coverage(self._providers)

    def resolve(
        self, descriptor: CapabilityDescriptor, request: dict[str, object]
    ) -> Resolution:
        """Re-derive the fact THROUGH the port chain (one honest provider).

        ADR-LA-001 D9: one ``resolve_through_fold`` over the whole
        ``(Ast, TextSearch)`` tuple (D2/D5) — no provider-specific dispatch,
        no ``isinstance`` / ``getattr`` / arity branching on provider
        identity (LA1-L2). A pure fold: no side effects, no mutable state
        (concurrency-safe by construction) for the FRESH case, unchanged.

        F-GRAPHIFY-STALE-DEGRADES-SILENTLY (Ale, 2026-08-24): when
        ``GraphifyAdapter`` is present but its data is stale for THIS
        request, it is given one chance to regenerate SYNCHRONOUSLY
        before the fold runs at all. A regeneration failure (the tool is
        absent, the subprocess errors, or the graph is still stale
        afterward) returns ``Failed`` HERE, short-circuiting the rest of
        this method entirely -- ``resolve_through_fold`` is never called,
        so ``AstAdapter``/``TextSearchAdapter`` never get a chance to
        answer underneath a stale-but-unrepaired graph. This is the one
        deliberate exception to "the fold has no side effects": the
        side effect (regeneration) happens strictly BEFORE the fold, and
        only for the one provider/cause this remedy targets --
        ``resolve_through_fold``'s own generic ``Failed`` -> ``continue``
        semantics for every OTHER provider/cause are untouched.

        Returns the full ``Resolution`` so a caller needing the bounded
        trace alongside the answer can read both off one fold; :meth:`query`
        is the thin legacy edge over this same operation.
        """
        if not self._graphify.has_data:
            trace_entry = self._graphify.non_answer_trace_entry(descriptor)
            if trace_entry is not None:
                return self._fold_with_prepended_trace(descriptor, request, trace_entry)
            return resolve_through_fold(descriptor, request, self._providers)
        trace_entry = self._graphify.executable_missing_trace_entry(descriptor, request)
        if trace_entry is not None:
            return self._fold_with_prepended_trace(descriptor, request, trace_entry)
        regen_failure = self._graphify.ensure_fresh_or_fail(descriptor, request)
        if regen_failure is not None:
            return regen_failure
        return resolve_through_fold(descriptor, request, self._providers)

    def _fold_with_prepended_trace(
        self,
        descriptor: CapabilityDescriptor,
        request: dict[str, object],
        entry,
    ) -> Resolution:
        """Fold over ``(self._ast, self._floor)`` only -- graphify is never
        asked to :meth:`resolve` a second time for the same request -- and
        return the fold's ``Resolution`` reconstructed with ``entry``
        PREPENDED to its trace tuple. ``Answered``/``Unsupported``/``Failed``
        are frozen dataclasses, so this is a new instance carrying the SAME
        provider_id/confidence/payload/cause/evidence_count the fold
        produced, only the trace tuple gains the one leading entry."""
        resolution = resolve_through_fold(descriptor, request, (self._ast, self._floor))
        return dataclasses.replace(resolution, trace=(entry, *resolution.trace))

    def query(
        self, descriptor: CapabilityDescriptor, request: dict[str, object]
    ) -> CodeFactResult | None:
        """Re-derive the fact THROUGH the port chain (one honest provider).

        For a stable-core capability the universal floor always covers it, so
        this always answers (``Unsupported``/``Failed`` render ``None`` — no
        answer faked)."""
        resolution = self.resolve(descriptor, request)
        if not isinstance(resolution, Answered):
            return None
        return resolution.payload
