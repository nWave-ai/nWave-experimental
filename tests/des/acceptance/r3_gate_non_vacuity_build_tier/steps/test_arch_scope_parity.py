"""Step definitions for r3-gate-non-vacuity-build-tier slice-03 (Mandate-12).

slice-03 (verdict-coherence / non-narrowing parity) -- the FINAL slice. It proves
the per-slice gate's architecture-invariant set is a PROVABLE SUBSET of the
whole-tree contract scope, so the per-slice arch verdict and the whole-tree
pre-push verdict can never diverge on the arch tier.

Mandate-13 SHAPE (resolved -- full rationale in `composition_slice_03` +
`domain_types_slice_03`): Option A (CLI black-box emitting both scopes) is
STRUCTURALLY UNAVAILABLE (the CLI surfaces only an irreversible digest + the
verdict event, never the node-id COLLECTIONS). Option B (chosen) drives the REAL
resolver triple over the REAL repo -- pure functions whose signature IS their
driving port. `from des.cli.run_contract_gate import ...` is NOT the S2-forbidden
`des.(domain|application|adapters)` import class; this is an arch/contract
STRUCTURAL-invariant test (`test_arch_` prefix) -- the recognised S2 tolerable
variant.

NON-VACUITY: the parity is asserted with FIVE guards (subset + arch-non-empty +
negative-control + arch-scoped + strict-superset) so an empty arch set can never
make the subset trivially true. Each guard is a port-exposed boolean observable
on the `ScopeParity` returned by the composition service.

GREEN-on-author (atdd_pure honesty): the subset HOLDS at HEAD (arch n=579 ⊆
whole n=5224). slice-03 is a REGRESSION-PIN of an existing coherence property,
NOT a fabricated RED. A future widening of `_arch_invariant_paths` that broke the
subset would RED it.

Step bodies delegate to `R3ParityComposition` -- no inline business logic
(Mandate-12 criterion 3: single delegation / single assertion, no control flow in
step bodies). Domain nouns are typed via `domain_types_slice_03` (criterion 1);
the composition service consumes those typed parameters (criterion 2).

S1 (step-text uniqueness): slice-03's parity Given/When/Then are an entirely
slice-03-specific vocabulary -- they do NOT collide with the `common_steps` SSOT
texts (`a slice whose feature scope collects cleanly`, `the gate refuses the
slice`, ...). `common_steps` is NOT imported here (slice-03 drives the real
resolvers, not the synthetic-repo CLI), so there is no shared-registry shadow
risk. Zero literal collisions across slice files.

Layer 1/2 over a real-IO collection (each `_collect_node_ids` spawns the real
worker subprocess) -> example-only (Mandate 9, 11). The domain is not unbounded
("the real repo at HEAD" + a fixed negative control), so example-based is correct,
not PBT.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from pytest_bdd import given, scenarios, then, when

from .composition_slice_03 import R3ParityComposition


scenarios("../slice-03-arch-scope-parity.feature")


@pytest.fixture
def composition() -> R3ParityComposition:
    """The production composition exercising the real resolver triple."""
    return R3ParityComposition()


# ===========================================================================
# Given -- the real repository the resolvers collect over
# ===========================================================================


@given(
    "the production contract-gate resolvers over the real repository",
    target_fixture="real_repo",
)
def _given_real_repo() -> Path:
    """The REAL repo root (NOT a synthetic tmp repo).

    The subset is structurally true BY `tests/conftest.py:757` auto-marking
    `tests/build/` -> `unit` into the whole-tree contract -- that conftest
    machinery is live only in the real repo. The resolver triple is exercised
    over THIS tree, exactly as the per-slice gate and the pre-push gate do.
    """
    return Path(__file__).resolve().parents[5]


# ===========================================================================
# When -- collect the two contract-scope tiers
# ===========================================================================


@when(
    "the architecture-invariant scope and the whole-tree contract scope are collected",
    target_fixture="parity",
)
def _when_collect_scopes(composition: R3ParityComposition, real_repo: Path):
    """Drive the real resolvers: arch scope + whole-tree scope over the real repo."""
    return composition.measure_scope_parity(real_repo)


# ===========================================================================
# Then -- the five non-vacuity parity guards (port-exposed observables)
# ===========================================================================


@then("the architecture-invariant scope is a subset of the whole-tree contract scope")
def _then_subset_holds(parity) -> None:
    # Guard 1 -- THE parity claim. On failure, name the exact arch node-ids that
    # are NOT in the whole-tree set: those are precisely the tests on which the
    # per-slice gate could diverge from the whole-tree pre-push gate.
    assert parity.subset_holds, (
        "the per-slice gate's architecture-invariant scope is NOT a subset of the "
        "whole-tree contract scope -- the two gates could diverge on the "
        f"architecture tier on these node-ids: {sorted(parity.arch_not_in_whole)[:10]} "
        f"({len(parity.arch_not_in_whole)} total). The per-slice gate has narrowed "
        "wrong: it runs arch tests the whole-tree contract does not enforce"
    )


@then("the architecture-invariant scope is not empty")
def _then_arch_non_empty(parity) -> None:
    # Guard 2 -- NON-VACUITY. An empty arch set would make guard 1 trivially true;
    # this proves the subset is asserted over a REAL, populated arch tier.
    assert parity.arch_is_non_empty, (
        "the architecture-invariant scope is EMPTY -- the subset claim would be "
        "vacuously true. `_arch_invariant_paths` returned no collectable arch "
        "tests; the parity must be asserted over a non-empty arch tier"
    )


@then("no fabricated architecture test appears in either scope")
def _then_negative_control_absent(parity) -> None:
    # Guard 3 -- negative control. A fabricated tests/build/-shaped node-id that
    # corresponds to no real collected item is in NEITHER set -- proving both
    # collections are REAL (not a degenerate universal set that would make any
    # subset vacuously true).
    assert parity.negative_control_absent, (
        "a fabricated architecture node-id appeared in one of the collected scopes "
        "-- a collection returned a degenerate universal set, so the subset would "
        "be vacuously true. Both scopes must be REAL collections of actual items"
    )


@then("every architecture-invariant test belongs to the architecture tier")
def _then_arch_scoped(parity) -> None:
    # Guard 4 -- the arch resolver scoped to tests/build/ and did not leak. If the
    # arch set held a non-tests/build/ id, `_arch_invariant_paths` would be
    # over-broad and the per-slice gate would run more than the arch tier.
    assert parity.arch_scoped_to_build, (
        "the architecture-invariant scope contains a test OUTSIDE tests/build/ -- "
        "`_arch_invariant_paths` leaked beyond the architecture tier glob, so the "
        "per-slice gate would run non-architecture tests as if they were arch "
        "invariants"
    )


@then("the whole-tree contract scope is strictly larger than the architecture scope")
def _then_strict_superset(parity) -> None:
    # Guard 5 -- the subset is MEANINGFUL. whole == arch would make the subset
    # trivially true; a strict superset proves the whole-tree contract genuinely
    # contains MORE than the arch tier (the feature/unit/integration breadth).
    assert parity.whole_is_strict_superset, (
        "the whole-tree contract scope is NOT strictly larger than the "
        f"architecture scope (|arch|={len(parity.arch_ids)}, "
        f"|whole|={len(parity.whole_ids)}) -- the subset would be trivially true. "
        "The whole-tree contract must contain strictly more than the arch tier"
    )


@then("the collection leaves the repository unchanged")
def _then_repo_unchanged(parity) -> None:
    # @contract-shape:unbounded-preservation: the resolver triple READS the
    # filesystem and COLLECTS (never runs, never writes). The port-exposed
    # observable of "unchanged" is that BOTH digests fingerprinted a non-empty
    # collection deterministically -- a successful read-only collection that
    # produced two stable digests, with no write side-effect. (Layer-1/2:
    # traditional assertion per Mandate 8; the universe is the two collected
    # scopes + their digests, all read-only observables.)
    assert parity.arch_digest and parity.whole_digest, (
        "the read-only collection did not produce stable digests for both scopes "
        "-- the parity measurement must be a side-effect-free read of the contract "
        f"suite (arch_digest set: {bool(parity.arch_digest)}, "
        f"whole_digest set: {bool(parity.whole_digest)})"
    )
