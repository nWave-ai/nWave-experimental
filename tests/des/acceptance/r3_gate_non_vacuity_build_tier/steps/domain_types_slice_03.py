"""Domain types for r3-gate-non-vacuity-build-tier slice-03 (Mandate-12 criterion 1).

slice-03 (verdict-coherence / non-narrowing parity) -- the FINAL slice. Where
slice-01 pinned that a broken arch tier REFUSES through the driving port and
slice-02 pinned that a present-but-vacuous arch tier degrades LOUD, slice-03
proves the structural guarantee that makes those two verdicts TRUSTWORTHY: the
architecture-invariant set the per-slice gate runs is a PROVABLE SUBSET of the
whole-tree contract scope the pre-push gate enforces.

WHY this matters (verdict-coherence): the per-slice `--feature-id` gate
collect-AND-RUNs `_arch_invariant_paths(repo)` (`tests/build/**`); the whole-tree
pre-push gate collects the `unit or integration or acceptance` contract over the
entire tree. If the per-slice arch set could contain a node-id the whole-tree set
does NOT, the two gates could DIVERGE on the arch tier -- the per-slice gate
might bless (or block) something the whole-tree gate disagrees with. The subset
invariant forecloses that divergence: arch-node-ids ⊆ whole-tree-node-ids means
the per-slice gate is a NON-NARROWING PROJECTION of the contract on the arch tier
-- never wider, so the two verdicts can never disagree about an arch test.

STRUCTURAL ANCHOR (verified-from-source, `tests/conftest.py:757`): the real
repo's root conftest auto-marks `tests/build/` -> `unit`. So every
`tests/build/**` test the arch resolver returns carries a contract marker and is
therefore ALSO in the whole-tree `unit or integration or acceptance` collection.
The subset is structurally true BY the conftest auto-mark -- slice-03 PINS that
structural truth so a future change to `_arch_invariant_paths` (e.g. widening the
glob to a directory that is NOT auto-marked into the contract) that broke the
subset would RED this slice.

SUT (Mandate-13 reconciliation): the SUT is the production resolver TRIPLE
`_arch_invariant_paths` + `_collect_node_ids` + `compute_gate_scope_digest` from
`des.cli.run_contract_gate`. These are PURE FUNCTIONS whose public signature IS
their driving port (per `nw-tdd-methodology`: "Pure domain functions ARE their
own driving ports -- calling them directly IS port-to-port testing"). The parity
is a COHERENCE INVARIANT over two collection functions, NOT a feature behaviour
reachable through a CLI. The `run_contract_gate` CLI exposes only an irreversible
SHA-256 digest (`--print-digest`) and the verdict event (`--feature-id`) -- NO
driving port surfaces the two node-id COLLECTIONS as parseable output, so a pure
black-box subprocess (Option A) cannot observe the two SETS to assert subset.
Option B (exercise the real resolvers over the real repo) is the only honest
shape. `des.cli.*` is NOT in the S2-forbidden `des.(domain|application|adapters)`
import class; the binding is an arch/contract test (`test_arch_` prefix) asserting
a STRUCTURAL invariant -- the recognised S2 tolerable variant.

Mandate-12 SSOT: the shared domain vocabulary (`FeatureId`, `GateVerdict`,
event-name constants) is RE-EXPORTED from `domain_types_slice_01` -- expressed
ONCE. Only the slice-03-specific noun (`ScopeTier` + the parity-axis constants)
is declared here.
"""

from __future__ import annotations

from enum import Enum

# Re-export the shared domain vocabulary (Mandate-12: expressed once in slice-01).
from .domain_types_slice_01 import (  # noqa: F401  (re-exported SSOT vocabulary)
    ARCH_PROBE_FEATURE_ID,
    FEATURE_SCOPE_CLEARED_EVENT,
    FEATURE_SCOPE_MALFORMED_EVENT,
    FeatureId,
    GateVerdict,
)


class ScopeTier(str, Enum):
    """The two contract-scope tiers slice-03's parity property relates.

    The subset invariant is `ARCH ⊆ WHOLE_TREE`: the per-slice gate's arch tier
    is a non-narrowing projection of the whole-tree contract.

    * ARCH -- the architecture-invariant node-id set the per-slice `--feature-id`
      gate collect-AND-RUNs: `_collect_node_ids(repo, paths=_arch_invariant_paths(repo))`.
      The `tests/build/**` glob (OQ-1-ratified for slice-01), each auto-marked
      `unit` by `tests/conftest.py:757`.
    * WHOLE_TREE -- the whole-tree contract node-id set the pre-push gate enforces:
      `_collect_node_ids(repo)` (no path filter, the `unit or integration or
      acceptance` marker over the entire tree). This is the SAME collection
      `compute_gate_scope_digest` fingerprints.
    """

    ARCH = "arch"  # the per-slice gate's tests/build/** arch-invariant set
    WHOLE_TREE = (
        "whole_tree"  # the whole-tree contract scope the pre-push gate enforces
    )


# A repo-relative canonical node-id that is GUARANTEED to be in NEITHER scope tier
# -- the negative control proving the two collected sets are REAL collections
# (not a degenerate "everything" that would make any subset vacuously true). A
# fabricated `tests/build/`-shaped path that corresponds to no collected item
# falls out of the arch set (the resolver collects only real items) AND the
# whole-tree set (likewise). If a regression made either collection return a
# universal set, this control would (correctly) appear and RED the parity.
NONEXISTENT_ARCH_NODE_ID = (
    "tests/build/__nonexistent_parity_perturbation__.py::test_ghost_invariant"
)
