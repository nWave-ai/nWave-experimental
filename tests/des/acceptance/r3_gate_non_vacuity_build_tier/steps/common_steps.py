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

Mandate-13: the per-slice driving port (`run_feature_scoped_gate`) is a Layer-3
subprocess black-box; these steps observe ONLY the CLI's exit code + stdout JSON
events. Mandate-12 criterion 3: step bodies are <=2 statements / assertion-only,
no business logic, no control flow beyond the assertion message expression.

RE-ALLOCATION (fix-e2-whole-tree-scope-blocks-unrelated-slices, 2026-07-30):
this module now carries TWO verdict vocabularies, because the protection this
feature encodes now lives on two surfaces. `gate_run`-shaped Thens observe the
PER-SLICE gate (which must judge a slice on its own scope and DEFER the
whole-tree tier LOUD); `whole_tree_run`-shaped Thens observe the FEATURE-END
whole-tree architecture run (where the keystone refusal relocated). No
protection was deleted -- each one is asserted at whichever surface now owns it.
"""

from __future__ import annotations

from pytest_bdd import given as bdd_given
from pytest_bdd import then, when

from .composition_slice_01 import R3GateComposition
from .domain_types_slice_01 import (
    BUILD_TIER_VERIFIED_EVENT,
    DEFERRED_TO_FEATURE_END,
    GateVerdict,
    WholeTreeVerdict,
)


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


@when(
    "the whole-tree architecture run certifies the repository",
    target_fixture="whole_tree_run",
)
def when_whole_tree_arch_run(composition: R3GateComposition, repo):
    """Drive the real whole-tree architecture run (the relocated protection)."""
    return composition.run_whole_tree_arch_gate(repo)


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


@then("the gate defers the whole-tree architecture tier to feature-end")
def then_gate_defers_whole_tree(gate_run) -> None:
    # RE-ALLOCATION (fix-e2-whole-tree-scope-blocks-unrelated-slices): the
    # per-slice gate no longer RUNS the whole-tree architecture tier, so it
    # must SAY SO. A narrowing that announces nothing is indistinguishable
    # from a coverage drop (GDP-6, no silent-wrong), and the record must NAME
    # where the coverage moved to or the reader cannot follow it.
    deferral = gate_run.whole_tree_deferral
    assert deferral is not None, (
        "the per-slice gate must LOUDLY emit BuildTierWholeTreeDeferred -- "
        "proof the whole-tree architecture tier was DEFERRED rather than "
        "silently narrowed away (a silent narrowing is indistinguishable from "
        f"a dropped protection). Saw events "
        f"{[e.get('event') for e in gate_run.emitted_events]!r}"
    )
    assert deferral.get("deferred_to") == DEFERRED_TO_FEATURE_END, (
        "the deferral record must NAME feature-end as where the whole-tree run "
        f"moves to, so the relocated coverage stays traceable -- got {deferral}"
    )


@then("the whole-tree architecture run refuses the repository")
def then_whole_tree_refuses(whole_tree_run) -> None:
    # Exit-code-exact: REFUSED <=> exit 1 (the BuildTierRefused fail-closed
    # path). CLEARED would mean the relocated protection evaporated in the
    # move; UNEXPECTED means it failed via a WRONG mode -- both are caught, so
    # the assertion never passes for the wrong reason.
    assert whole_tree_run.verdict is WholeTreeVerdict.REFUSED, (
        f"expected the whole-tree architecture run to REFUSE (exit 1), got "
        f"verdict {whole_tree_run.verdict.value!r} (exit "
        f"{whole_tree_run.exit_code}) -- this run is where the keystone "
        "protection RELOCATED to when the per-slice gate stopped sweeping the "
        "whole tree; if it clears here, the protection was dropped, not moved"
    )


@then("the whole-tree architecture run clears the repository")
def then_whole_tree_clears(whole_tree_run) -> None:
    assert whole_tree_run.verdict is WholeTreeVerdict.CLEARED, (
        f"expected the whole-tree architecture run to CLEAR a sound repository "
        f"(exit 0), got verdict {whole_tree_run.verdict.value!r} (exit "
        f"{whole_tree_run.exit_code})"
    )


@then("the whole-tree architecture run certifies a non-vacuous architecture-tier scope")
def then_whole_tree_arch_scope_non_vacuous(whole_tree_run) -> None:
    # RELOCATED from the per-slice gate. The CLEAR must carry a
    # BuildTierVerified naming a NON-ZERO executed count -- a run that
    # executed nothing has certified nothing, however green its exit code
    # (`check:unfired-is-not-evidence`).
    assert whole_tree_run.event == BUILD_TIER_VERIFIED_EVENT, (
        "the whole-tree run cleared but did not surface a BuildTierVerified "
        f"verdict (saw event {whole_tree_run.event!r}, exit "
        f"{whole_tree_run.exit_code})"
    )
    assert whole_tree_run.collected > 0, (
        "the whole-tree run must certify a NON-VACUOUS architecture scope -- a "
        "run reporting zero executed invariants certified nothing; got "
        f"collected={whole_tree_run.collected}"
    )
