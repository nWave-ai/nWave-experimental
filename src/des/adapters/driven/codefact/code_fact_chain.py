"""``CodeFactChain`` — the provider-chain negotiation (ADR-LA-001 §5).

Walks the fallback chain ``Tsunami -> Ast -> TextSearch`` top-down and returns the
first provider that *covers* the capability at the floor, tagging the answer
``{provider, confidence, reason_code}``. For a stable-core capability there is NO
"no provider" outcome — the universal :class:`TextSearchAdapter` floor (and the
structural :class:`AstAdapter`) always answer (ADR-LA-001 §5).

slice-01 (the walking skeleton) wired ONLY the floor. slice-02 prepends the two
precision tiers ahead of it:

* the :class:`AstAdapter` (``approx``) — the structural tier, always present on a
  parseable target.
* the :class:`TsunamiAdapter` (``binding-resolved``) — the paid open-core tier,
  wired only when its ``probe()`` passes (``ADR-LA-001`` §3, Earned-Trust). On a
  plain Python-only target it is ABSENT (the NORMAL case): the chain SKIPS it
  LOUDLY — emitting a ``health.gate.code-fact.*`` skip event — and PROCEEDS to the
  next tier (degrade-LOUD, never silent-fail, never a hang).

A capability only the paid tier can honor (outside the LOCKED 5-capability stable
core, e.g. ``query.tsunami-call-graph``) with Tsunami ABSENT is SKIPPED LOUDLY and
the gate PROCEEDS (C8) — the chain does NOT block on Tsunami absence and does NOT
fabricate a lower-tier answer for a capability only Tsunami can honor.

The chain is the seam a code-fact gate re-derives a fact THROUGH (one honest
provider) instead of a per-gate hand-rolled ``import ast`` — so a gate's answer is
tagged with which provider produced it and at what declared confidence, never a
hallucinated claim.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from des.adapters.driven.codefact.ast_code_fact_adapter import AstAdapter
from des.adapters.driven.codefact.text_search_code_fact_adapter import TextSearchAdapter
from des.adapters.driven.codefact.tsunami_code_fact_adapter import TsunamiAdapter


if TYPE_CHECKING:
    from pathlib import Path

    from des.ports.code_fact_port import (
        CapabilityDescriptor,
        CodeFactResult,
    )


# The LOUD-skip health-event family (ADR-LA-001 §5a). A skip event whose name
# carries this prefix is the degrade-LOUD observable a gate reads off the chain.
_HEALTH_SKIP_PREFIX = "health.gate.code-fact"
# The specific LOUD-skip event the chain emits when it skips the absent paid tier.
_TSUNAMI_ABSENT_SKIP = f"{_HEALTH_SKIP_PREFIX}.tsunami-absent"


class CodeFactChain:
    """The composition that walks the provider chain and tags the answer.

    Constructed with the ``root`` of the tree to query and whether the paid Tsunami
    tier is present (``tsunami_present``; ``False`` is the normal OSS case). The
    chain wires ``Tsunami -> Ast -> TextSearch`` in descending precision and returns
    the first provider that *covers* the capability — emitting a LOUD
    ``health.gate.code-fact.*`` skip event when it skips the absent paid tier.
    """

    def __init__(self, root: Path | str, tsunami_present: bool = False) -> None:
        self._tsunami = TsunamiAdapter(root=root, present=tsunami_present)
        self._ast = AstAdapter(root=root)
        self._floor = TextSearchAdapter(root=root)
        self._health_events: list[str] = []

    def query(
        self, descriptor: CapabilityDescriptor, request: dict[str, object]
    ) -> CodeFactResult | None:
        """Re-derive the fact THROUGH the port chain (one honest provider).

        Walks the chain top-down. The paid Tsunami tier is consulted only if its
        ``probe`` passes; an absent paid tier is SKIPPED LOUDLY (a
        ``health.gate.code-fact.*`` event) and the chain PROCEEDS. A stable-core
        capability is then answered by the structural floor tiers. A Tsunami-only
        capability with Tsunami absent has no covering lower tier: it returns
        ``None`` (no answer faked) while the loud skip is recorded and the gate
        proceeds (C8).
        """
        if self._tsunami.probe():
            return self._tsunami.query(descriptor, request)
        self._record_tsunami_skip()
        return self._negotiate_floor_tiers(descriptor, request)

    def health_events(self) -> list[str]:
        """The LOUD ``health.gate.code-fact.*`` skip events the chain emitted.

        Read by a gate to observe a degrade-LOUD skip (the paid tier was absent).
        Empty when no tier was skipped (e.g. the paid tier was present).
        """
        return list(self._health_events)

    # -- negotiation internals --------------------------------------------

    def _negotiate_floor_tiers(
        self, descriptor: CapabilityDescriptor, request: dict[str, object]
    ) -> CodeFactResult | None:
        """The first non-paid tier whose manifest COVERS the capability (Ast, floor).

        Walks ``Ast -> TextSearch`` and returns the first tier whose ``probe``
        manifest lists the capability — the structural ``AstAdapter`` (``approx``)
        wins for a stable-core capability, the universal ``TextSearchAdapter`` floor
        is the always-present fallback. A Tsunami-only capability is in NEITHER
        manifest, so no lower tier is dressed up as covering it: the walk returns
        ``None`` (the loud skip is already recorded; the gate proceeds, C8).
        """
        for tier in (self._ast, self._floor):
            if self._covers(tier, descriptor.id):
                return tier.query(descriptor, request)
        return None

    @staticmethod
    def _covers(tier: object, capability_id: str) -> bool:
        """True iff ``tier``'s ``probe`` manifest lists ``capability_id`` as ``ok``."""
        probe = getattr(tier, "probe", None)
        manifest = probe() if callable(probe) else ()
        return any(
            entry.get("capability_id") == capability_id and entry.get("ok")
            for entry in manifest
        )

    def _record_tsunami_skip(self) -> None:
        """Emit the LOUD skip event for the absent paid tier (degrade-LOUD)."""
        self._health_events.append(_TSUNAMI_ABSENT_SKIP)
