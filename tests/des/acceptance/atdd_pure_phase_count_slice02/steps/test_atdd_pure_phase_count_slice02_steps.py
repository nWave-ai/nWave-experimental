"""Step definitions for the atdd_pure_phase_count slice-02 acceptance suite.

Mandate-12: step bodies are <=2 statements ending in a composition service call
or an assertion against a typed observable. No control flow, no inline business
logic. Domain nouns arrive enum-typed via ``parsers.parse``.

Mandate-13: every step drives the SUT through a Layer-3 subprocess driving port
(``des.cli.phases --resolve``). No production domain/application/adapter symbol
is imported.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from pytest_bdd import given, parsers, scenarios, then, when

from .domain_types import CommitStepWord


if TYPE_CHECKING:
    from .composition import (
        CommitGateOutcome,
        CommitStepGateComposition,
        PhaseResolveComposition,
        ResolutionResult,
    )


scenarios("../atdd_pure_phase_count_slice02.feature")


# --- Givens -----------------------------------------------------------------


@given(
    "the delivery runtime exposes its phase-resolution port",
    target_fixture="resolver",
)
def _given_resolver(phase_resolver: PhaseResolveComposition) -> PhaseResolveComposition:
    return phase_resolver


@given("every canonical phase resolves to itself")
def _given_canonical_self(resolver: PhaseResolveComposition) -> None:
    assert resolver.all_canonical_self_resolve(), (
        "a canonical phase failed self-resolution through the resolve port"
    )


# --- Whens ------------------------------------------------------------------


@when(
    parsers.parse('the operator resolves the phase name "{phase_name}"'),
    target_fixture="resolution",
)
def _when_resolve(
    resolver: PhaseResolveComposition, phase_name: str
) -> ResolutionResult:
    return resolver.resolve(phase_name)


# --- Thens ------------------------------------------------------------------


@then(parsers.parse('the resolved canonical phase is "{expected}"'))
def _then_resolved(resolution: ResolutionResult, expected: str) -> None:
    assert resolution.canonical == expected, (
        f"resolving {resolution.input_name!r}: expected canonical {expected!r}, "
        f"got {resolution.canonical!r} (exit={resolution.exit_code})"
    )


@then("the resolution succeeds")
def _then_resolution_ok(resolution: ResolutionResult) -> None:
    assert not resolution.rejected, (
        f"resolving {resolution.input_name!r} was rejected "
        f"(exit={resolution.exit_code}); expected a lossless replay"
    )


@then("every canonical phase resolves to itself")
def _then_canonical_self(resolver: PhaseResolveComposition) -> None:
    assert resolver.all_canonical_self_resolve(), (
        "a canonical phase failed self-resolution through the resolve port"
    )


@then("the phase name is rejected as unknown")
def _then_rejected(resolution: ResolutionResult) -> None:
    assert resolution.rejected, (
        f"resolving {resolution.input_name!r} was accepted "
        f"(canonical={resolution.canonical!r}); an unknown phase must be "
        f"rejected with a typed error, never silently mapped"
    )


@then("the unknown phase name does not silently map to a canonical phase")
def _then_no_silent_map(resolution: ResolutionResult) -> None:
    assert resolution.canonical == "", (
        f"unknown phase {resolution.input_name!r} silently mapped to "
        f"{resolution.canonical!r}"
    )


# --- Thens: routing/seam outcome (D_GAP_ROUTING third outcome) --------------


@then("the resolution is recognised as a routing event")
def _then_routing(resolution: ResolutionResult) -> None:
    assert resolution.routing, (
        f"resolving {resolution.input_name!r}: expected the routing/seam "
        f"outcome, got canonical={resolution.canonical!r} rejected="
        f"{resolution.rejected} (exit={resolution.exit_code}); the retired "
        f"routing marker must resolve to a routing event, not a phase"
    )


@then("the routing event carries no canonical phase")
def _then_routing_no_phase(resolution: ResolutionResult) -> None:
    assert resolution.canonical == "", (
        f"routing marker {resolution.input_name!r} carried canonical phase "
        f"{resolution.canonical!r}; a routing event maps to no canonical phase"
    )


@then("the routing event is not rejected as unknown")
def _then_routing_not_rejected(resolution: ResolutionResult) -> None:
    assert not resolution.rejected, (
        f"routing marker {resolution.input_name!r} was rejected as unknown "
        f"(exit={resolution.exit_code}); it must be recognised as a routing "
        f"event, distinct from an unknown-phase rejection"
    )


# --- Hook commit-gate routing (C3 re-key, Layer-4 wiring_e2e) ----------------


@given(
    "a returning delivery agent in a workspace with no verified slice commit",
    target_fixture="gate",
)
def _given_returning_agent(
    commit_step_gate: CommitStepGateComposition,
) -> CommitStepGateComposition:
    return commit_step_gate


@when(
    "the agent reports it has finished the canonical commit step",
    target_fixture="last_outcome",
)
def _when_finished_canonical(gate: CommitStepGateComposition) -> CommitGateOutcome:
    return gate.report_finished_commit_step(CommitStepWord.CANONICAL)


@when(
    "the agent reports it has finished the legacy commit step",
    target_fixture="last_outcome",
)
def _when_finished_legacy(gate: CommitStepGateComposition) -> CommitGateOutcome:
    return gate.report_finished_commit_step(CommitStepWord.LEGACY)


@then("the feature-end commit gate stops the agent from closing the slice")
def _then_commit_gate_blocks(last_outcome: CommitGateOutcome) -> None:
    assert last_outcome.blocked, (
        f"the commit step word {last_outcome.word!r} did not route to the "
        f"commit exit-gate: decision={last_outcome.decision!r} "
        f"event={last_outcome.event!r}; expected the gate to block "
        f"(SliceCommitBlocked) -- the C3 dispatch must route this word to the gate"
    )
