"""pytest-bdd binding for f-wave-contract-coherence slice-05 (greenfield triangle).

Driving surface (Mandate-13 driving-port-only): the REAL shipped DISCUSS gate-IN
spine seam (``PreToolUseService._discuss_gate_in_invoker`` over the production
``DiscussGateIn.evaluate`` pure core), the REAL shipped DISCUSS prose, and the REAL
shipped layout validator -- composition_greenfield_triangle.py. Step bodies delegate
to the composition root; no business logic in step bodies (Mandate-12). The
``locus`` example column is coerced to the ``DiscussBootstrapLocus`` enum at the step
boundary -- the DSL ranges over the enum members (command + skill), not a decorator
per locus.

Active-RED scaffold (atdd_pure -- NOT @skip): each scenario is RED until DELIVER
declasses the MIGRATION_UNMET veto -> advisory (AT-12), reconciles bootstrap-ownership
to DIVERGE-owns in both prose loci (AT-13), and retires the legacy ``discuss/*.md``
output enumeration from the command prose (AT-14). At HEAD the spine hard-blocks a
greenfield entry, both loci carry the stale DISCUSS-bootstraps claim, and the command
prose still enumerates legacy outputs -> every Then fires a semantic AssertionError,
never a collection / import / setup error. The end-state halves a prior ADR-FLOW-002
Q4 ship may already satisfy are asserted as end-state (idempotent -- green either way).
"""

from __future__ import annotations

import pytest
from pytest_bdd import given, parsers, scenarios, then, when

from .composition_greenfield_triangle import GreenfieldTriangleComposition
from .domain_types import DiscussBootstrapLocus


scenarios("../greenfield-triangle.feature")


@pytest.fixture
def triangle() -> GreenfieldTriangleComposition:
    return GreenfieldTriangleComposition()


# --- AT-12: greenfield gate-IN ---------------------------------------------


@given("a greenfield project where docs/product is absent")
def given_greenfield_project(triangle: GreenfieldTriangleComposition) -> None:
    triangle.given_greenfield_project()


@when("the DISCUSS gate-in is evaluated for the greenfield project")
def when_discuss_gate_in_evaluated(triangle: GreenfieldTriangleComposition) -> None:
    triangle.when_discuss_gate_in_evaluated_for_greenfield()


@then("the DISCUSS gate-in does not hard-block the wave entry")
def then_gate_in_does_not_hard_block(
    triangle: GreenfieldTriangleComposition,
) -> None:
    triangle.then_gate_in_does_not_hard_block()


@then("the INDETERMINATE degrade-loud veto is left intact for an unreadable root")
def then_indeterminate_veto_left_intact(
    triangle: GreenfieldTriangleComposition,
) -> None:
    triangle.then_indeterminate_veto_left_intact()


# --- AT-13: bootstrap-ownership reconcile ----------------------------------


@given(parsers.parse("the shipped DISCUSS {locus} bootstrap-ownership prose"))
def given_shipped_bootstrap_prose(
    triangle: GreenfieldTriangleComposition, locus: str
) -> None:
    triangle.given_shipped_bootstrap_prose(DiscussBootstrapLocus[locus.upper()])


@then(
    "the shipped DISCUSS prose carries no stale DISCUSS-bootstraps-docs-product claim"
)
def then_no_stale_discuss_bootstraps_claim(
    triangle: GreenfieldTriangleComposition,
) -> None:
    triangle.then_no_stale_discuss_bootstraps_claim()


@then("the shipped DISCUSS prose attributes greenfield bootstrap to DIVERGE")
def then_attributes_bootstrap_to_diverge(
    triangle: GreenfieldTriangleComposition,
) -> None:
    triangle.then_attributes_bootstrap_to_diverge()


# --- AT-14: legacy discuss/*.md retirement ---------------------------------


@given("the shipped layout validator and the shipped DISCUSS command prose")
def given_layout_validator_and_command_prose(
    triangle: GreenfieldTriangleComposition,
) -> None:
    triangle.given_layout_validator_and_command_prose()


@then("the layout validator rejects a legacy discuss multi-file output")
def then_validator_rejects_legacy_discuss_output(
    triangle: GreenfieldTriangleComposition,
) -> None:
    triangle.then_validator_rejects_legacy_discuss_output()


@then(
    "the shipped DISCUSS command prose enumerates no legacy discuss multi-file outputs"
)
def then_command_prose_enumerates_no_legacy_outputs(
    triangle: GreenfieldTriangleComposition,
) -> None:
    triangle.then_command_prose_enumerates_no_legacy_outputs()
