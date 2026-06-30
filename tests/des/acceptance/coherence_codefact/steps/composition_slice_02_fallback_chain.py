"""Composition root for the f-coherence-and-attestation slice-02 ATs.

Mandate-13 driving-port-only (Layer 3 composition): each behaviour is driven
through the REAL production seam the slice-02 Code-Design pins -- the
``AstAdapter`` / the full ``CodeFactChain`` negotiation (``Tsunami -> Ast ->
TextSearch``) via the production composition root -- built via lazy import inside
the driving-port invocation. No production module is imported-and-called at the
step boundary for its business logic; the step bodies (in ``test_slice_02_*``)
delegate to these composition methods (Mandate-12 -- no logic in step bodies).

active-RED scaffold (atdd_pure -- NOT @skip): at HEAD the slice-02 seams are
ABSENT / floor-only:
  * ``src/des/adapters/driven/codefact/ast_code_fact_adapter.py``    (AstAdapter,
    confidence ``approx``, REUSES ``testarch/adapters/python_ast.py``) -- ABSENT.
  * ``src/des/adapters/driven/codefact/tsunami_code_fact_adapter.py`` (TsunamiAdapter,
    paid seam, confidence ``binding-resolved``) -- ABSENT.
  * ``CodeFactChain`` -- ships FLOOR-ONLY at slice-01 (it wires only the
    TextSearchAdapter); slice-02 EXTENDS it to the full ``Tsunami -> Ast ->
    TextSearch`` negotiation that walks down tiers, declares each tier's
    confidence, degrades LOUD when a tier is absent, and SKIPS a Tsunami-only
    capability LOUDLY (``health.gate.code-fact.*`` event) while the gate PROCEEDS.
Each driving-port invocation captures the absent / not-yet-extended seam as a
sentinel; the ``Then`` reads the observable and fires a NAMED semantic
``AssertionError`` (the expected observable is missing because the seam is
unbuilt) -- never a collection / import / setup error. GREEN once DELIVER lands
the AstAdapter + TsunamiAdapter seam + the full chain negotiation.

DRIVING SURFACE: the SEAM / the ``CodeFactResult`` envelope (provider /
confidence / reason_code / payload) / the chain's provider-selection / the chain's
LOUD-skip signal -- NEVER a line number.

DESIGN-CONTRACT ASSUMPTIONS flagged to DELIVER (state-here-so-DELIVER-matches):
  A1 (AstAdapter ctor): the slice-02 Code-Design pins ``AstAdapter`` at
     ``src/des/adapters/driven/codefact/ast_code_fact_adapter.py`` delegating to
     the ``TestSuiteAstAdapter`` Protocol, but does NOT fix the ctor signature.
     This composition constructs it with ``root=<tree>`` (mirroring the shipped
     ``TextSearchAdapter(root=...)`` sibling). If DELIVER ships a different ctor
     (e.g. injecting a ``PythonAstAdapter`` parser instance), update THIS single
     invocation (``_query_ast``) -- the SEAM, not a line number.
  A2 (Tsunami probe seam): the chain wires the ``TsunamiAdapter`` only when its
     ``probe()`` passes (``ADR-LA-001`` §3; absence is the NORMAL case). The
     PRESENT case is driven via a chain ctor flag / injected probe-double; this
     composition asks the chain to wire a stub Tsunami when present. If DELIVER's
     chain takes a different injection shape, update ``_query_chain``.
  A3 (LOUD-skip observable / health-event seam): the chain must surface a LOUD
     ``health.gate.code-fact.*`` skip signal when a tier is skipped because it is
     absent (degrade-LOUD, ``ADR-LA-001`` §5a / C8). The DESIGN names the EVENT
     but not the accessor; this composition reads the chain's emitted health/skip
     events via whichever of ``health_events`` / ``skip_events`` /
     ``code_fact_health_events`` the chain exposes (a list of event dicts /
     strings). If DELIVER names the accessor differently, update
     ``_read_loud_skip`` -- the SEAM (the emitted event), not a line number.
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
from .domain_types_slice_02_fallback_chain import (
    ChainObservable,
    ChainScope,
    TsunamiPresence,
)


# Sentinel an absent / not-yet-extended seam invocation records, so the Then can
# name the missing observable instead of letting an ImportError or a floor-only
# chain escape as a collection error / silent green.
_SEAM_ABSENT = "__SEAM_ABSENT__"

# A premium capability only the paid Tsunami tier honors (NOT in the LOCKED
# stable-core). With Tsunami absent the chain SKIPS it LOUDLY + PROCEEDS (C8).
_TSUNAMI_ONLY_CAPABILITY = "query.tsunami-call-graph"

# The health-event surface family the chain emits a LOUD skip on (ADR-LA-001 §5a).
_HEALTH_SKIP_PREFIX = "health.gate.code-fact"


@dataclass
class FallbackChainComposition:
    """Drives the slice-02 fallback-chain seams through their REAL driving surface."""

    # AT-1 (AstAdapter) observable
    _capability: CapabilityId | None = field(default=None)

    # AT-2/AT-3/AT-4 (chain) observable
    _tsunami: TsunamiPresence | None = field(default=None)
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
        confidence=``approx`` (the structural tier; never the floor's ``noisy``,
        never a faked ``binding-resolved``).
        """
        assert self._capability is not None
        tree = self._write_python_tree(tmp_path)
        self._observable = self._query_ast(self._capability, tree)

    # =====================================================================
    # AT-2 -- the full chain negotiation returns the FIRST provider covering
    #         the capability at the floor (Tsunami absent -> Ast `approx`)
    # AT-3 -- Tsunami ABSENT degrades LOUD: the chain SKIPS Tsunami loudly and
    #         PROCEEDS to the next tier (not silent-fail, not a hang)
    # AT-4 -- C8: a Tsunami-only capability + Tsunami ABSENT -> SKIP LOUDLY
    #         (health.gate.code-fact.* event) + the gate PROCEEDS
    # =====================================================================

    def given_tsunami_presence(self, presence: TsunamiPresence) -> None:
        """Arm whether the paid Tsunami tier is wired (PRESENT) or absent (NORMAL)."""
        self._tsunami = presence

    def given_chain_scope(self, scope: ChainScope) -> None:
        """Arm whether the chain query targets a stable-core or Tsunami-only capability."""
        self._scope = scope

    def when_chain_negotiates(self, tmp_path: Path) -> None:
        """Drive the REAL CodeFactChain negotiation over a real tree.

        Walks ``Tsunami -> Ast -> TextSearch`` and returns the first provider
        covering the capability at the floor, tagging ``{provider, confidence,
        reason_code}``. With Tsunami ABSENT (the normal case) a stable-core
        capability is answered by the Ast tier (``approx``); a Tsunami-only
        capability is SKIPPED LOUDLY (``health.gate.code-fact.*``) while the gate
        PROCEEDS (C8). The observable is the tagged envelope + the loud-skip
        signal + whether the gate proceeded.
        """
        assert self._tsunami is not None
        scope = self._scope or ChainScope.STABLE_CORE
        tree = self._write_python_tree(tmp_path)
        self._observable = self._query_chain(tree, self._tsunami, scope)

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
            f"{Confidence.APPROX.value!r} -- never the floor's 'noisy', never a "
            f"faked 'binding-resolved' -- got confidence={obs.confidence!r}. "
            f"{self._observed()}"
        )

    def then_provider_is_tsunami_at_binding_resolved(self) -> None:
        """With Tsunami PRESENT, the chain head answers provider=tsunami @ binding-resolved."""
        obs = self._require_observable()
        assert obs.provider == Provider.TSUNAMI.value, (
            f"with the paid Tsunami tier wired (probe passes) the chain head must "
            f"answer provider={Provider.TSUNAMI.value!r} -- got "
            f"provider={obs.provider!r}. {self._observed()}"
        )
        assert obs.confidence == Confidence.BINDING_RESOLVED.value, (
            f"the TsunamiAdapter must tag its precise answer "
            f"confidence={Confidence.BINDING_RESOLVED.value!r} -- got "
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

    def then_tsunami_absence_degraded_loud(self) -> None:
        """Tsunami ABSENT must SKIP LOUDLY (a health event) -- never silent-fail."""
        obs = self._require_observable()
        assert obs.loud_skip_event, (
            f"with Tsunami ABSENT (the normal case) the chain must SKIP the Tsunami "
            f"tier LOUDLY -- emitting a {_HEALTH_SKIP_PREFIX!r} health/skip signal "
            f"(the confidence/skip label IS the loud signal, Invariant 2) -- the "
            f"chain skipped SILENTLY (no loud-skip event observed). {self._observed()}"
        )

    def then_chain_proceeded_to_next_tier(self) -> None:
        """After skipping Tsunami the chain PROCEEDS to the next tier (answers)."""
        obs = self._require_observable()
        assert obs.gate_proceeded and obs.answered, (
            f"after skipping the absent Tsunami tier the chain must PROCEED to the "
            f"next tier and still return a usable answer (not block, not hang, not "
            f"silent-fail) -- the chain did not proceed to a usable answer. "
            f"{self._observed()}"
        )

    def then_tsunami_only_capability_skipped_loudly(self) -> None:
        """C8: a Tsunami-only capability + Tsunami absent -> SKIP LOUDLY (no answer faked)."""
        obs = self._require_observable()
        assert obs.loud_skip_event, (
            f"a Tsunami-only capability with Tsunami ABSENT must SKIP LOUDLY -- "
            f"emitting a {_HEALTH_SKIP_PREFIX!r} ledger event (C8) -- rather than "
            f"silently fabricating a stable-core-tier answer for a capability only "
            f"Tsunami can honor. No loud-skip event was observed. {self._observed()}"
        )
        assert obs.provider is None, (
            f"a Tsunami-only capability the chain cannot honor without Tsunami must "
            f"NOT be answered by a lower tier dressed up as covering it -- the "
            f"answer provider must be None (skipped), got provider={obs.provider!r}. "
            f"{self._observed()}"
        )

    def then_gate_proceeded_despite_skip(self) -> None:
        """C8: after the loud skip the gate PROCEEDS (does not block on Tsunami absence)."""
        obs = self._require_observable()
        assert obs.gate_proceeded, (
            f"after a Tsunami-only capability is SKIPPED LOUDLY the gate must PROCEED "
            f"(C8 -- INDETERMINATE/fail-closed is reserved for genuine high-stakes "
            f"ambiguity, NOT the routine 'paid tier absent' path, ADR-LA-001 §4/§6) "
            f"-- the gate did not proceed. {self._observed()}"
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
        return self._envelope_observable(result, loud_skip=False, proceeded=True)

    def _query_chain(
        self, tree: Path, tsunami: TsunamiPresence, scope: ChainScope
    ) -> ChainObservable:
        """Drive the REAL full CodeFactChain negotiation (assumptions A2 + A3)."""
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

        chain = self._build_chain(CodeFactChain, tree, tsunami)
        if chain is _SEAM_ABSENT:
            self._seam_error = _SEAM_ABSENT
            return self._absent_observable()

        capability_id = (
            CapabilityId.NEVER_WIRED.value
            if scope is ChainScope.STABLE_CORE
            else _TSUNAMI_ONLY_CAPABILITY
        )
        descriptor = CapabilityDescriptor(
            id=capability_id,
            stability=("stable" if scope is ChainScope.STABLE_CORE else "spike"),
            contract_version="1.0.0",
            io_schema=capability_id,
            providing_adapter=Provider.TSUNAMI.value,
        )
        result = chain.query(descriptor, {"symbol": "CacheWriter.flush"})
        loud_skip = self._read_loud_skip(chain)
        return self._envelope_observable(result, loud_skip=loud_skip, proceeded=True)

    def _build_chain(
        self, chain_cls: type, tree: Path, tsunami: TsunamiPresence
    ) -> object:
        """Build the chain wiring the Tsunami tier per the armed presence (A2).

        slice-02 EXTENDS the chain to take the Tsunami presence. The PRESENT case
        injects a passing-probe Tsunami; the ABSENT case (the normal target) wires
        no Tsunami tier. If the floor-only slice-01 chain ctor cannot carry the
        Tsunami presence, the construction degrades to the absent-seam sentinel so
        the Then names the not-yet-extended chain (active-RED).
        """
        try:
            return chain_cls(
                root=tree, tsunami_present=(tsunami is TsunamiPresence.PRESENT)
            )
        except TypeError:
            # The slice-01 floor-only chain ctor does not yet carry the Tsunami
            # presence kwarg -> the slice-02 extension is unbuilt (active-RED).
            return _SEAM_ABSENT

    @staticmethod
    def _read_loud_skip(chain: object) -> bool:
        """Read whether the chain emitted a LOUD health.gate.code-fact.* skip (A3).

        Reads the chain's emitted health/skip events via whichever accessor it
        exposes; a non-empty event whose name carries the
        ``health.gate.code-fact`` prefix is the LOUD-skip observable. An absent
        accessor (the slice-01 floor-only chain) yields False -- the Then then
        fires the named RED (the loud-skip seam is unbuilt).
        """
        for accessor in ("health_events", "skip_events", "code_fact_health_events"):
            events = getattr(chain, accessor, None)
            if events is None:
                continue
            collected = events() if callable(events) else events
            for event in collected or ():
                name = getattr(event, "name", None)
                if name is None and isinstance(event, dict):
                    name = event.get("event") or event.get("name")
                if name is None:
                    name = str(event)
                if _HEALTH_SKIP_PREFIX in str(name):
                    return True
        return False

    # =====================================================================
    # envelope reader + absent-seam observable
    # =====================================================================

    def _envelope_observable(
        self, result: object, *, loud_skip: bool, proceeded: bool
    ) -> ChainObservable:
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
            loud_skip_event=loud_skip,
            gate_proceeded=proceeded,
        )

    def _absent_observable(self) -> ChainObservable:
        """The seam is absent / not-yet-extended -> no observable; the Then names it."""
        return ChainObservable(
            answered=False,
            provider=None,
            confidence=None,
            reason_code=None,
            loud_skip_event=False,
            gate_proceeded=False,
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
                "REUSING testarch/adapters/python_ast.py + the TsunamiAdapter paid "
                "seam + the full CodeFactChain 'Tsunami -> Ast -> TextSearch' "
                "negotiation that degrades LOUD) must exist and return a tagged "
                "CodeFactResult envelope (+ a loud-skip signal) -- the seam is "
                "ABSENT / floor-only at HEAD (active-RED, DELIVER builds "
                "src/des/adapters/driven/codefact/ast_code_fact_adapter.py + "
                "tsunami_code_fact_adapter.py + EXTENDS code_fact_chain.py). "
                f"{self._observed()}"
            )
        return self._observable

    def _observed(self) -> str:
        cap = self._capability.value if self._capability else None
        return (
            f"capability={cap!r}; tsunami={self._tsunami!r}; scope={self._scope!r}; "
            f"observable={self._observable!r}; seam_error={self._seam_error!r}"
        )
