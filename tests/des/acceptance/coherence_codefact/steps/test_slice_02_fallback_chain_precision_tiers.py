"""pytest-bdd binding for the f-coherence-and-attestation slice-02 scenarios.

Driving surface (Mandate-13 driving-port-only, Layer 3 composition): the REAL
AstAdapter / the full CodeFactChain negotiation via the production composition
root. Step bodies delegate to the composition root
(composition_slice_02_fallback_chain.py); no business logic in step bodies
(Mandate-12). The ``<capability>`` parameter is parsed once into the typed
``CapabilityId`` enum, so ONE scenario shape ranges over the LOCKED stable-core
capability set.

active-RED scaffold (atdd_pure -- NOT @skip): every scenario is RED until DELIVER
lands the slice-02 seams (the AstAdapter @ approx + the TsunamiAdapter paid seam +
the full chain negotiation that degrades LOUD). Each scenario fails with a
semantic AssertionError naming the missing / floor-only seam, never a collection /
import / setup error.

STEP-TEXT UNIQUENESS (S1): every literal/template step phrase below is DISTINCT
from the slice-01 step phrases (slice-01 uses "is asked for the fact through the
CodeFactPort"; slice-02 uses "answers the structural fact" / "negotiates the best
available provider") -- no pytest-bdd global-registry shadow.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from pytest_bdd import given, parsers, scenarios, then, when

from .composition_slice_02_fallback_chain import FallbackChainComposition
from .domain_types_coherence_codefact import CapabilityId
from .domain_types_slice_02_fallback_chain import ChainScope, TsunamiPresence


scenarios("../slice-02-fallback-chain-precision-tiers.feature")


# Capability wire-token (kebab-lowercase, LOCKED) -> typed enum.
_CAPABILITY_BY_TOKEN = {c.value: c for c in CapabilityId}


@pytest.fixture
def fallback_chain() -> FallbackChainComposition:
    return FallbackChainComposition()


# --- Given -----------------------------------------------------------------


@given(
    parsers.parse(
        "a maintainer asks the structural tier for the capability {capability}"
    )
)
def given_structural_tier_capability(
    fallback_chain: FallbackChainComposition, capability: str
) -> None:
    fallback_chain.given_capability_required(_CAPABILITY_BY_TOKEN[capability])


@given("the paid precision tier is not installed on this target")
def given_tsunami_absent(fallback_chain: FallbackChainComposition) -> None:
    fallback_chain.given_tsunami_presence(TsunamiPresence.ABSENT)


@given("the paid precision tier is installed on this target")
def given_tsunami_present(fallback_chain: FallbackChainComposition) -> None:
    fallback_chain.given_tsunami_presence(TsunamiPresence.PRESENT)


@given(parsers.parse("the negotiation targets the stable-core capability {capability}"))
def given_negotiation_stable_core(
    fallback_chain: FallbackChainComposition, capability: str
) -> None:
    fallback_chain.given_capability_required(_CAPABILITY_BY_TOKEN[capability])
    fallback_chain.given_chain_scope(ChainScope.STABLE_CORE)


@given("the negotiation targets a premium-only capability the floor cannot honor")
def given_negotiation_tsunami_only(
    fallback_chain: FallbackChainComposition,
) -> None:
    fallback_chain.given_chain_scope(ChainScope.TSUNAMI_ONLY)


# --- When ------------------------------------------------------------------


@when("the ast tier answers the structural fact over a real source tree")
def when_ast_answers(fallback_chain: FallbackChainComposition, tmp_path: Path) -> None:
    fallback_chain.when_ast_adapter_answers_via_port(tmp_path)


@when("the fallback chain negotiates the best available provider")
def when_chain_negotiates(
    fallback_chain: FallbackChainComposition, tmp_path: Path
) -> None:
    fallback_chain.when_chain_negotiates(tmp_path)


# --- Then ------------------------------------------------------------------


@then("a structural answer is returned by the chain")
def then_structural_answer(fallback_chain: FallbackChainComposition) -> None:
    fallback_chain.then_a_usable_answer_came_back()


@then("the structural answer is tagged ast at approx confidence")
def then_tagged_ast_approx(fallback_chain: FallbackChainComposition) -> None:
    fallback_chain.then_provider_is_ast_at_approx()


@then("the structural answer carries locked cross-tier provenance tokens")
def then_locked_provenance(fallback_chain: FallbackChainComposition) -> None:
    fallback_chain.then_provenance_tokens_are_locked()


@then("the absent precision tier is skipped with a loud health signal")
def then_absent_tier_loud_skip(fallback_chain: FallbackChainComposition) -> None:
    fallback_chain.then_tsunami_absence_degraded_loud()


@then("the chain proceeds to the next tier and still answers")
def then_chain_proceeds(fallback_chain: FallbackChainComposition) -> None:
    fallback_chain.then_chain_proceeded_to_next_tier()


@then("the precise tier is tagged tsunami at binding-resolved confidence")
def then_tagged_tsunami_binding_resolved(
    fallback_chain: FallbackChainComposition,
) -> None:
    fallback_chain.then_provider_is_tsunami_at_binding_resolved()


@then("the premium-only capability is skipped with a loud health signal")
def then_premium_only_loud_skip(
    fallback_chain: FallbackChainComposition,
) -> None:
    fallback_chain.then_tsunami_only_capability_skipped_loudly()


@then("no lower tier is dressed up as covering the premium-only capability")
def then_no_lower_tier_dressed_up(
    fallback_chain: FallbackChainComposition,
) -> None:
    fallback_chain.then_tsunami_only_capability_skipped_loudly()


@then("the gate proceeds despite the loud skip")
def then_gate_proceeds_despite_skip(
    fallback_chain: FallbackChainComposition,
) -> None:
    fallback_chain.then_gate_proceeded_despite_skip()
