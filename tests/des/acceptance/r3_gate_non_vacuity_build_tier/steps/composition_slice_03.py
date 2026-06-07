"""Composition root for r3-gate-non-vacuity-build-tier slice-03 (Mandate-12 SSOT).

slice-03 (verdict-coherence / non-narrowing parity) -- the FINAL slice. It proves
the architecture-invariant set the per-slice gate runs is a PROVABLE SUBSET of
the whole-tree contract scope, so the per-slice arch verdict and the whole-tree
pre-push verdict can never diverge on the arch tier.

Mandate-13 SHAPE DECISION (resolved -- see `domain_types_slice_03` for the full
rationale):

  * Option A (a pure black-box subprocess emitting BOTH scopes) is STRUCTURALLY
    UNAVAILABLE: the `run_contract_gate` CLI surfaces only an IRREVERSIBLE
    SHA-256 digest (`--print-digest`) and the verdict event (`--feature-id`).
    No driving port exposes the two node-id COLLECTIONS as parseable output, so
    a CLI black-box cannot observe the two SETS to assert subset.
  * Option B (chosen) exercises the REAL production resolvers over the REAL repo.
    The SUT is the resolver TRIPLE `_arch_invariant_paths` + `_collect_node_ids`
    + `compute_gate_scope_digest` -- PURE FUNCTIONS whose public signature IS
    their driving port (port-to-port at the domain/CLI-helper scope). The parity
    is a COHERENCE INVARIANT over two collection functions, not a feature
    behaviour. `from des.cli.run_contract_gate import ...` is NOT in the
    S2-forbidden `des.(domain|application|adapters)` import class; this is an
    arch/contract STRUCTURAL-invariant test (the recognised S2 tolerable
    variant), bound under a `test_arch_` prefix.

NON-VACUITY (the directive's hard requirement -- an empty arch set is trivially a
subset). The observable `ScopeParity` carries FIVE guards, not just `arch ⊆
whole`:

  1. subset            -- arch_ids ⊆ whole_ids (the parity claim);
  2. arch non-empty    -- |arch_ids| > 0 (NOT vacuously true on an empty set);
  3. negative control  -- a fabricated `tests/build/`-shaped node-id is in NEITHER
                          set (the sets are REAL collections, not "everything");
  4. arch scoped       -- every arch id is genuinely under `tests/build/` (the
                          resolver scoped to the arch glob, did not leak);
  5. strict superset   -- whole_ids ⊋ arch_ids (the subset is MEANINGFUL --
                          whole is strictly larger, not arch == whole).

The collection runs against the REAL repo (NOT a synthetic tmp repo): the subset
is structurally true BY `tests/conftest.py:757` auto-marking `tests/build/` ->
`unit` into the whole-tree contract; that conftest machinery is live only in the
real repo. (A synthetic tmp repo lacks that conftest, so its whole-tree run drops
`tests/build/` -- which would manufacture a FALSE non-subset; verified
empirically during DISTILL authoring.)

GREEN-on-author honesty: the subset invariant HOLDS at HEAD (arch n=579 ⊆ whole
n=5224, difference 0, arch non-empty). slice-03 is therefore a REGRESSION-PIN of
an existing coherence property -- it is NOT a fabricated RED. A future change to
`_arch_invariant_paths` that widened the arch glob to a directory NOT auto-marked
into the contract would break the subset and RED this slice. (Reported honestly
per atdd_pure: see the DISTILL hand-off message.)

Genericità (STANDING mandate): Python + filesystem only. The single pytest spawn
is the EXISTING `_collect_scope` worker (`python_for("pytest")`); slice-03 adds NO
new spawn site and NO production code -- it only READS the resolvers. No git, no
external tool.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

# Mandate-13 reconciliation: `des.cli.*` is NOT the S2-forbidden
# `des.(domain|application|adapters)` import class. These three are PURE-FUNCTION
# resolvers whose signature IS their driving port; the parity is a structural
# coherence invariant (arch/contract test), not feature behaviour through a CLI.
from des.cli.run_contract_gate import (
    _arch_invariant_paths,
    _collect_node_ids,
    compute_gate_scope_digest,
)

from .domain_types_slice_03 import NONEXISTENT_ARCH_NODE_ID


@dataclass(frozen=True)
class ScopeParity:
    """The observable parity between the arch set and the whole-tree contract set.

    Port-exposed observables only (Mandate 8 universe shape): the two node-id
    SETS the production resolvers return + the SHA-256 digests they fingerprint.
    No internal struct fields -- these are exactly the collections the per-slice
    gate and the pre-push gate fingerprint.
    """

    arch_ids: frozenset[str]
    whole_ids: frozenset[str]
    arch_digest: str
    whole_digest: str

    # --- the five non-vacuity guards (each a port-exposed boolean observable) --

    @property
    def subset_holds(self) -> bool:
        """Guard 1 -- the parity claim: arch_ids ⊆ whole_ids."""
        return self.arch_ids <= self.whole_ids

    @property
    def arch_is_non_empty(self) -> bool:
        """Guard 2 -- NON-VACUITY: |arch_ids| > 0 (not a trivial empty-set subset)."""
        return len(self.arch_ids) > 0

    @property
    def negative_control_absent(self) -> bool:
        """Guard 3 -- a fabricated arch node-id is in NEITHER set (sets are real)."""
        return (
            NONEXISTENT_ARCH_NODE_ID not in self.arch_ids
            and NONEXISTENT_ARCH_NODE_ID not in self.whole_ids
        )

    @property
    def arch_scoped_to_build(self) -> bool:
        """Guard 4 -- every arch id is genuinely under `tests/build/` (no leak)."""
        return all(node_id.startswith("tests/build/") for node_id in self.arch_ids)

    @property
    def whole_is_strict_superset(self) -> bool:
        """Guard 5 -- the subset is MEANINGFUL: whole strictly larger than arch."""
        return self.arch_ids < self.whole_ids

    @property
    def arch_not_in_whole(self) -> frozenset[str]:
        """The arch ids that are NOT in the whole-tree set (empty when subset holds).

        The precise diagnostic the parity assertion reports on failure -- the
        exact node-ids that would let the per-slice gate diverge from the
        whole-tree gate.
        """
        return self.arch_ids - self.whole_ids


@dataclass
class R3ParityComposition:
    """Production composition exercising the real resolver triple over the real repo.

    The SUT is `_arch_invariant_paths` + `_collect_node_ids` +
    `compute_gate_scope_digest` -- the exact production functions the per-slice
    gate (`_mode_feature_scoped` -> the arch join) and the pre-push gate
    (`gate_scope_digest`) call. Driving them directly IS port-to-port testing
    (pure-function public signature = driving port).
    """

    last_parity: ScopeParity | None = field(default=None)

    def measure_scope_parity(self, repo: Path) -> ScopeParity:
        """Collect the arch set + the whole-tree set over ``repo`` and fingerprint.

        Reuses the EXISTING production seams verbatim:
          * `_arch_invariant_paths(repo)` -- the `tests/build/**` arch resolver;
          * `_collect_node_ids(repo, paths=...)` -- the single collection seam
            (DDD-12), narrowed to the arch paths for the arch tier, unfiltered for
            the whole tree;
          * `compute_gate_scope_digest(...)` -- the SHA-256 the gate fingerprints.

        Mandate-12 criterion 3: this method is the composition-root service; the
        step bodies delegate to it and assert on the returned observable -- no
        business logic in step bodies.
        """
        arch_paths = _arch_invariant_paths(repo)
        arch_ids = frozenset(_collect_node_ids(repo, paths=arch_paths))
        whole_ids = frozenset(_collect_node_ids(repo))
        self.last_parity = ScopeParity(
            arch_ids=arch_ids,
            whole_ids=whole_ids,
            arch_digest=compute_gate_scope_digest(list(arch_ids)),
            whole_digest=compute_gate_scope_digest(list(whole_ids)),
        )
        return self.last_parity
