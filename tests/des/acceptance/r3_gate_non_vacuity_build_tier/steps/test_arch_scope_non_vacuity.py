"""Step definitions for r3-gate-non-vacuity-build-tier slice-02 (Mandate-12).

slice-02 (PO REVISED, Ale): the per-slice exit gate must refuse LOUD when a
target's architecture tier EXISTS but collects ZERO invariant (a malformed arch
tier), while still CLEARING a target that legitimately carries NO architecture
tier at all. The two holes are NOT symmetric -- the `--feature-id` gate runs on
the TARGET repo during DELIVER, and an external target (TS/Go/minimal Python)
legitimately has no nWave `tests/build/` arch tier; refusing it would violate the
STANDING genericità mandate and break the prior `atdd_pure_carpaccio_spine` ATs.

RE-ALLOCATION (fix-e2-whole-tree-scope-blocks-unrelated-slices, 2026-07-30):
slice-02's protections are UNCHANGED and UNWEAKENED; they move to the surface
that now owns the whole-tree architecture tier. The original allocation charged
the present-but-vacuous refusal to the PER-SLICE gate, which meant a malformed
tier owned by ANOTHER concurrent lane refused every lane's slice tree-wide.

  * PER-SLICE, ANY arch-tier state -> CLEAR (exit 0 `FeatureScopeCleared`) + a
    LOUD `BuildTierWholeTreeDeferred` naming feature-end. A slice is judged on
    its OWN scope; the state of a tier it does not own is not its business.
    RED at HEAD for the vacuous shape (production still sweeps per-slice).
  * WHOLE-TREE, arch tier ABSENT        -> CLEAR (`BuildTierNotApplicable`).
    Genericità: no arch tier means no arch invariant to enforce, announced as an
    honest N/A rather than a silent pass.
  * WHOLE-TREE, arch tier collects zero -> REFUSE (exit 1 `BuildTierRefused`
    reason `arch-scope-zero-collected`). The genuinely malformed case: the tier
    is present but would fingerprint a vacuous run. GREEN at HEAD -- pinned as
    an invariant guard the re-allocation must not perturb.
  * WHOLE-TREE, arch tier present + green -> CLEAR control (`BuildTierVerified`
    with a NON-ZERO executed count), guarding against over-refusal of a
    non-vacuous green tier.

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
from .domain_types_slice_01 import (
    BUILD_TIER_NOT_APPLICABLE_EVENT,
    WholeTreeVerdict,
)
from .domain_types_slice_02 import (
    ARCH_SCOPE_ZERO_COLLECTED_REASON,
    FEATURE_SCOPE_CLEARED_EVENT,
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


@then("the whole-tree run reports the architecture scope collected nothing")
def _then_arch_scope_zero_collected(whole_tree_run) -> None:
    # RELOCATED from the per-slice gate. The REFUSE must still surface the
    # precise present-but-vacuous reason `arch-scope-zero-collected`. Precision
    # distinguishes the zero-collected refusal from the keystone
    # arch-invariant-failed refusal -- a tier that collects nothing has
    # certified nothing, and saying so precisely is what makes it fixable.
    assert whole_tree_run.reason == ARCH_SCOPE_ZERO_COLLECTED_REASON, (
        "the whole-tree run refused but did not report reason "
        f"{ARCH_SCOPE_ZERO_COLLECTED_REASON!r} -- a present arch tier that "
        "collects zero invariants must be refused LOUD and named precisely, not "
        f"silently cleared (got reason {whole_tree_run.reason!r}, event "
        f"{whole_tree_run.event!r}, exit {whole_tree_run.exit_code})"
    )


@then("the whole-tree run reports the architecture tier is not applicable")
def _then_whole_tree_not_applicable(whole_tree_run) -> None:
    # Genericità, RELOCATED: a target that legitimately carries NO arch tier
    # must clear with an HONEST N/A -- an explicit "there was nothing to
    # enforce here", never a silent pass claim that would be indistinguishable
    # from "everything checked out".
    assert whole_tree_run.event == BUILD_TIER_NOT_APPLICABLE_EVENT, (
        "a target carrying no architecture tier must clear with an explicit "
        f"{BUILD_TIER_NOT_APPLICABLE_EVENT} -- an honest N/A, never a silent "
        f"pass. Got event {whole_tree_run.event!r} (exit "
        f"{whole_tree_run.exit_code})"
    )


@then("the gate does not over-refuse the absent architecture tier")
def _then_no_over_refuse_absent(gate_run) -> None:
    # Genericità regression guard, UNCHANGED by the re-allocation: a target that
    # legitimately carries NO arch tier must CLEAR (exit 0 FeatureScopeCleared),
    # never be refused for an absent arch scope. An external target (TS/Go/
    # minimal Python) carries no nWave architecture tier at all.
    assert gate_run.event == FEATURE_SCOPE_CLEARED_EVENT, (
        "the gate did not clear a legitimate no-arch-tier target -- it surfaced "
        f"event {gate_run.event!r} (exit {gate_run.exit_code}) instead of "
        "FeatureScopeCleared. An external target (TS/Go/minimal Python) carries no "
        "nWave architecture tier; refusing it over-narrows and violates genericità "
        "(production still over-refuses absent arch tier with arch-scope-empty)"
    )


@then("the system is unchanged")
def _then_system_unchanged(whole_tree_run) -> None:
    # @contract-shape:unbounded-preservation: the run INSPECTS + refuses; it must
    # not mutate the system. The port-exposed observable of "unchanged" is the
    # fail-closed refusal with no side-effect emission beyond the verdict event
    # -- a clean exit 1 (REFUSED), never an UNEXPECTED crash that could have left
    # partial state. (Layer-3 real-IO: traditional assertion per Mandate 8; the
    # universe here is the verdict + the absence of an UNEXPECTED failure mode.)
    assert whole_tree_run.verdict is WholeTreeVerdict.REFUSED, (
        "an arch-tier-vacuity refusal must be a clean fail-closed REFUSED "
        f"(exit 1), leaving the system unchanged; got verdict "
        f"{whole_tree_run.verdict.value!r} (exit {whole_tree_run.exit_code})"
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
    """RELOCATED. For a synthetic repo whose architecture tier EXISTS but
    collects ZERO invariant under the `-m` filter, the WHOLE-TREE architecture
    run REFUSES (exit 1 BuildTierRefused reason `arch-scope-zero-collected`).

    This is the original slice-02 refuse property, moved to the surface that now
    owns the whole-tree tier. The claim is unchanged: nobody earns a verified
    record by "covering an empty arch set" when the tier is present-but-broken.
    What changed is who is blocked -- that feature's own close, not every
    concurrent lane's slice.

    Universe (port-exposed): the whole-tree run's `verdict` (exit-code-exact) +
    its verdict `event` + the named `reason`. Perturbation-bound, not vacuously
    true: the clear property below proves the run CLEARS the non-refuse shapes
    (ABSENT + PRESENT), so a refuse-always property would be over-specified.

    GREEN at HEAD: the whole-tree run already refuses a present-but-vacuous arch
    tier. Pinned as an invariant guard the re-allocation must not perturb -- a
    protection that survives a move only in prose is a protection that was
    dropped.
    """
    composition = R3GateComposition2()
    repo = composition.make_arch_scope_repo(
        tmp_path_factory.mktemp("arch_scope_refuse"),
        shape,
    )

    run = composition.run_whole_tree_arch_gate(repo)

    assert run.verdict is WholeTreeVerdict.REFUSED, (
        "the whole-tree run did not refuse a present-but-vacuous arch tier "
        f"({shape.value!r}) (verdict {run.verdict.value!r}, exit "
        f"{run.exit_code}) -- a present arch tier collecting zero invariants is "
        "malformed and must be refused LOUD"
    )
    assert run.reason == ARCH_SCOPE_ZERO_COLLECTED_REASON, (
        "the refusal did not name reason "
        f"{ARCH_SCOPE_ZERO_COLLECTED_REASON!r} for a {shape.value!r} arch tier "
        f"(got reason {run.reason!r}, event {run.event!r})"
    )


@settings(
    max_examples=3,  # layer-3: each example spawns a real subprocess
    deadline=None,
    suppress_health_check=[HealthCheck.function_scoped_fixture],
)
@given(shape=st.sampled_from(list(ArchScopeShape)))
def test_no_arch_tier_state_ever_blocks_a_slice_whose_own_scope_is_green(
    tmp_path_factory, shape
) -> None:
    """For EVERY architecture-tier state -- absent, present-but-vacuous, or
    present-and-green -- the PER-SLICE gate must CLEAR a slice whose own feature
    scope collects cleanly. The state of a tier the entering slice does not own
    is not that slice's business.

    Universe (port-exposed): the gate's `verdict` (exit-code-exact) + its verdict
    `event`. This property quantifies the WHOLE `ArchScopeShape` domain, which is
    exactly the point: after the re-allocation there is no arch-tier state that
    charges a green slice, so the per-slice verdict is INVARIANT across the
    domain the whole-tree run discriminates on.

    RED at HEAD for the ZERO_COLLECTED shape: production still sweeps the whole
    tier per-slice, so a vacuous tier refuses the slice with
    `arch-scope-zero-collected` instead of deferring.
    """
    composition = R3GateComposition2()
    repo = composition.make_arch_scope_repo(
        tmp_path_factory.mktemp("arch_scope_per_slice"),
        shape,
    )

    run = composition.run_feature_scoped_gate(repo)

    assert run.verdict is GateVerdict.CLEARED, (
        "the per-slice gate refused a slice whose OWN feature scope is fully "
        f"green, over a {shape.value!r} architecture tier it does not own "
        f"(verdict {run.verdict.value!r}, exit {run.exit_code}) -- the "
        "whole-tree architecture tier must be DEFERRED to feature-end, not "
        "charged to every entering slice"
    )


@settings(
    max_examples=8,  # layer-3: each example spawns a real subprocess
    deadline=None,
    suppress_health_check=[HealthCheck.function_scoped_fixture],
)
@given(shape=st.sampled_from([ArchScopeShape.ABSENT, ArchScopeShape.PRESENT]))
def test_non_refuse_arch_scope_clears(tmp_path_factory, shape) -> None:
    """RELOCATED. For ANY synthetic repo whose architecture tier is either
    ABSENT (no `tests/build/`, genericità) or PRESENT-and-green (a non-vacuous
    tier whose invariant holds), the WHOLE-TREE architecture run CLEARS (exit 0).

    The over-refusal guard, moved with the protection it guards: an external
    target (TS/Go/minimal Python) carrying no nWave architecture tier must never
    be refused for its absence, and a genuinely non-vacuous green tier must never
    be refused either. Perturbation-bound: the refuse property above proves the
    present-but-vacuous shape REFUSES, so a clear-always property would be
    over-specified.

    GREEN at HEAD -- pinned as an invariant guard the re-allocation must not
    perturb.
    """
    composition = R3GateComposition2()
    repo = composition.make_arch_scope_repo(
        tmp_path_factory.mktemp("arch_scope_clear"),
        shape,
    )

    run = composition.run_whole_tree_arch_gate(repo)

    assert run.verdict is WholeTreeVerdict.CLEARED, (
        f"the whole-tree run did not clear a non-refuse arch scope "
        f"({shape.value!r}) (verdict {run.verdict.value!r}, exit "
        f"{run.exit_code}) -- ABSENT is a legitimate no-arch-tier target "
        "(genericità) and PRESENT-green is a non-vacuous holding tier; neither "
        "may be over-refused"
    )
