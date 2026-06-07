"""Step bindings for D4 Phase 3 slice-03 D1 readiness pre-dispatch gate.

Mandate-12 criterion 3 -- every step body has <=2 statements, the final
statement is `composition.<method>(...)`. NO control flow (`if`/`for`/
`while`/`try`) in step bodies. The DSL emerges from typed parameter coercion
via `parsers.parse` + `domain_types` enum lookups.

Mandate-13 (S2 driving-port-only) -- step modules import ONLY the slice-03
composition root from conftest + `domain_types`. ZERO `from des.<domain|
application|adapters>.<x> import <internal>` direct-domain imports. The
public driving-port entry is `des verify-readiness-pre-dispatch` CLI
subcommand (Layer 3 subprocess) exposed via the
`readiness_composition.verify()` composition method; step bodies never reach
into gate internals.

S1 step-text uniqueness -- every literal `@given/@when/@then` arg in this
module is unique within the `d4_phase_3_flavor_dispatcher` feature scope
(distinct from `steps_dispatcher.py` slice-01 + `steps_carpaccio_refactor.py`
slice-02 literals -- slice-03 talks about "the readiness gate composition",
"the operator runs the readiness gate", "the readiness verdict refuses /
clears", "the diagnostic names ... invariant", "the system filesystem is
unchanged"). No collision.
"""

from __future__ import annotations

from pytest_bdd import given, parsers, then, when

from .domain_types import (
    INVARIANT_BY_PHRASE,
    FirstDispatchInvariantId,
    InvariantStatus,
    ReadinessVerdict,
)


# --- Background ------------------------------------------------------------


@given("the readiness gate composition is available")
def given_readiness_composition(readiness_composition) -> None:
    assert readiness_composition is not None


# --- Given: workspace authoring -------------------------------------------


@given("a feature workspace with no feature delta authored")
def given_workspace_without_feature_delta(readiness_composition) -> None:
    readiness_composition.workspace_without_feature_delta()


@given("a feature workspace with a feature delta lacking the slice plan heading")
def given_workspace_missing_slice_plan_heading(readiness_composition) -> None:
    readiness_composition.workspace_missing_slice_plan_heading()


@given("a feature workspace satisfying every first-dispatch invariant")
def given_workspace_satisfying_every_invariant(readiness_composition) -> None:
    readiness_composition.workspace_satisfying_every_invariant()


# --- When: gate invocation -------------------------------------------------


@when("the operator runs the readiness gate for the workspace")
def when_operator_runs_gate(readiness_composition) -> None:
    readiness_composition.verify()


# --- Then: observable verdict + diagnostic -------------------------------


@then("the readiness verdict refuses dispatch")
def then_verdict_refuses(readiness_composition) -> None:
    assert readiness_composition.last_verdict() is ReadinessVerdict.REFUSED


@then("the readiness verdict clears the dispatch")
def then_verdict_clears(readiness_composition) -> None:
    assert readiness_composition.last_verdict() is ReadinessVerdict.CLEARED


@then(parsers.parse("the diagnostic names the {invariant_phrase} invariant as failed"))
def then_diagnostic_names_invariant_failed(
    readiness_composition, invariant_phrase: str
) -> None:
    invariant = INVARIANT_BY_PHRASE[invariant_phrase]
    assert (
        readiness_composition.last_invariant_status(invariant) is InvariantStatus.FAILED
    )


@then("the diagnostic remediation mentions the missing slice plan heading")
def then_remediation_mentions_slice_plan(readiness_composition) -> None:
    assert readiness_composition.last_remediation_mentions(
        FirstDispatchInvariantId.SLICE_PLAN_SECTION, "Slice Plan"
    )


@then("the diagnostic names every first-dispatch invariant as satisfied")
def then_every_invariant_satisfied(readiness_composition) -> None:
    assert readiness_composition.every_invariant_satisfied() is True


@then("the system filesystem is unchanged")
def then_filesystem_unchanged(readiness_composition) -> None:
    # Closed-world filesystem oracle (Mandate-14 unbounded-preservation): the
    # composition snapshotted the bounded repo_root workspace tree (paths +
    # sha256 content fingerprints) immediately before and after the gate's
    # verify() subprocess. This asserts the two snapshots are byte-identical --
    # the readiness gate's read-only guarantee. Falsifiable: any write under
    # the workspace during verify() flips this RED. Verdict coverage stays
    # pinned independently by then_verdict_refuses.
    assert readiness_composition.verify_was_filesystem_preserving() is True
