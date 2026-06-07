"""Slice-02 step bindings -- contract-gate fail-closed on a suppressed scope.

Driving port: the real ``des run-contract-gate --verify-gate-scope`` CLI
subprocess (Layer 3, Mandate-13) -- the EXIT-GATE path the G_COMMIT commit gate
actually runs (slice-01 wired its parity guard only into ``--print-digest``).
Step bodies are <=2-statement delegations to the composition root (Mandate-12);
all logic lives there. No production import.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from pytest_bdd import given, parsers, scenarios, then, when

from .domain_types import GateVerdict, ScopeIntegrity


if TYPE_CHECKING:
    from .composition import ContractGateDigestComposition


scenarios("../slice-02-gate-fails-closed-on-suppressed-scope.feature")


@given(
    parsers.parse(
        "the contract gate is asked to verify a tree that suppresses its "
        "collected scope"
    )
)
def _given_suppressed_tree(composition: ContractGateDigestComposition) -> None:
    composition.stage_tree(ScopeIntegrity.SUPPRESSED)


@given(
    parsers.parse(
        "the contract gate is asked to verify a tree with an honest collected scope"
    )
)
def _given_honest_tree(composition: ContractGateDigestComposition) -> None:
    composition.stage_tree(ScopeIntegrity.HONEST)


@when(parsers.parse("the operator verifies the gate scope through the commit gate"))
def _when_verify(composition: ContractGateDigestComposition) -> None:
    composition.verify_gate_scope_via_commit_gate()


@then(parsers.parse("the contract gate fails closed"))
def _then_failed_closed(composition: ContractGateDigestComposition) -> None:
    composition.assert_gate_verdict(GateVerdict.FAILED_CLOSED)


@then(parsers.parse("the contract gate reaches a verdict"))
def _then_reaches_verdict(composition: ContractGateDigestComposition) -> None:
    composition.assert_gate_verdict(GateVerdict.PRODUCED)
