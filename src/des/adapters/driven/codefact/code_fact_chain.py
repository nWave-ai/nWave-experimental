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

from typing import TYPE_CHECKING

from des.adapters.driven.codefact.ast_code_fact_adapter import AstAdapter
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
    ``Ast -> TextSearch`` in descending precision and returns the first
    provider that *covers* the capability — a pure, stateless fold (D5); no
    mutable per-instance diagnostic channel, only the per-query
    ``Resolution.trace``.
    """

    def __init__(self, root: Path | str) -> None:
        self._ast = AstAdapter(root=root)
        self._floor = TextSearchAdapter(root=root)
        self._providers = (self._ast, self._floor)
        verify_composition_coverage(self._providers)

    def resolve(
        self, descriptor: CapabilityDescriptor, request: dict[str, object]
    ) -> Resolution:
        """Re-derive the fact THROUGH the port chain (one honest provider).

        ADR-LA-001 D9: one ``resolve_through_fold`` over the whole
        ``(Ast, TextSearch)`` tuple (D2/D5) — no provider-specific dispatch,
        no ``isinstance`` / ``getattr`` / arity branching on provider
        identity (LA1-L2). A pure fold: no side effects, no mutable state
        (concurrency-safe by construction). Returns the full ``Resolution``
        so a caller needing the bounded trace alongside the answer can read
        both off one fold; :meth:`query` is the thin legacy edge over this
        same operation.
        """
        return resolve_through_fold(descriptor, request, self._providers)

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
