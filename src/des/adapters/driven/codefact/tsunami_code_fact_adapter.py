"""``TsunamiAdapter`` — the paid-tier precision seam (ADR-LA-001 §5 tier 1).

The head of the CodeFact fallback chain and the most precise provider:
``binding-resolved`` confidence (a resolved-binding structural fact, not a
syntactic ``approx`` nor a textual ``noisy`` guess). It is the **paid open-core
seam** — wired into the chain ONLY when its :meth:`probe` passes. On a plain
Python-only target the paid transport is absent (the NORMAL case, ADR-LA-001 C7),
``probe`` returns ``False``, and the chain degrades LOUD to the next tier.

The transport (how Tsunami resolves bindings) is an L4-deferred implementation
detail (ADR-LA-001 L4); the OSS port assumes NO transport. This module ships the
SEAM — the ``probe`` gate + the ``binding-resolved``-tagged envelope shape — so the
chain can wire and negotiate the tier; an OSS install never has a passing default
probe (``present=False`` by construction), so the paid tier is honestly absent
unless a paid adapter is injected with ``present=True``.

Earned-Trust (Principle 13): wire → **probe** → use. The chain never assumes the
paid tier; it asks ``probe`` first and only consults this adapter when it answers.
"""

from __future__ import annotations

from pathlib import Path

from des.ports.code_fact_port import (
    CapabilityDescriptor,
    CodeFactResult,
    Confidence,
    Provider,
)


class TsunamiAdapter:
    """Paid-tier ``CodeFactPort`` seam; present only when its probe passes.

    Constructed with the ``root`` of the tree and an explicit ``present`` flag
    standing in for the paid transport's availability. On an OSS-only target the
    transport is absent, so ``present`` defaults to ``False`` and :meth:`probe`
    reports the tier ABSENT — the chain then degrades LOUD past it. A paid
    deployment injects ``present=True`` (and, in a real install, a transport);
    only then does :meth:`query` produce a ``binding-resolved`` answer.
    """

    confidence = Confidence.BINDING_RESOLVED.value
    provider = Provider.TSUNAMI.value

    def __init__(self, root: Path | str, present: bool = False) -> None:
        self._root = Path(root)
        self._present = present

    # -- Earned-Trust gate -------------------------------------------------

    def probe(self) -> bool:
        """Whether the paid Tsunami transport is available on this target.

        ``False`` on a plain Python-only target (the NORMAL case) — the chain reads
        this and SKIPS the tier LOUDLY, degrading to the next provider. ``True``
        only when a paid transport is wired (``present=True``).
        """
        return self._present

    # -- the CodeFactPort surface ------------------------------------------

    def query(
        self, descriptor: CapabilityDescriptor, request: dict[str, object]
    ) -> CodeFactResult:
        """Answer ``descriptor`` precisely (``binding-resolved``) — paid tier only.

        Called only after :meth:`probe` passes (the chain's Earned-Trust gate).
        Returns the precise structural fact tagged ``tsunami`` @
        ``binding-resolved``. The transport that resolves the binding is the
        L4-deferred paid impl; this seam ships the precise-tagged envelope shape the
        chain head consumes.
        """
        symbol = self._symbol_of(request)
        return CodeFactResult(
            provider=self.provider,
            confidence=self.confidence,
            payload={"symbol": symbol, "capability": descriptor.id, "resolved": True},
            reason_code=None,
        )

    @staticmethod
    def _symbol_of(request: dict[str, object]) -> str:
        """The symbol/anchor the request targets (``symbol`` or ``anchor`` fallback)."""
        for key in ("symbol", "anchor", "name"):
            value = request.get(key)
            if isinstance(value, str) and value:
                return value
        return ""
