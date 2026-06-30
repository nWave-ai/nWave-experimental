"""Step definitions for r3-gate-non-vacuity-build-tier slice-02 (Mandate-12).

slice-02 (PO REVISED, Ale): the per-slice exit gate must refuse LOUD when a
target's architecture tier EXISTS but collects ZERO invariant (a malformed arch
tier), while still CLEARING a target that legitimately carries NO architecture
tier at all. The two holes are NOT symmetric -- the `--feature-id` gate runs on
the TARGET repo during DELIVER, and an external target (TS/Go/minimal Python)
legitimately has no nWave `tests/build/` arch tier; refusing it would violate the
STANDING genericità mandate and break the prior `atdd_pure_carpaccio_spine` ATs.

  * arch tier ABSENT        -> CLEAR (exit 0 `FeatureScopeCleared`). Genericità:
    no arch tier means no arch invariant to enforce. slice-02 adds an ABSENT
    *clear control* -- the gate must NOT over-refuse a legitimate no-arch-tier
    target. RED at HEAD: current production over-refuses ABSENT with
    `arch-scope-empty` exit 2; this control is the RED witness for the upcoming
    "remove the Hole A branch" production change.
  * arch tier collects zero  -> REFUSE (exit 2 `FeatureScopeMalformed` reason
    `arch-scope-zero-collected`). The genuinely malformed case: an arch tier is
    present (the dir exists) but the gate would fingerprint a vacuous arch run.
    GREEN at HEAD: current production already refuses it.
  * arch tier present + green -> CLEAR control (exit 0 `FeatureScopeCleared`),
    guards against over-refusal of a non-vacuous green tier.

Step bodies delegate to `R3GateComposition2` -- no inline business logic
(Mandate-12 criterion 3: <=2 statements, single delegation / single assertion,
no control flow). Domain nouns are typed via `domain_types_slice_02` (criterion
1); the composition service signatures consume those typed parameters (criterion
2).

Mandate-13: the SUT is driven exclusively through the real `des
run-contract-gate --feature-id` CLI as a Layer-3 subprocess black-box (inherited
verbatim from slice-01 via `R3GateComposition2`). Mandate-9/11: layer-3 real-IO
-> example-only; the paired PBT properties (refuse / clear) live at the SAME
driving port and are example-budgeted small (each spawns a real subprocess per
example), and are perturbation-bound (present-but-vacuous refuses; absent +
present-green clear), never vacuous constants.

S1 (step-text uniqueness): the shared clean-feature-scope Given + the When + the
shared verdict Thens (`the gate refuses the slice`, `the gate clears the slice's
feature scope`, `the gate certifies a non-vacuous architecture-tier scope`) are
imported from the single SSOT module `common_steps` -- NOT redeclared here. Only
the slice-02-specific Givens + the precise-reason / clear-control Thens are
declared in this module. Zero literal collisions across slice files.
"""

from __future__ import annotations

import pytest
from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st
from pytest_bdd import given as bdd_given
from pytest_bdd import scenarios, then

# Shared step SSOT (S1 single-source re-use): the clean-scope Given + When + the
# shared verdict Thens.
from .common_steps import *
from .composition_slice_02 import R3GateComposition2
from .domain_types_slice_02 import (
    ARCH_SCOPE_ZERO_COLLECTED_REASON,
    FEATURE_SCOPE_CLEARED_EVENT,
    FEATURE_SCOPE_MALFORMED_EVENT,
    ArchScopeShape,
    GateVerdict,
)


scenarios("../slice-02-arch-scope-non-vacuity.feature")


@pytest.fixture
def composition() -> R3GateComposition2:
    """The production composition root driving the real contract-gate CLI."""
    return R3GateComposition2()


# ===========================================================================
# Given -- slice-02-specific (the shared clean-feature-scope Given comes from
# common_steps; S1 single SSOT)
# ===========================================================================


@bdd_given("the repository carries no architecture tier")
def _given_arch_absent(composition: R3GateComposition2, repo) -> None:
    """Seed the genericità clear-control: clean feature scope, NO `tests/build/`."""
    composition.make_arch_scope_repo(repo, ArchScopeShape.ABSENT)


@bdd_given("the architecture tier collects no invariant")
def _given_arch_zero_collected(composition: R3GateComposition2, repo) -> None:
    """Seed the refuse case: a `tests/build/` dir holding only an UNMARKED test."""
    composition.make_arch_scope_repo(repo, ArchScopeShape.ZERO_COLLECTED)


@bdd_given("the architecture tier carries a holding invariant")
def _given_arch_present(composition: R3GateComposition2, repo) -> None:
    """Seed the clear-control: a non-vacuous `tests/build/` tier that runs GREEN."""
    composition.make_arch_scope_repo(repo, ArchScopeShape.PRESENT)


# ===========================================================================
# Then -- slice-02-specific precise-reason / clear-control assertions
# ===========================================================================


@then("the gate reports the architecture scope collected nothing")
def _then_arch_scope_zero_collected(gate_run) -> None:
    # The REFUSE must surface the malformed verdict event with the precise
    # present-but-vacuous reason `arch-scope-zero-collected`. Precision
    # distinguishes the zero-collected refusal from the keystone
    # arch-invariant-failed refusal and from the feature-scope floor reasons.
    assert gate_run.event == FEATURE_SCOPE_MALFORMED_EVENT, (
        "the gate refused but did not surface a FeatureScopeMalformed verdict "
        f"(saw event {gate_run.event!r}, exit {gate_run.exit_code}) -- a present "
        "arch tier that collects zero invariants must be refused LOUD, not silently "
        "cleared"
    )
    assert ARCH_SCOPE_ZERO_COLLECTED_REASON in gate_run.stdout, (
        "the gate refused but did not report reason "
        f"{ARCH_SCOPE_ZERO_COLLECTED_REASON!r} -- the malformed verdict must name "
        "the zero-collected architecture tier, not a generic floor trip "
        f"(stdout: {gate_run.stdout.strip()[:300]!r})"
    )


@then("the gate does not over-refuse the absent architecture tier")
def _then_no_over_refuse_absent(gate_run) -> None:
    # Genericità regression guard: a target that legitimately carries NO arch
    # tier must CLEAR (exit 0 FeatureScopeCleared), never be refused for an absent
    # arch scope. RED at HEAD: current production over-refuses ABSENT with
    # `arch-scope-empty` exit 2 -- this assertion pins the over-refusal that the
    # upcoming production change must drop.
    assert gate_run.event == FEATURE_SCOPE_CLEARED_EVENT, (
        "the gate did not clear a legitimate no-arch-tier target -- it surfaced "
        f"event {gate_run.event!r} (exit {gate_run.exit_code}) instead of "
        "FeatureScopeCleared. An external target (TS/Go/minimal Python) carries no "
        "nWave architecture tier; refusing it over-narrows and violates genericità "
        "(production still over-refuses absent arch tier with arch-scope-empty)"
    )


@then("the system is unchanged")
def _then_system_unchanged(gate_run) -> None:
    # @contract-shape:unbounded-preservation: the gate INSPECTS + refuses; it must
    # not mutate the system. The port-exposed observable of "unchanged" is the
    # fail-closed refusal with no side-effect emission beyond the single verdict
    # event -- a clean exit 2 (REFUSED), never an UNEXPECTED crash that could have
    # left partial state. (Layer-3 real-IO: traditional assertion per Mandate 8;
    # the universe here is the verdict + the absence of an UNEXPECTED failure mode.)
    assert gate_run.verdict is GateVerdict.REFUSED, (
        "an arch-tier-vacuity refusal must be a clean fail-closed REFUSED "
        f"(exit 2), leaving the system unchanged; got verdict "
        f"{gate_run.verdict.value!r} (exit {gate_run.exit_code})"
    )


# ===========================================================================
# Paired properties (Mandate 9/11: layer-3 example-budgeted PBT at the SAME
# driving port). Universe = the gate's exit-code-derived verdict (port-exposed).
# ===========================================================================


@settings(
    max_examples=6,  # layer-3: each example spawns a real subprocess
    deadline=None,
    suppress_health_check=[HealthCheck.function_scoped_fixture],
)
@given(shape=st.just(ArchScopeShape.ZERO_COLLECTED))
def test_present_but_vacuous_arch_tier_refuses(tmp_path_factory, shape) -> None:
    """For a synthetic repo whose feature `.feature` scope is all-clean but whose
    architecture tier EXISTS and collects ZERO invariant under the `-m` filter,
    the feature-scoped exit gate REFUSES (exit 2 FeatureScopeMalformed reason
    `arch-scope-zero-collected`).

    Universe (port-exposed): the gate's `verdict` (exit-code-exact) + the
    structured verdict `event` on stdout. The refuse property quantifies ONLY the
    genuinely-malformed shape (present-but-vacuous). It is perturbation-bound, not
    vacuously true: the clear property below proves the gate CLEARS the
    non-refuse shapes (ABSENT + PRESENT), so a refuse-always property would be
    over-specified.

    GREEN at HEAD: current production already refuses a present-but-vacuous arch
    tier. (This property guards against a regression that would re-open the
    silent-narrowing hole.)
    """
    composition = R3GateComposition2()
    repo = composition.make_arch_scope_repo(
        tmp_path_factory.mktemp("arch_scope_refuse"),
        shape,
    )

    run = composition.run_feature_scoped_gate(repo)

    assert run.verdict is GateVerdict.REFUSED, (
        f"the gate did not refuse a present-but-vacuous arch tier ({shape.value!r}) "
        f"(verdict {run.verdict.value!r}, exit {run.exit_code}) -- a present arch "
        "tier collecting zero invariants is malformed and must be refused LOUD"
    )
    assert run.event == FEATURE_SCOPE_MALFORMED_EVENT, (
        f"the gate refused but surfaced no FeatureScopeMalformed verdict for a "
        f"{shape.value!r} arch tier (event {run.event!r})"
    )
    assert ARCH_SCOPE_ZERO_COLLECTED_REASON in run.stdout, (
        f"the malformed verdict did not name reason "
        f"{ARCH_SCOPE_ZERO_COLLECTED_REASON!r} for a {shape.value!r} arch tier "
        f"(stdout: {run.stdout.strip()[:300]!r})"
    )


@settings(
    max_examples=8,  # layer-3: each example spawns a real subprocess
    deadline=None,
    suppress_health_check=[HealthCheck.function_scoped_fixture],
)
@given(shape=st.sampled_from([ArchScopeShape.ABSENT, ArchScopeShape.PRESENT]))
def test_non_refuse_arch_scope_clears(tmp_path_factory, shape) -> None:
    """For ANY synthetic repo whose feature `.feature` scope is all-clean and
    whose architecture tier is either ABSENT (no `tests/build/`, genericità) or
    PRESENT-and-green (a non-vacuous tier whose invariant holds), the
    feature-scoped exit gate CLEARS (exit 0 FeatureScopeCleared).

    Universe (port-exposed): the gate's `verdict` + the verdict `event`. The
    clear property quantifies the two NON-refuse shapes -- it is the genericità
    over-refusal guard (ABSENT must not be refused) + the no-over-refusal guard
    (a green tier must not be refused). Perturbation-bound: the refuse property
    above proves the present-but-vacuous shape REFUSES, so a clear-always
    property would be over-specified.

    Mixed RED/GREEN at HEAD: PRESENT clears today (GREEN); ABSENT is over-refused
    today with `arch-scope-empty` (RED -- the genericità fix this slice drives).
    """
    composition = R3GateComposition2()
    repo = composition.make_arch_scope_repo(
        tmp_path_factory.mktemp("arch_scope_clear"),
        shape,
    )

    run = composition.run_feature_scoped_gate(repo)

    assert run.verdict is GateVerdict.CLEARED, (
        f"the gate did not clear a non-refuse arch scope ({shape.value!r}) "
        f"(verdict {run.verdict.value!r}, exit {run.exit_code}) -- ABSENT is a "
        "legitimate no-arch-tier target (genericità) and PRESENT-green is a "
        "non-vacuous holding tier; neither may be over-refused"
    )
    assert run.event == FEATURE_SCOPE_CLEARED_EVENT, (
        f"the gate cleared but surfaced no FeatureScopeCleared verdict for a "
        f"{shape.value!r} arch scope (event {run.event!r}, exit {run.exit_code})"
    )
