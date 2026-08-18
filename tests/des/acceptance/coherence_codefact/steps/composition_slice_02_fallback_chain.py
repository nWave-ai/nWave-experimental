"""Composition root for the f-coherence-and-attestation slice-02 ATs.

Mandate-13 driving-port-only (Layer 3 composition): each behaviour is driven
through the REAL production seam the slice-02 Code-Design pins -- the
``AstAdapter`` / the full ``CodeFactChain`` negotiation (``Ast -> TextSearch``)
via the production composition root -- built via lazy import inside the
driving-port invocation. No production module is imported-and-called at the
step boundary for its business logic; the step bodies (in ``test_slice_02_*``)
delegate to these composition methods (Mandate-12 -- no logic in step bodies).

ADR-LA-001 D6-R1 / D9 RED_TO_GREEN(b): the paid Tsunami tier was a fabricated
precision stub no production caller ever wired (LA1-L7: a
``binding-resolved`` answer requires a real ``TransportWitness``, which OSS
ships none of). Its scenarios (a fictional ``present`` counter-case, a
``tsunami-absent`` skip event, a Tsunami-only capability skip) are deleted
with the stub -- this composition drives only the real, GREEN
``AstAdapter`` + ``CodeFactChain`` (``Ast -> TextSearch``) surface.

DRIVING SURFACE: the SEAM / the ``CodeFactResult`` envelope (provider /
confidence / reason_code / payload) / the chain's provider-selection --
NEVER a line number.

DESIGN-CONTRACT ASSUMPTION A1 (AstAdapter ctor): the slice-02 Code-Design pins
``AstAdapter`` at ``src/des/adapters/driven/codefact/ast_code_fact_adapter.py``
delegating to the ``TestSuiteAstAdapter`` Protocol; this composition
constructs it with ``root=<tree>`` (mirroring the shipped
``TextSearchAdapter(root=...)`` sibling / the shipped ``CodeFactChain(root=...)``
ctor). If a future DELIVER ships a different ctor, update THIS single
invocation (``_query_ast`` / ``_query_chain``) -- the SEAM, not a line number.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from .domain_types_coherence_codefact import (
    LOCKED_CONFIDENCES,
    LOCKED_PROVIDERS,
    CapabilityId,
    Confidence,
    Provider,
)
from .domain_types_slice_02_fallback_chain import ChainObservable, ChainScope


# Sentinel an absent driving-seam import records, so the Then can name the
# missing observable instead of letting an ImportError escape as a collection
# error / silent green.
_SEAM_ABSENT = "__SEAM_ABSENT__"


@dataclass
class FallbackChainComposition:
    """Drives the slice-02 fallback-chain seams through their REAL driving surface."""

    # AT-1 (AstAdapter) observable
    _capability: CapabilityId | None = field(default=None)

    # AT-2 (chain) observable
    _scope: ChainScope | None = field(default=None)

    _observable: ChainObservable | None = field(default=None)
    _seam_error: str | None = field(default=None)

    # =====================================================================
    # AT-1 -- the AstAdapter answers a stable-core capability structurally
    #         at `approx` (REUSING testarch python_ast.py, never a 2nd parser)
    # =====================================================================

    def given_capability_required(self, capability: CapabilityId) -> None:
        """Arm which LOCKED stable-core capability the AstAdapter must answer."""
        self._capability = capability

    def when_ast_adapter_answers_via_port(self, tmp_path: Path) -> None:
        """Drive the REAL AstAdapter THROUGH the CodeFactPort over a real tree.

        Builds a tiny real Python tree, then asks the AstAdapter for the armed
        stable-core capability via the port's ``query``. The observable is the
        ``CodeFactResult`` envelope -- it must come back provider=``ast`` @
        confidence=``approx`` (the structural tier; never the floor's ``noisy``).
        """
        assert self._capability is not None
        tree = self._write_python_tree(tmp_path)
        self._observable = self._query_ast(self._capability, tree)

    # =====================================================================
    # AT-2 -- the full chain negotiation returns the FIRST provider covering
    #         the capability at the floor (Ast `approx`)
    # =====================================================================

    def given_chain_scope(self, scope: ChainScope) -> None:
        """Arm which capability class the chain query targets."""
        self._scope = scope

    def when_chain_negotiates(self, tmp_path: Path) -> None:
        """Drive the REAL CodeFactChain negotiation over a real tree.

        Walks ``Ast -> TextSearch`` and returns the first provider covering
        the capability at the floor, tagging ``{provider, confidence,
        reason_code}``. A stable-core capability is answered by the Ast tier
        (``approx``).
        """
        scope = self._scope or ChainScope.STABLE_CORE
        tree = self._write_python_tree(tmp_path)
        self._observable = self._query_chain(tree, scope)

    # ---- observable readers (Then) --------------------------------------

    def then_a_usable_answer_came_back(self) -> None:
        """The chain ALWAYS answers a stable-core capability (degrade, never refuse)."""
        obs = self._require_observable()
        assert obs.answered, (
            f"the CodeFactChain must ALWAYS return a usable answer for a stable-core "
            f"capability (degrade down the tiers, never refuse) -- got no usable "
            f"answer. {self._observed()}"
        )

    def then_provider_is_ast_at_approx(self) -> None:
        """The AstAdapter tier answers provider=ast @ confidence=approx."""
        obs = self._require_observable()
        assert obs.provider == Provider.AST.value, (
            f"the AstAdapter must tag its answer provider={Provider.AST.value!r} "
            f"(the structural tier) -- got provider={obs.provider!r}. "
            f"{self._observed()}"
        )
        assert obs.confidence == Confidence.APPROX.value, (
            f"the AstAdapter must declare its TRUE structural confidence "
            f"{Confidence.APPROX.value!r} -- never the floor's 'noisy' -- got "
            f"confidence={obs.confidence!r}. {self._observed()}"
        )

    def then_provenance_tokens_are_locked(self) -> None:
        """The answering tier's provider+confidence are LOCKED cross-tier tokens."""
        obs = self._require_observable()
        assert obs.provider in LOCKED_PROVIDERS, (
            f"the answering provider token must be one of the cross-tier-LOCKED set "
            f"{sorted(LOCKED_PROVIDERS)!r} (ADR-LA-001 §5a) -- got "
            f"provider={obs.provider!r}. {self._observed()}"
        )
        assert obs.confidence in LOCKED_CONFIDENCES, (
            f"the answering confidence token must be one of the cross-tier-LOCKED "
            f"set {sorted(LOCKED_CONFIDENCES)!r} (ADR-LA-001 §5a) -- got "
            f"confidence={obs.confidence!r}. {self._observed()}"
        )

    # =====================================================================
    # driving-port invocations (lazy seam import -> sentinel on absence)
    # =====================================================================

    def _query_ast(self, capability: CapabilityId, tree: Path) -> ChainObservable:
        """Drive the REAL AstAdapter through the REAL CodeFactPort (assumption A1)."""
        try:
            from des.adapters.driven.codefact.ast_code_fact_adapter import (
                AstAdapter,
            )
            from des.ports.code_fact_port import (
                CapabilityDescriptor,
                CodeFactPort,
            )
        except (ImportError, ModuleNotFoundError):
            self._seam_error = _SEAM_ABSENT
            return self._absent_observable()

        adapter: CodeFactPort = AstAdapter(root=tree)
        descriptor = CapabilityDescriptor(
            id=capability.value,
            stability="stable",
            contract_version="1.0.0",
            io_schema=capability.value,
            providing_adapter=Provider.AST.value,
        )
        result = adapter.query(
            descriptor, {"symbol": "CacheWriter.flush", "root": str(tree)}
        )
        return self._envelope_observable(result)

    def _query_chain(self, tree: Path, scope: ChainScope) -> ChainObservable:
        """Drive the REAL full CodeFactChain negotiation (assumption A1)."""
        try:
            from des.adapters.driven.codefact.code_fact_chain import (
                CodeFactChain,
            )
            from des.ports.code_fact_port import (
                CapabilityDescriptor,
            )
        except (ImportError, ModuleNotFoundError):
            self._seam_error = _SEAM_ABSENT
            return self._absent_observable()

        chain = CodeFactChain(root=tree)
        # The scope is always STABLE_CORE (ChainScope's only member); the
        # negotiation always targets the LOCKED never-wired capability -- the
        # `<capability>` Examples column parametrizes the Gherkin's prose, not
        # which capability the chain negotiates over (all three examples
        # exercise the identical Ast-answers-first negotiation path).
        assert scope is ChainScope.STABLE_CORE
        capability_id = CapabilityId.NEVER_WIRED.value
        descriptor = CapabilityDescriptor(
            id=capability_id,
            stability="stable",
            contract_version="1.0.0",
            io_schema=capability_id,
            providing_adapter=Provider.AST.value,
        )
        result = chain.query(descriptor, {"symbol": "CacheWriter.flush"})
        return self._envelope_observable(result)

    # =====================================================================
    # envelope reader + absent-seam observable
    # =====================================================================

    def _envelope_observable(self, result: object) -> ChainObservable:
        """Read the port-exposed {provider, confidence, reason_code} + answered."""
        provider = self._token(getattr(result, "provider", None))
        confidence = self._token(getattr(result, "confidence", None))
        reason_code = self._token(getattr(result, "reason_code", None))
        payload = getattr(result, "payload", None)
        return ChainObservable(
            answered=payload is not None,
            provider=provider,
            confidence=confidence,
            reason_code=reason_code,
        )

    def _absent_observable(self) -> ChainObservable:
        """The seam is absent -> no observable; the Then names it."""
        return ChainObservable(
            answered=False,
            provider=None,
            confidence=None,
            reason_code=None,
        )

    @staticmethod
    def _token(value: object) -> str | None:
        """Coerce an enum-or-str port value to its wire token (or None)."""
        if value is None:
            return None
        return getattr(value, "value", value)

    # =====================================================================
    # substrate plumbing
    # =====================================================================

    def _write_python_tree(self, tmp_path: Path) -> Path:
        """A tiny real Python source tree the AstAdapter / chain parse (real I/O).

        Defines a net-new effectful symbol ``CacheWriter.flush`` WITH a production
        call-site, so a structural (Ast) answer is a non-vacuous, observable
        difference from the textual floor.
        """
        root = tmp_path / "ast_probe_tree" / "src"
        root.mkdir(parents=True, exist_ok=True)
        (root / "cache_writer.py").write_text(
            "class CacheWriter:\n"
            "    def flush(self) -> None:\n"
            "        self._buffer.clear()\n",
            encoding="utf-8",
        )
        (root / "service.py").write_text(
            "from .cache_writer import CacheWriter\n\n"
            "def run() -> None:\n"
            "    CacheWriter().flush()\n",
            encoding="utf-8",
        )
        return root

    # =====================================================================
    # diagnostics
    # =====================================================================

    def _require_observable(self) -> ChainObservable:
        if self._observable is None or self._seam_error == _SEAM_ABSENT:
            raise AssertionError(
                "the slice-02 fallback-chain seams (the AstAdapter @ 'approx' "
                "REUSING testarch/adapters/python_ast.py + the full CodeFactChain "
                "'Ast -> TextSearch' negotiation) must exist and return a tagged "
                "CodeFactResult envelope -- the seam is ABSENT at HEAD "
                "(src/des/adapters/driven/codefact/ast_code_fact_adapter.py + "
                "code_fact_chain.py). "
                f"{self._observed()}"
            )
        return self._observable

    def _observed(self) -> str:
        cap = self._capability.value if self._capability else None
        return (
            f"capability={cap!r}; scope={self._scope!r}; "
            f"observable={self._observable!r}; seam_error={self._seam_error!r}"
        )
