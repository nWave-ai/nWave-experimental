"""Step definitions for r3-gate-non-vacuity-build-tier slice-01 (Mandate-12).

slice-01 (walking skeleton) -- the per-slice exit gate
(`des run-contract-gate --feature-id <f> --entering-slice <s>`) must cover the
architecture tier (`tests/build/**`), not just the feature's own `.feature`
scope. Today it narrows collection to the feature scope (collect-only) and
neither runs NOR collects `tests/build/`, so a slice that fails a RUN-TIME
arch-boundary invariant clears its feature scope and earns a verified record --
while the whole-tree pre-push gate (which RUNS the suite) would have refused it.

Form A (feature-delta §6 ADDENDUM): the keystone threat is a RUN-TIME arch
invariant (the real F-D-09 gate is a scans-not-imports AST scanner that asserts
at run-time). The synthetic broken-arch tier therefore PASSES collection and
FAILS at run-time; only the collect-AND-RUN fix (`--run` worker branch) observes
it -> `FeatureScopeMalformed` reason `arch-invariant-failed` exit 2.

These ATs are genuine RED at HEAD: the arch-invariant collect-AND-RUN does not
exist yet, so the gate clears the slice (exit 0) even when the synthetic arch
tier fails at run-time. GREEN (after DELIVER ships the `--run` branch +
`_arch_invariant_paths` + `_run_arch_invariant_set`) makes the gate refuse the
broken-arch slice (exit 2). They are NOT xfail-marked: the dispatch requires
RED-for-right-reason to be observable directly.

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

from .common_steps import *  # noqa: F403 (shared step SSOT -- S1 single-source re-use)
from .composition_slice_01 import R3GateComposition
from .domain_types_slice_01 import (
    ARCH_INVARIANT_FAILED_REASON,
    ArchTierState,
    ArchViolationShape,
    GateVerdict,
)


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


@then("the gate reports the architecture invariant failed")
def _then_arch_invariant_failed(gate_run) -> None:
    # The REFUSE must surface the malformed verdict event with the KEYSTONE
    # reason `arch-invariant-failed` (§6.2 join point) -- not a bare crash and
    # not a different floor-trip reason (zero-collected / arch-scope-zero-collected).
    # Precision: distinguishes the keystone run-time-arch-failure refusal from
    # any other malformed cause.
    assert gate_run.event == "FeatureScopeMalformed", (
        "the gate refused but did not surface a FeatureScopeMalformed verdict "
        f"(saw event {gate_run.event!r}, exit {gate_run.exit_code}) -- the run-time "
        "arch failure must be observed in the feature-scoped verdict, not a silent "
        "crash (arch-invariant collect-AND-RUN not yet delivered)"
    )
    assert ARCH_INVARIANT_FAILED_REASON in gate_run.stdout, (
        "the gate refused but did not report reason "
        f"{ARCH_INVARIANT_FAILED_REASON!r} -- the malformed verdict must name the "
        "run-time arch-invariant failure, not a generic floor trip "
        f"(stdout: {gate_run.stdout.strip()[:300]!r})"
    )


# ===========================================================================
# Paired property (Mandate 9/11: layer-3 example-budgeted PBT at the SAME
# driving port). Universe = the gate's exit-code-derived verdict (port-exposed).
# ===========================================================================


@settings(
    max_examples=12,  # layer-3: each example spawns a real subprocess
    deadline=None,
    suppress_health_check=[HealthCheck.function_scoped_fixture],
)
@given(violation=st.sampled_from(list(ArchViolationShape)))
def test_arch_tier_coverage_property(tmp_path_factory, violation) -> None:
    """For ANY synthetic repo whose feature `.feature` scope is all-clean AND
    whose architecture tier fails a RUN-TIME invariant of ANY shape (Form A: the
    tier PASSES collection, FAILS at run-time), the feature-scoped exit gate
    REFUSES (exit 2 FeatureScopeMalformed).

    Universe (port-exposed): the gate's `verdict` (derived exit-code-exact from
    the CLI's exit code) + the structured verdict `event` on stdout. The
    property quantifies over the arch-violation shape domain
    (`ArchViolationShape`); the feature scope is held clean.

    RED at HEAD: the feature-scoped gate neither runs nor collects tests/build/**,
    so the gate CLEARS (exit 0) for every shape -- the run-time arch failure is
    invisible. The property is perturbation-bound (broken arch tier), not
    vacuously true: with a CLEAN arch tier the gate CLEARS by design (asserted by
    the example-based clean-arch scenario), so a refuse-always property would be
    over-specified.
    """
    composition = R3GateComposition()
    repo = composition.make_probe_repo(
        tmp_path_factory.mktemp("arch_probe"),
        ArchTierState.BROKEN,
        violation,
    )

    run = composition.run_feature_scoped_gate(repo)

    assert run.verdict is GateVerdict.REFUSED, (
        f"the feature-scoped gate did not refuse a slice breaking the architecture "
        f"tier with a {violation.value!r} violation (verdict {run.verdict.value!r}, "
        f"exit {run.exit_code}) -- tests/build/** is excluded from the feature "
        "scope, so the arch violation is invisible (arch-tier union not delivered)"
    )
    assert run.event == "FeatureScopeMalformed", (
        f"the gate refused but surfaced no FeatureScopeMalformed verdict for a "
        f"{violation.value!r} violation (event {run.event!r})"
    )
