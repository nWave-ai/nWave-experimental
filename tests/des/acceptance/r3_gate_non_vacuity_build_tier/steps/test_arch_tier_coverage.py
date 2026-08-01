"""Step definitions for r3-gate-non-vacuity-build-tier slice-01 (Mandate-12).

RE-ALLOCATION (fix-e2-whole-tree-scope-blocks-unrelated-slices, 2026-07-30).
The keystone concern is UNCHANGED and UNWEAKENED -- a slice must not earn a
verified record while breaking an architecture boundary. What moved is WHERE
it is enforced:

  * PER-SLICE (`des run-contract-gate --feature-id`) -- judges the entering
    slice's OWN scope and DEFERS the whole-tree `tests/build/**` tier to
    feature-end, announcing the deferral LOUD (`BuildTierWholeTreeDeferred`
    naming feature-end). It must never refuse a slice over a file belonging to
    a different concurrent lane.
  * FEATURE-END (the whole-tree architecture run) -- still REFUSES every shape
    of run-time architecture-invariant failure, and still NAMES the failing
    invariant.

The original allocation swept the whole tier per-slice, which (measured twice
on 2026-07-30, lanes c1-matcher and D80) refused slices whose OWN scope was
fully green because another lane's legitimate active-RED scaffold was failing
elsewhere. Restores nw-throughput move 3 (C1). Every protection this module
originally encoded is asserted below, at whichever surface now owns it.

Form A (feature-delta §6 ADDENDUM): the keystone threat is still a RUN-TIME arch
invariant (the real F-D-09 gate is a scans-not-imports AST scanner that asserts
at run-time). The synthetic broken-arch tier therefore PASSES collection and
FAILS at run-time; only a collect-AND-RUN observes it -> `BuildTierRefused`
reason `arch-invariant-failed` exit 1 on the whole-tree run.

RED at HEAD: the per-slice legs are genuine RED -- `_mode_feature_scoped` still
resolves the WHOLE-TREE `_arch_invariant_paths(repo)` and runs every member on
every entering slice, so it refuses (exit 2) and names the foreign file. The
whole-tree legs are GREEN today and are pinned as invariant guards the fix must
not perturb. Nothing is xfail-marked: the dispatch requires RED-for-right-reason
to be observable directly.

Step bodies delegate to `R3GateComposition` -- no inline business logic
(Mandate-12 criterion 3: <=2 statements, final = composition.<method>(...), no
control flow). Domain nouns are typed via `domain_types_slice_01` (criterion 1);
the composition service signatures consume those typed parameters (criterion 2).

Mandate-13: the SUT is driven exclusively through the real `des
run-contract-gate --feature-id` CLI as a Layer-3 subprocess black-box (see
composition). Mandate-9/11: layer-3 real-IO -> example-only; the paired PBT
property (`test_arch_tier_coverage_property`) lives at the SAME driving port and
is example-budgeted small (it spawns a real subprocess per example).
"""

from __future__ import annotations

import pytest
from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st
from pytest_bdd import given as bdd_given
from pytest_bdd import parsers, scenarios, then

from .common_steps import *
from .composition_slice_01 import R3GateComposition
from .domain_types_slice_01 import (
    ARCH_INVARIANT_FAILED_REASON,
    ArchTierState,
    ArchViolationShape,
    GateVerdict,
)


# The architecture tier's home. A PER-SLICE verdict must never name anything
# under it: in this fixture the entering slice's own scope lives under
# `tests/arch_probe_fixture/`, so a `tests/build/` path in the per-slice verdict
# is BY CONSTRUCTION a file the entering slice never touched -- the exact
# refusal shape fix-e2-whole-tree-scope-blocks-unrelated-slices exists to stop.
_ARCH_TIER_HOME = "tests/build"


scenarios("../slice-01-arch-tier-coverage.feature")


# The human-readable Gherkin token for each arch-violation shape (Pillar 1:
# the `.feature` speaks domain language; this maps the token to the typed enum
# at the test boundary, keeping the Scenario Outline readable).
_VIOLATION_BY_PHRASE = {
    "forbidden dev-root import": ArchViolationShape.FORBIDDEN_DEV_ROOT_IMPORT,
    "inline interpreter spawn": ArchViolationShape.INLINE_INTERPRETER_SPAWN,
    "seeded runtime assertion": ArchViolationShape.SEEDED_RUNTIME_ASSERTION,
}


@pytest.fixture
def composition() -> R3GateComposition:
    """The production composition root driving the real contract-gate CLI."""
    return R3GateComposition()


# ===========================================================================
# Given -- slice-01-specific (the shared clean-feature-scope Given comes from
# common_steps; S1 single SSOT)
# ===========================================================================


@bdd_given("the architecture tier holds every invariant")
def _given_arch_clean(composition: R3GateComposition, repo) -> None:
    """Seed a CLEAN arch tier (an arch test under tests/build/ that runs GREEN)."""
    composition.make_probe_repo(repo, ArchTierState.CLEAN)


@bdd_given(parsers.parse("the architecture tier fails a run-time {phrase} invariant"))
def _given_arch_violation_shape(
    composition: R3GateComposition, repo, phrase: str
) -> None:
    """Seed a BROKEN arch tier of the requested run-time shape (Scenario Outline)."""
    composition.make_probe_repo(
        repo, ArchTierState.BROKEN, _VIOLATION_BY_PHRASE[phrase]
    )


# ===========================================================================
# When -- imported from common_steps (shared SSOT, S1)
# ===========================================================================


# ===========================================================================
# Then -- slice-01-specific (the shared verdict Thens come from common_steps)
# ===========================================================================


@then("the whole-tree run reports the architecture invariant failed")
def _then_arch_invariant_failed(whole_tree_run) -> None:
    # RELOCATED from the per-slice gate. The keystone REFUSE must still surface
    # the reason `arch-invariant-failed` -- not a bare crash and not a different
    # floor-trip reason (arch-scope-zero-collected). Precision: distinguishes
    # the keystone run-time-arch-failure refusal from any other cause.
    assert whole_tree_run.reason == ARCH_INVARIANT_FAILED_REASON, (
        "the whole-tree run refused but did not report reason "
        f"{ARCH_INVARIANT_FAILED_REASON!r} -- the refusal must name the run-time "
        "arch-invariant failure, not a generic floor trip (got reason "
        f"{whole_tree_run.reason!r}, event {whole_tree_run.event!r}, exit "
        f"{whole_tree_run.exit_code})"
    )


@then("the whole-tree run names the failing architecture invariant")
def _then_whole_tree_names_the_failure(whole_tree_run) -> None:
    # GDP-3 (WHAT/WHY/HOW) at the relocated surface: the protection did not
    # merely survive the move, it stayed ACTIONABLE -- the refusal still names
    # WHICH invariant broke, so the feature owner can fix it before their close.
    assert whole_tree_run.names(_ARCH_TIER_HOME), (
        "the whole-tree refusal must NAME the failing architecture test so the "
        "feature owner can act on it -- a refusal that does not say which "
        f"invariant broke is not actionable. Got {whole_tree_run.events}"
    )


@then("the refusal never names a file outside the entering slice's own scope")
def _then_no_foreign_file_named(gate_run) -> None:
    # THE DEFECT SHAPE this re-allocation exists to stop: a per-slice verdict
    # naming a file belonging to a lane the blocked maintainer has never opened,
    # with no action available to them other than fixing somebody else's
    # in-flight work. In this fixture the entering slice's own scope lives under
    # `tests/arch_probe_fixture/`, so any `tests/build/` path in the per-slice
    # verdict is by construction foreign to it.
    assert _ARCH_TIER_HOME not in gate_run.stdout, (
        "the per-slice verdict names a file under "
        f"{_ARCH_TIER_HOME!r} -- a file the entering slice never touched, "
        "belonging to whichever lane owns that architecture tier. A legitimate "
        "refusal must name something the maintainer can act on INSIDE THEIR OWN "
        f"SCOPE. Verdict stdout: {gate_run.stdout.strip()[:400]!r}"
    )


# ===========================================================================
# Paired property (Mandate 9/11: layer-3 example-budgeted PBT at the SAME
# driving port). Universe = the gate's exit-code-derived verdict (port-exposed).
# ===========================================================================


@settings(
    max_examples=3,  # layer-3: each example spawns a real worker subprocess
    deadline=None,
    suppress_health_check=[HealthCheck.function_scoped_fixture],
)
@given(violation=st.sampled_from(list(ArchViolationShape)))
def test_whole_tree_run_refuses_every_shape_of_architecture_failure(
    tmp_path_factory, violation
) -> None:
    """RELOCATED KEYSTONE. For ANY synthetic repo whose architecture tier fails
    a RUN-TIME invariant of ANY shape (Form A: the tier PASSES collection, FAILS
    at run-time), the WHOLE-TREE architecture run REFUSES (exit 1
    BuildTierRefused).

    This is the original slice-01 property, moved to the surface that now owns
    the protection. The claim it defends is unchanged: a feature cannot close
    while an architecture-boundary invariant is broken, for ANY shape of break.
    What changed is WHO is blocked -- that feature's own close, not every
    concurrent lane's slice.

    Universe (port-exposed): the whole-tree run's `verdict` (exit-code-exact) +
    its structured verdict event. Perturbation-bound (broken arch tier), not
    vacuously true: with a CLEAN arch tier the whole-tree run CLEARS by design
    (asserted by the non-vacuous clean-tier scenario), so a refuse-always
    property would be over-specified.
    """
    composition = R3GateComposition()
    repo = composition.make_probe_repo(
        tmp_path_factory.mktemp("arch_probe_whole_tree"),
        ArchTierState.BROKEN,
        violation,
    )

    run = composition.run_whole_tree_arch_gate(repo)

    assert run.verdict is WholeTreeVerdict.REFUSED, (
        "the whole-tree architecture run did not refuse a repository breaking "
        f"the architecture tier with a {violation.value!r} violation (verdict "
        f"{run.verdict.value!r}, exit {run.exit_code}) -- this run is where the "
        "keystone protection relocated to; if it clears here, the protection "
        "was dropped, not moved"
    )
    assert run.reason == ARCH_INVARIANT_FAILED_REASON, (
        "the whole-tree run refused but surfaced no "
        f"{ARCH_INVARIANT_FAILED_REASON!r} reason for a {violation.value!r} "
        f"violation (reason {run.reason!r}, event {run.event!r})"
    )


@settings(
    max_examples=3,  # layer-3: each example spawns a real subprocess
    deadline=None,
    suppress_health_check=[HealthCheck.function_scoped_fixture],
)
@given(violation=st.sampled_from(list(ArchViolationShape)))
def test_per_slice_gate_never_blocks_a_green_slice_over_a_foreign_arch_failure(
    tmp_path_factory, violation
) -> None:
    """For ANY shape of run-time architecture failure living in a file the
    entering slice never touched, the PER-SLICE gate must still CLEAR a slice
    whose own feature scope collects cleanly -- and must never name that foreign
    file in its verdict.

    Universe (port-exposed): the gate's `verdict` (exit-code-exact) + the
    verdict text on stdout. Perturbation-bound over the arch-violation shape
    domain; the feature scope is held clean throughout, because the defect is
    precisely that a fully-green own scope was refused anyway.

    RED at HEAD: `_mode_feature_scoped` resolves the WHOLE-TREE
    `_arch_invariant_paths(repo)` and runs every member on every entering slice,
    so the gate refuses (exit 2) for every shape, naming the foreign file.
    """
    composition = R3GateComposition()
    repo = composition.make_probe_repo(
        tmp_path_factory.mktemp("arch_probe_per_slice"),
        ArchTierState.BROKEN,
        violation,
    )

    run = composition.run_feature_scoped_gate(repo)

    assert run.verdict is GateVerdict.CLEARED, (
        "the per-slice gate refused a slice whose OWN feature scope is fully "
        f"green, over a {violation.value!r} architecture failure it never "
        f"touched (verdict {run.verdict.value!r}, exit {run.exit_code}) -- the "
        "whole-tree architecture tier must be DEFERRED to feature-end, not swept "
        "on every entering slice"
    )
    assert _ARCH_TIER_HOME not in run.stdout, (
        "the per-slice verdict names a file under "
        f"{_ARCH_TIER_HOME!r} that the entering slice never touched, for a "
        f"{violation.value!r} violation -- got {run.stdout.strip()[:400]!r}"
    )
