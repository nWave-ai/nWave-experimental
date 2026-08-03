"""Step bindings -- slice-01 (@walking-skeleton refuse path, O-1-independent).

The readiness gate REFUSES a feature-delta carrying neither a `## Reuse
Analysis` section nor a `## Wave: DESIGN / [REF] Design Skipped` witness, with
the net-new `reuse_first_or_design_skip` invariant FAILED and the (now four,
post fix-readiness-carpaccio-disagree) pre-existing invariants unchanged. Also
covers the two DESIGN-flagged tokens (malformed-reuse-analysis,
unjustified-create-new) -> ABSENT/refuse degrade-LOUD.

The step text below still literally reads "the five pre-existing ..." -- that
string is the Gherkin `.feature` contract (crafter does not edit `.feature`
files); the PYTHON side it drives now asserts over the 4 surviving members of
`PRE_EXISTING_INVARIANTS` only.

Mandate-13 (S2 driving-port-only): step modules import ONLY the composition root
(from conftest fixture) + `domain_types`. ZERO `from des.<domain|application|
adapters>.<x>` direct-domain imports. The driving port is the real
`des verify-readiness-pre-dispatch` CLI subprocess via `composition.verify()`.

Mandate-12 criterion 3: every step body is <=2 statements, the final statement
is a `composition.<method>(...)` call; no control flow in step bodies.

S1 step-text uniqueness: every literal `@given/@when/@then` arg here is unique
within the `readiness_reuse_invariant` feature scope; slice-02 literals are
distinct (parametrized templates carry distinct placeholder sets).
"""

from __future__ import annotations

from pytest_bdd import given, parsers, then, when

from .domain_types import (
    PRE_EXISTING_INVARIANTS,
    REUSE_SHAPE_BY_PHRASE,
    WITNESS_BY_PHRASE,
    FirstDispatchInvariantId,
    InvariantStatus,
    ReadinessVerdict,
)


# --- Given: arm a five-invariant-satisfying workspace, varying the reuse dim --


@given(
    parsers.parse(
        "a complete feature workspace with {reuse_phrase} and {witness_phrase}"
    )
)
def given_workspace_with_reuse_and_witness(
    readiness_reuse_composition, reuse_phrase: str, witness_phrase: str
) -> None:
    readiness_reuse_composition.arm_feature_delta(
        REUSE_SHAPE_BY_PHRASE[reuse_phrase], WITNESS_BY_PHRASE[witness_phrase]
    )


# --- When: drive the real readiness gate subprocess ------------------------


@when("the maintainer runs the readiness gate before first crafter dispatch")
def when_maintainer_runs_readiness_gate(readiness_reuse_composition) -> None:
    readiness_reuse_composition.verify()


# --- Then: observable verdict + 6th-invariant status + unchanged 5 ----------


@then("the readiness gate refuses the dispatch")
def then_gate_refuses(readiness_reuse_composition) -> None:
    assert readiness_reuse_composition.last_verdict() is ReadinessVerdict.REFUSED


@then("the reuse-first invariant is reported as failed")
def then_reuse_first_failed(readiness_reuse_composition) -> None:
    assert (
        readiness_reuse_composition.last_invariant_status(
            FirstDispatchInvariantId.REUSE_FIRST
        )
        is InvariantStatus.FAILED
    )


@then(
    "the remediation names both the Reuse Analysis section and the Design Skipped witness"
)
def then_remediation_names_both_paths(readiness_reuse_composition) -> None:
    assert readiness_reuse_composition.last_remediation_contains(
        FirstDispatchInvariantId.REUSE_FIRST, "Reuse Analysis"
    ) and readiness_reuse_composition.last_remediation_contains(
        FirstDispatchInvariantId.REUSE_FIRST, "Design Skipped"
    )


@then("the remediation names the malformed reuse cause")
def then_remediation_names_malformed_cause(readiness_reuse_composition) -> None:
    # DESIGN degrade-LOUD: the FAIL remediation is prefixed with the
    # `validate_reuse_analysis_content` `detail`. The malformed fixture trips a
    # column-mismatch, whose detail names the "canonical" five-column header --
    # the discriminating token DELIVER must surface (not a generic "missing").
    assert readiness_reuse_composition.last_remediation_contains(
        FirstDispatchInvariantId.REUSE_FIRST, "canonical"
    )


@then("the remediation names the unjustified create-new cause")
def then_remediation_names_unjustified_cause(readiness_reuse_composition) -> None:
    assert readiness_reuse_composition.last_remediation_contains(
        FirstDispatchInvariantId.REUSE_FIRST, "Justification"
    )


@then("the five pre-existing first-dispatch invariants are still reported as satisfied")
def then_five_pre_existing_unchanged(readiness_reuse_composition) -> None:
    expected = dict.fromkeys(PRE_EXISTING_INVARIANTS, InvariantStatus.SATISFIED)
    assert readiness_reuse_composition.pre_existing_invariants_unchanged(expected)


@then("the feature workspace files are unchanged after the gate ran")
def then_workspace_files_unchanged(readiness_reuse_composition) -> None:
    # Witnesses @contract-shape:unbounded-preservation: the closed-world FS
    # snapshot taken around verify() proves the readiness gate is read-only.
    assert readiness_reuse_composition.verify_was_filesystem_preserving()
