"""pytest-bdd binding for f-wave-contract-coherence slice-03 (DISCUSS prose pointers).

Driving surface (Mandate-13 driving-port-only): the REAL
``des verify-wave-contract-coherence`` subcommand (the slice-02 shipped gate) invoked
as a Layer-3 subprocess over the REAL shipped DISCUSS prose + registry
(composition_discuss_pointers.py). Step bodies delegate to the composition root; no
business logic in step bodies (Mandate-12). The ``locus`` example column is coerced to
the ``DiscussProseLocus`` enum at the step boundary -- the DSL ranges over the enum
members (command + skill), not a decorator per locus.

Active-RED scaffold (atdd_pure -- NOT @skip): each scenario is RED until DELIVER adds
the ``gates-ref``/``outputs-ref`` pointers and STRIPS the inline gate-id / [REF]-section
restatement from both shipped DISCUSS prose loci. At HEAD the shipped prose carries no
pointer and still restates ``validate-feature-delta`` inline, so AT-7's structural facts
are false and AT-8's gate emits FAIL not PASS -> every Then fires a semantic
AssertionError naming the missing pointer / surviving restatement / FAIL verdict, never
a collection / import / setup error.
"""

from __future__ import annotations

import pytest
from pytest_bdd import given, parsers, scenarios, then, when

from .composition_discuss_pointers import DiscussPointersComposition
from .domain_types import CoherenceVerdict, DiscussProseLocus


scenarios("../discuss-prose-pointers.feature")


@pytest.fixture
def gate() -> DiscussPointersComposition:
    return DiscussPointersComposition()


# --- Given -----------------------------------------------------------------


@given(parsers.parse("the shipped DISCUSS {locus} prose"))
def given_shipped_discuss_prose(gate: DiscussPointersComposition, locus: str) -> None:
    gate.given_shipped_discuss_prose(DiscussProseLocus[locus.upper()])


# --- When ------------------------------------------------------------------


@when("the maintainer runs the coherence-check gate over the DISCUSS prose")
def when_maintainer_runs_coherence_check_over_discuss(
    gate: DiscussPointersComposition,
) -> None:
    gate.when_maintainer_runs_coherence_check_over_discuss()


# --- Then ------------------------------------------------------------------


@then("the shipped DISCUSS prose carries both gates-ref and outputs-ref pointers")
def then_prose_carries_both_pointers(gate: DiscussPointersComposition) -> None:
    gate.then_prose_carries_both_pointers()


@then("the shipped DISCUSS prose restates no catalog gate-id inline")
def then_prose_restates_nothing_inline(gate: DiscussPointersComposition) -> None:
    gate.then_prose_restates_nothing_inline()


@then("the coherence-check gate emits the PASS verdict")
def then_gate_emits_pass(gate: DiscussPointersComposition) -> None:
    gate.then_gate_emits_verdict(CoherenceVerdict.PASS)
