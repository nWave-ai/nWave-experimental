"""Shared step vocabulary for the fix-robustness-pbt-density-gate suite.

Mandate-12 (SSOT via Types + Services + DSL): the five slice `.feature` files
share ONE step vocabulary. Each decorator below is a parameterized template
over a typed-enum parameter (from ``domain_types.py``) -- the DSL emerges
from the typed domain concepts, not from one decorator per literal phrase.

Mandate-12 criterion 3: every step body is <=2 statements, ends in a single
``composition.<service>(...)`` call (or a typed-lookup + call), and contains
no control flow. Business logic lives in ``composition.py`` service methods,
never here.

The slice ``test_slice_NN_*.py`` files import ``*`` from this module and
call ``scenarios(...)`` on their own ``.feature`` file -- pytest-bdd
resolves the steps from this shared module (Mandate 10 shared-vocabulary
contract).
"""

from __future__ import annotations

import pytest
from pytest_bdd import given, parsers, then, when

from .composition import RobustnessGateComposition
from .domain_types import (
    EXIT_BY_MEANING,
    DomainId,
)


@pytest.fixture
def composition() -> RobustnessGateComposition:
    """The production composition root, fresh per scenario."""
    return RobustnessGateComposition()


# --- Given: declaration + AT-scope staging -----------------------------------


@given(
    parsers.parse(
        'a declared unbounded input domain "{domain_id}" carrying a property-based '
        "test that exercises it"
    )
)
def given_declared_domain_with_coverage(
    composition: RobustnessGateComposition, domain_id: str
) -> None:
    composition.given_declared_domain_with_coverage(DomainId(domain_id))


@given(
    parsers.parse(
        'a declared unbounded input domain "{domain_id}" with no property-based '
        "test exercising it"
    )
)
def given_declared_domain_without_coverage(
    composition: RobustnessGateComposition, domain_id: str
) -> None:
    composition.given_declared_domain_without_coverage(DomainId(domain_id))


@given("a declaration document that cannot be parsed as a valid manifest projection")
def given_malformed_declaration(composition: RobustnessGateComposition) -> None:
    composition.given_malformed_declaration()


# --- slice-02: declaration-state staging vocabulary (additive) ---------------


@given(
    "a declaration document that omits the unbounded-input-domains block while "
    "acceptance tests exist in the scope"
)
def given_declaration_missing_block_with_ats(
    composition: RobustnessGateComposition,
) -> None:
    composition.given_declaration_missing_block_with_ats_in_scope()


@given(
    "a declaration document that explicitly declares no unbounded input domains "
    "and carries a one-line rationale"
)
def given_explicit_empty_with_rationale(
    composition: RobustnessGateComposition,
) -> None:
    composition.given_explicit_empty_declaration_with_rationale()


@given(
    parsers.parse(
        "a declaration document carrying a distill-authored unbounded input "
        'domain "{domain_id}" that the design component manifest never declared'
    )
)
def given_distill_authored_manifest_absent(
    composition: RobustnessGateComposition, domain_id: str
) -> None:
    composition.given_distill_authored_domain_absent_from_manifest(DomainId(domain_id))


# --- slice-03: genuineness-layer staging vocabulary (additive) ---------------


@given(
    parsers.parse(
        'a declared unbounded input domain "{domain_id}" covered by a property-based '
        "test whose strategy is reached through a single-hop module-local helper "
        "returning a constant"
    )
)
def given_trivial_strategy_via_helper(
    composition: RobustnessGateComposition, domain_id: str
) -> None:
    composition.given_trivial_strategy_via_helper(DomainId(domain_id))


@given(
    parsers.parse(
        'a declared unbounded input domain "{domain_id}" covered by a property-based '
        "test whose only assertion is reached through a single-hop module-local helper "
        "returning a tautology"
    )
)
def given_tautology_assert_via_helper(
    composition: RobustnessGateComposition, domain_id: str
) -> None:
    composition.given_tautology_assert_via_helper(DomainId(domain_id))


@given(
    parsers.parse(
        'a declared unbounded input domain "{domain_id}" alongside an adversarial '
        "test file whose parametrize value list is reached through a module-local "
        "helper the gate parser cannot classify"
    )
)
def given_adversarial_indirect_parametrize(
    composition: RobustnessGateComposition, domain_id: str
) -> None:
    composition.given_adversarial_indirect_parametrize(DomainId(domain_id))


# --- slice-04: genuineness layer 2 staging vocabulary (additive) -------------
# Mandate-12 / Mandate-10: shared-vocabulary contract. Each Given below maps
# one cell of `Slice04Layer2State` (in `domain_types.py`) to one composition
# service method; step bodies are <=2 statements and delegate to the SSOT.


@given(
    parsers.parse(
        'a declared unbounded input domain "{domain_id}" covered by a property-based '
        "test whose declared sut symbol has kill-rate zero in the fixture mutmut "
        "report while the positive control was killed"
    )
)
def given_layer2_kill_rate_zero(
    composition: RobustnessGateComposition, domain_id: str
) -> None:
    composition.given_layer2_kill_rate_zero(DomainId(domain_id))


@given(
    parsers.parse(
        'a declared unbounded input domain "{domain_id}" covered by a property-based '
        "test whose declared sut symbol has positive kill-rate in the fixture mutmut "
        "report while the positive control was killed"
    )
)
def given_layer2_kill_rate_positive(
    composition: RobustnessGateComposition, domain_id: str
) -> None:
    composition.given_layer2_kill_rate_positive(DomainId(domain_id))


@given(
    parsers.parse(
        'a declared unbounded input domain "{domain_id}" covered by a property-based '
        "test whose fixture mutmut report is untrustworthy"
    )
)
def given_layer2_report_untrustworthy(
    composition: RobustnessGateComposition, domain_id: str
) -> None:
    composition.given_layer2_report_untrustworthy(DomainId(domain_id))


# --- slice-05: wiring staging vocabulary (additive) -------------------------
# WIRING SLICE -- last by design (feature-delta § 6 line 410). Slice-05 drives
# the SUT through THREE wiring driving ports per Mandate-13:
#   AT1 -- the real at_review_verdict.py producer (Layer 3 subprocess)
#   AT2 -- the real SubagentStop hook chain (Layer 4 wiring_e2e, NEVER mocked)
#   AT3 -- the real M slice-04 manifest producer (Layer 3 subprocess)
# Each Given delegates to a typed-domain composition service per Mandate-12
# criterion 3 (<=2 statements, no control flow, final stmt = composition.X).


@given(
    parsers.parse(
        'a slice whose declared unbounded input domain "{domain_id}" is staged with '
        "a property-based test the robustness density gate refuses"
    )
)
def given_slice_refused_by_robustness_gate(
    composition: RobustnessGateComposition, domain_id: str
) -> None:
    composition.given_slice_refused_by_robustness_gate(DomainId(domain_id))


@given(
    parsers.parse(
        'a slice whose declared unbounded input domain "{domain_id}" is staged with '
        "a property-based test the robustness density gate refuses and a real "
        "sub agent dispatch is prepared for that slice"
    )
)
def given_slice_refused_and_real_dispatch_prepared(
    composition: RobustnessGateComposition, domain_id: str
) -> None:
    # Two delegations per criterion 3: stage the refused slice substrate
    # AND provision the real SubagentStop dispatch payload. Both are SSOT
    # service methods on the composition root -- step body delegates only.
    composition.given_slice_refused_by_robustness_gate(DomainId(domain_id))
    composition.given_real_subagent_dispatch_prepared(DomainId(domain_id))


@given(
    parsers.parse(
        "a throwaway feature whose design component manifest is emitted by the real "
        'design manifest producer and declares an unbounded input domain "{domain_id}" '
        "with no property-based test coverage in the slice scope"
    )
)
def given_throwaway_feature_with_real_m_producer_manifest(
    composition: RobustnessGateComposition, domain_id: str
) -> None:
    composition.given_throwaway_feature_with_real_m_producer_manifest(
        DomainId(domain_id)
    )


# --- When: gate invocation ---------------------------------------------------


@when("the developer runs the robustness density gate against the declared scope")
def when_run_gate(composition: RobustnessGateComposition) -> None:
    composition.result = composition.run_gate_against_staged_scope()


@when(
    "the developer runs the robustness density gate against the declared scope "
    "including the fixture mutmut report"
)
def when_run_gate_with_mutmut_report(composition: RobustnessGateComposition) -> None:
    # Slice-04 When-vocabulary specialization for Pillar-1 clarity: the
    # narrative names the fixture mutmut report as part of the invocation
    # scope. Composition method is the same -- the report path was wired in
    # the slice-04 Given (`_stage_layer2_scenario`); the When merely runs
    # the gate. Mandate-12 criterion 3: <=2 statements, no control flow.
    composition.result = composition.run_gate_against_staged_scope()


# --- Then: outcome assertions ------------------------------------------------


@then("the gate exit status indicates success")
def then_exit_success(composition: RobustnessGateComposition) -> None:
    assert composition.result.exit_code == EXIT_BY_MEANING["success"]


@then("the gate exit status indicates a check failed")
def then_exit_check_failed(composition: RobustnessGateComposition) -> None:
    assert composition.result.exit_code == EXIT_BY_MEANING["check failed"]


@then("the gate exit status indicates a malformed declaration")
def then_exit_malformed(composition: RobustnessGateComposition) -> None:
    assert composition.result.exit_code == EXIT_BY_MEANING["a malformed declaration"]


# --- slice-02: exit-status assertions (additive) -----------------------------
# Slice-02 widens exit-1 semantics without adding new exit codes. The
# dedicated phrases keep Pillar 1 (domain readability) while resolving to
# the same RobustnessGateExit.CHECK_FAILED value via EXIT_BY_MEANING.


@then("the gate exit status indicates a missing declaration")
def then_exit_missing_declaration(composition: RobustnessGateComposition) -> None:
    # Universe extension (Mandate 8): exit code alone is too narrow --
    # slice-02 distinguishes three exit-1 sub-classes via the human-surface
    # diagnostic token. Asserting on the token closes the universe-too-narrow
    # trap (slice-01 CLI crashes with KeyError on missing block and happens
    # to exit 1 -- a token-blind AT would vacuously pass).
    assert composition.result.exit_code == EXIT_BY_MEANING["a missing declaration"]
    assert "RobustnessDeclarationMissing" in composition.result.stdout


@then("the gate exit status indicates a provenance violation")
def then_exit_provenance_violation(composition: RobustnessGateComposition) -> None:
    assert composition.result.exit_code == EXIT_BY_MEANING["a provenance violation"]
    assert "RobustnessProvenanceViolation" in composition.result.stdout


@then("the gate exit status indicates the explicit empty declaration was accepted")
def then_exit_explicit_empty_accepted(
    composition: RobustnessGateComposition,
) -> None:
    # Universe extension (Mandate 8): asserting exit 0 alone vacuously passes
    # the slice-01 CLI's empty-list behavior (zero declared, zero covered ->
    # exit 0 by accident). The discriminating observable is the human-surface
    # token RobustnessExplicitEmptyAccepted -- the slice-02 implementation
    # must consciously emit it after reading the rationale field, not fall
    # through the slice-01 coverage-walk happy path.
    assert composition.result.exit_code == EXIT_BY_MEANING["success"]
    assert "RobustnessExplicitEmptyAccepted" in composition.result.stdout


@then(parsers.parse('the gate exit status is "{exit_meaning}"'))
def then_exit_status_is(
    composition: RobustnessGateComposition, exit_meaning: str
) -> None:
    assert composition.result.exit_code == EXIT_BY_MEANING[exit_meaning]


# --- slice-03: genuineness-layer outcome assertions (additive) ---------------
# Slice-03 widens exit-1 semantics further with the RobustnessPBTShallow
# diagnostic token. Universe extension (Mandate 8) per the slice-02 precedent:
# discriminating observable lives in stdout, NOT in exit code alone.


@then("the gate exit status indicates a shallow property-based test")
def then_exit_shallow_pbt(composition: RobustnessGateComposition) -> None:
    # Slice-03 universe extension: exit 1 alone vacuously matches slice-01's
    # coverage-miss CHECK_FAILED and slice-02's declaration-missing /
    # provenance-violation CHECK_FAILED. The discriminating observable is
    # the RobustnessPBTShallow diagnostic token emitted by the genuineness
    # layers 1+3 branch the production CLI must grow in DELIVER.
    assert (
        composition.result.exit_code == EXIT_BY_MEANING["a shallow property-based test"]
    )
    assert "RobustnessPBTShallow" in composition.result.stdout


@then(
    "the gate completes the adversarial parser probe without crashing and records "
    "an advisory verdict for the unclassifiable indirect parametrize source"
)
def then_exit_adversarial_probe_no_crash(
    composition: RobustnessGateComposition,
) -> None:
    # R6 gate-self-dogfood: the slice's highest-risk surface is the gate's
    # own AST parser. The deterministic verdict here is exit 0 (the
    # genuine @given covers the domain; the adversarial indirect-
    # parametrize file is advisory-only per the architect) PLUS the
    # discriminating observable that the genuineness scanner consciously
    # classified the V4 indirect-parametrize source as unclassifiable. The
    # token RobustnessAdvisoryUnclassified is the CLI's typed contract --
    # absent today, MUST be emitted by the genuineness branch DELIVER
    # ships. Without this token assertion AT3 would vacuously pass against
    # the slice-01 CLI (which is silent on adversarial-AST files because
    # it has no genuineness branch at all).
    assert composition.result.exit_code is not None, (
        "gate parser crashed on adversarial AST -- exit code is out of "
        "the {0, 1, 2} enum and could not be coerced"
    )
    assert composition.result.exit_code == EXIT_BY_MEANING["success"]
    assert "RobustnessAdvisoryUnclassified" in composition.result.stdout
    # Absence-of-shallow-token is the third universe dimension: the
    # adversarial file MUST NOT spuriously trigger genuineness layers 1+3
    # (those layers only fire on @given-tagged shallow shapes; an
    # un-tagged parametrize file is out of their scope).
    assert "RobustnessPBTShallow" not in composition.result.stdout


# --- slice-04: genuineness layer 2 outcome assertions (additive) -------------
# Slice-04 introduces TWO new diagnostic tokens (RobustnessPBTNotFalsifiable
# at exit 1, RobustnessLayer2Unavailable at exit 3) AND a new exit code
# (3 = UNAVAILABLE, R5 three-state). Universe extension (Mandate 8) per the
# slice-02/03 precedent: discriminating observable lives in stdout, NOT in
# exit code alone -- slice-04's exit-1 cell (RobustnessPBTNotFalsifiable)
# would vacuously match slice-01 coverage-miss / slice-02 declaration-missing
# / slice-03 shallow without the token assertion.


@then("the gate exit status indicates a property-based test that is not falsifiable")
def then_exit_pbt_not_falsifiable(composition: RobustnessGateComposition) -> None:
    # Slice-04 layer-2 refusal universe: exit 1 alone vacuously matches
    # earlier slices' CHECK_FAILED cells. The discriminating observable is
    # the RobustnessPBTNotFalsifiable token emitted by the layer-2
    # mutmut-delta proxy branch the production CLI must grow in DELIVER.
    assert (
        composition.result.exit_code
        == EXIT_BY_MEANING["a property-based test that is not falsifiable"]
    )
    assert "RobustnessPBTNotFalsifiable" in composition.result.stdout
    # Absence-of-Unavailable guards the R5 three-state distinction: a
    # kill-rate-zero verdict where mutmut WAS trustworthy MUST classify
    # as NotFalsifiable (exit 1), never as Unavailable (exit 3) -- else
    # a discriminating mutmut run would silently downgrade to "neither
    # pass nor fail".
    assert "RobustnessLayer2Unavailable" not in composition.result.stdout


@then("the gate exit status indicates the falsifiability layer was satisfied")
def then_exit_layer2_satisfied(composition: RobustnessGateComposition) -> None:
    # Slice-04 happy-path universe: exit 0 alone vacuously matches slice-01
    # coverage-pass / slice-02 explicit-empty-accepted / slice-03 advisory-
    # unclassified. The discriminating observable is absence of any
    # layer-2 refusal token AND absence of Unavailable. The slice-04
    # CLI implementation choice for a positive observable (e.g. a
    # `RobustnessLayer2Satisfied` token) is DELIVER's; the AT contract
    # here is "the gate exited 0 AND emitted no refusal/unavailable token".
    assert (
        composition.result.exit_code
        == EXIT_BY_MEANING["the falsifiability layer was satisfied"]
    )
    assert "RobustnessPBTNotFalsifiable" not in composition.result.stdout
    assert "RobustnessLayer2Unavailable" not in composition.result.stdout


@then(
    "the gate exit status indicates the falsifiability layer is unavailable and the "
    "feature is held out of ready"
)
def then_exit_layer2_unavailable(composition: RobustnessGateComposition) -> None:
    # Slice-04 R5 three-state universe: the new exit 3 is DISTINCT from
    # CHECK_FAILED (exit 1). An exit-1 verdict here would silently
    # downgrade "mutmut cannot be trusted" to "PBT cannot falsify the SUT"
    # -- the exact failure mode R5 was specified to prevent. The
    # RobustnessLayer2Unavailable token discriminates the cell within
    # the universe; the new exit code 3 holds the feature out of `ready`
    # in the parent verdict producer (slice-05 wiring).
    assert (
        composition.result.exit_code
        == EXIT_BY_MEANING[
            "the falsifiability layer is unavailable and the feature is held out of ready"
        ]
    )
    assert "RobustnessLayer2Unavailable" in composition.result.stdout
    # Absence-of-NotFalsifiable is the second universe dimension: an
    # Unavailable verdict MUST NOT also emit NotFalsifiable -- the two
    # cells are mutually exclusive per R5 (the gate has either evidence
    # the dependency lies OR evidence the PBT is shallow, never both).
    assert "RobustnessPBTNotFalsifiable" not in composition.result.stdout


# --- slice-05: wiring When + Then vocabulary (additive) ---------------------
# Slice-05 widens the AT outcome universe with the wiring substrate's
# discriminating observables (Mandate 8 / closed-world-effect 2026-05-15):
# the verdict-producer's ledger-write decision (AT1), the SubagentStop hook
# chain's dispatch-block decision (AT2), and the gate's refusal verdict
# against the M-producer-emitted manifest (AT3). The fields below sit on
# the same RobustnessGateResult dataclass earlier slices populate, kept on
# one universe per Mandate-12 SSOT discipline.


@when(
    "the developer runs the AT review verdict producer for the slice with the "
    "robustness density gate wired into its DISTILL exit"
)
def when_run_at_review_verdict_producer_with_gate_wired(
    composition: RobustnessGateComposition,
) -> None:
    composition.when_run_at_review_verdict_producer_with_gate_wired()


@when(
    "the real sub agent dispatch passes through the real SubagentStop hook chain "
    "with the robustness density gate registered as an intercept"
)
def when_real_subagent_dispatch_passes_through_subagent_stop_hook_chain(
    composition: RobustnessGateComposition,
) -> None:
    composition.when_real_subagent_dispatch_passes_through_subagent_stop_hook_chain()


@when(
    "the developer runs the robustness density gate against the throwaway feature "
    "using the real design manifest producer emitted component manifest"
)
def when_run_robustness_gate_against_real_m_producer_manifest(
    composition: RobustnessGateComposition,
) -> None:
    composition.when_run_robustness_gate_against_real_m_producer_manifest()


@then(
    "the AT review verdict producer does not write an approved AT review verdict "
    "ledger record"
)
def then_at_review_verdict_record_not_written(
    composition: RobustnessGateComposition,
) -> None:
    # Slice-05 AT1 wiring-effect universe: the discriminating observable is
    # the producer's ledger-write decision, NOT the gate CLI's exit code
    # alone. A wiring AT that asserted on the gate CLI exit code only would
    # vacuously match the slice-01 CLI's refusal verdict WITHOUT proving the
    # producer consulted it -- this is the fixture-only-wiring defect the
    # slice exists to prevent (feature-delta § 6 lines 440-449).
    assert composition.result.verdict_record_written is False, (
        "slice-05 AT1 wiring contract violated: at_review_verdict producer "
        "wrote an APPROVED ledger record despite the robustness density gate "
        "refusing the slice -- the gate CLI exit code is not gating the "
        "producer's ledger write"
    )


@then(
    "the AT review verdict producer surfaces the robustness density gate refusal "
    "as the blocking diagnostic"
)
def then_verdict_producer_surfaces_gate_refusal(
    composition: RobustnessGateComposition,
) -> None:
    # Slice-05 AT1 diagnostic universe: the producer MUST surface the gate
    # refusal on its stderr (the human-surface diagnostic channel). The
    # token is the gate's own ``RobustnessCoverageMiss`` (slice-01 refusal
    # shape), forwarded by the verdict producer. Absence of the token would
    # mean the producer silently swallowed the gate refusal -- a second
    # fixture-only-wiring defect class.
    assert "RobustnessCoverageMiss" in composition.result.verdict_producer_stderr, (
        "slice-05 AT1 diagnostic contract violated: at_review_verdict "
        "producer did not surface the gate refusal token "
        "RobustnessCoverageMiss in its stderr -- the gate's diagnostic is "
        "silently swallowed at the producer boundary"
    )


@then("the SubagentStop hook chain blocks the dispatch outcome from completing")
def then_subagent_stop_hook_chain_blocks_dispatch(
    composition: RobustnessGateComposition,
) -> None:
    # Slice-05 AT2 wiring-effect universe (B4 mandate): the discriminating
    # observable is the dispatch-block decision the hook chain emits, NOT
    # the gate CLI's exit code. A hook-chain AT that asserted on the gate
    # CLI alone would vacuously pass against a registration that EXISTS but
    # is never EXERCISED -- the precise defect class B4 enforces against
    # (feature-delta § 6 lines 440-449).
    assert composition.result.dispatch_blocked is True, (
        "slice-05 AT2 wiring contract violated: the SubagentStop hook chain "
        "did not block the dispatch outcome despite the robustness density "
        "gate refusing the slice -- the hook intercept registration exists "
        "but the hook chain does not actually invoke + gate on it"
    )


@then(
    "the SubagentStop hook chain surfaces the robustness density gate refusal "
    "as the blocking diagnostic"
)
def then_hook_chain_surfaces_gate_refusal(
    composition: RobustnessGateComposition,
) -> None:
    # Slice-05 AT2 diagnostic universe: the hook chain MUST surface the
    # gate's RobustnessCoverageMiss token in its block diagnostic so the
    # downstream operator can identify WHY the dispatch was blocked. A
    # silent block would surface as "dispatch blocked" without naming the
    # gate -- the same fixture-only-wiring defect at the operator surface.
    assert "RobustnessCoverageMiss" in composition.result.hook_chain_diagnostic, (
        "slice-05 AT2 diagnostic contract violated: the SubagentStop hook "
        "chain did not surface the gate refusal token RobustnessCoverageMiss "
        "in its block diagnostic -- the gate's diagnostic is silently "
        "swallowed at the hook-chain boundary"
    )


@then("the robustness density gate refuses the throwaway feature")
def then_gate_refuses_throwaway_feature(
    composition: RobustnessGateComposition,
) -> None:
    # Slice-05 AT3 wiring-effect universe (B1 mandate): the gate CLI's exit
    # code is the wiring-effect observable when the input is the REAL M
    # producer's component-manifest (NOT a hand-authored fixture). The
    # universe contract widens to "the gate refuses the real producer's
    # output" -- if the producer emits a shape the gate cannot parse, the
    # exit code surfaces it; if the producer emits a coverage-missing
    # declaration, the exit code surfaces it. Either way, the producer-to-
    # gate seam is demonstrated rather than asserted on calendar.
    assert composition.result.exit_code == EXIT_BY_MEANING["check failed"], (
        "slice-05 AT3 wiring contract violated: the robustness density gate "
        "did not refuse the throwaway feature whose declared unbounded input "
        "domain has no coverage in the slice scope -- either the real M "
        "producer is emitting a manifest shape the gate cannot parse, or the "
        "gate is not consulting the producer-emitted manifest"
    )


@then(
    "the robustness density gate diagnostic identifies the uncovered declared "
    "unbounded input domain"
)
def then_gate_diagnostic_identifies_uncovered_domain(
    composition: RobustnessGateComposition,
) -> None:
    # Slice-05 AT3 diagnostic universe: the gate's stdout MUST carry the
    # RobustnessCoverageMiss token (slice-01 refusal shape). Absent the
    # token, the gate exit-1 verdict is ambiguous (slice-02/03/04 refusal
    # shapes also exit 1) -- the discriminating observable disambiguates.
    assert "RobustnessCoverageMiss" in composition.result.stdout, (
        "slice-05 AT3 diagnostic contract violated: the gate did not emit "
        "RobustnessCoverageMiss for the throwaway feature whose declared "
        "unbounded input domain has no coverage -- the gate's diagnostic "
        "is missing or named incorrectly for the producer-emitted manifest"
    )
