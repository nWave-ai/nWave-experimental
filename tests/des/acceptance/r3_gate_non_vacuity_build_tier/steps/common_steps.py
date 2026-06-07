"""Shared step-method SSOT for r3-gate-non-vacuity-build-tier (Mandate-12 + S1).

The When + the verdict-shaped Then steps are SHARED across every slice of this
feature (slice-01 keystone, slice-02 arch-scope non-vacuity, future slices).
They are declared ONCE here -- the S1 step-text-uniqueness invariant
(`nw-at-completeness-check` §2-bis) requires a single SSOT module rather than
duplicate `@then("the gate refuses the slice")` bodies across slice files
(which would shadow in pytest-bdd's process-global registry -> silent test
inversion).

Each slice's test binding does `from .common_steps import *` (the S1 tolerable
"single SSOT module, designed re-use" variant). The step bodies delegate to the
shared `gate_run` observable derived from the `R3GateComposition` driving port;
they are agnostic to WHICH slice produced the run (slice-01 broken-arch run-time
failure, slice-02 vacuous arch scope) -- both observe the same exit-code-exact
verdict + the structured verdict event on stdout.

Mandate-13: the driving port (`run_feature_scoped_gate`) is a Layer-3 subprocess
black-box; these steps observe ONLY the CLI's exit code + stdout JSON verdict
event. Mandate-12 criterion 3: step bodies are <=2 statements / assertion-only,
no business logic, no control flow beyond the assertion message expression.
"""

from __future__ import annotations

from pytest_bdd import given as bdd_given
from pytest_bdd import then, when

from .composition_slice_01 import R3GateComposition
from .domain_types_slice_01 import GateVerdict


# The slice bindings do `from .common_steps import *` (the proven repo idiom +
# the S1 tolerable "single SSOT module" variant). The step functions carry
# NON-underscore names so `import *` exports them (underscore names are excluded
# from star-import) and so the formatter does not prune them -- pytest-bdd
# discovers the decorated functions by their module-level names.


# ===========================================================================
# Given (shared across all slices -- S1 single SSOT declaration)
# ===========================================================================


@bdd_given(
    "a slice whose feature scope collects cleanly",
    target_fixture="repo",
)
def given_clean_feature_scope(composition: R3GateComposition, tmp_path):
    """Precondition: a synthetic repo whose feature `.feature` scope is clean.

    Writes ONLY the clean feature scope (no arch tier) -- the subsequent
    slice-specific arch Given writes the arch tier on top. `composition` is the
    slice's fixture (slice-01 `R3GateComposition`, slice-02 `R3GateComposition2`
    subclass); both expose `make_clean_feature_scope_repo`.
    """
    return composition.make_clean_feature_scope_repo(tmp_path)


# ===========================================================================
# When (shared across all slices)
# ===========================================================================


@when(
    "the exit gate certifies the slice over its feature scope",
    target_fixture="gate_run",
)
def when_certify_slice(composition: R3GateComposition, repo):
    """Drive the real `des run-contract-gate --feature-id` CLI (subprocess)."""
    return composition.run_feature_scoped_gate(repo)


# ===========================================================================
# Then -- verdict-shaped, slice-agnostic (shared across all slices)
# ===========================================================================


@then("the gate refuses the slice")
def then_gate_refuses(gate_run) -> None:
    # Exit-code-exact: REFUSED <=> exit 2 (the `FeatureScopeMalformed` fail-closed
    # path). CLEARED means the gate certified the slice though its arch coverage
    # is unsound (the defect under test); UNEXPECTED means it failed via a WRONG
    # mode -- both are caught, so the assertion never passes for the wrong reason.
    assert gate_run.verdict is GateVerdict.REFUSED, (
        f"expected the gate to REFUSE the slice (exit 2), got verdict "
        f"{gate_run.verdict.value!r} (exit {gate_run.exit_code}) -- "
        + (
            "the gate CLEARED a slice whose architecture coverage is unsound: "
            "the feature-scoped gate silently narrowed its arch-tier claim "
            "instead of refusing LOUD (arch-scope non-vacuity floor not yet "
            "delivered)"
            if gate_run.verdict is GateVerdict.CLEARED
            else "the gate failed via the WRONG mode -- not the fail-closed "
            "FeatureScopeMalformed refusal"
        )
    )


@then("the gate clears the slice's feature scope")
def then_gate_clears(gate_run) -> None:
    assert gate_run.verdict is GateVerdict.CLEARED, (
        f"expected the gate to CLEAR a sound slice (exit 0), got verdict "
        f"{gate_run.verdict.value!r} (exit {gate_run.exit_code})"
    )


@then("the gate certifies a non-vacuous architecture-tier scope")
def then_arch_scope_non_vacuous(gate_run) -> None:
    # The CLEAR must carry the FeatureScopeCleared verdict event -- proving the
    # gate did not clear vacuously (the arch tier collected real node-ids
    # alongside the feature scope).
    assert gate_run.event == "FeatureScopeCleared", (
        "the gate cleared but did not surface a FeatureScopeCleared verdict "
        f"(saw event {gate_run.event!r}, exit {gate_run.exit_code})"
    )
