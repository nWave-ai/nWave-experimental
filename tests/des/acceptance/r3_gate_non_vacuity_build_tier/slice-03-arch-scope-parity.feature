@feature-r3-gate-non-vacuity-build-tier
Feature: The per-slice gate's architecture tier never diverges from the whole-tree contract

  As the U2 SubagentStop / G_COMMIT exit gate that certifies a carpaccio slice
    GREEN before it earns a SliceCommitVerified record
  I want the architecture-invariant set the per-slice gate runs to be a provable
    subset of the whole-tree contract scope the pre-push gate enforces
  So that the per-slice arch verdict and the whole-tree pre-push verdict can never
    disagree about an architecture test -- the per-slice gate is a non-narrowing
    projection of the contract, never wider than what it claims to enforce

  # slice-03 (verdict-coherence / non-narrowing parity) -- the FINAL slice. It
  # proves the structural guarantee that makes slice-01's "broken arch tier
  # REFUSES" and slice-02's "vacuous arch tier degrades LOUD" TRUSTWORTHY: the
  # per-slice gate's arch set is a SUBSET of the whole-tree contract. If the arch
  # set could contain a node-id the whole-tree set does NOT, the two gates could
  # DIVERGE on the arch tier. The subset invariant forecloses that.
  #
  # STRUCTURAL ANCHOR (verified-from-source, tests/conftest.py:757): the real
  # repo's root conftest auto-marks tests/build/ -> unit, so every tests/build/**
  # test the arch resolver returns ALSO falls into the whole-tree
  # `unit or integration or acceptance` collection. The subset is structurally
  # true BY the conftest auto-mark; slice-03 PINS it so a future widening of
  # `_arch_invariant_paths` to a directory NOT auto-marked into the contract
  # (which would break the subset) would RED this slice.
  #
  # NON-VACUITY (the directive's hard requirement -- an empty arch set is
  # trivially a subset). The parity is asserted with FIVE guards, not just
  # `arch ⊆ whole`:
  #   1. subset           -- arch ⊆ whole (the parity claim);
  #   2. arch non-empty   -- |arch| > 0 (NOT vacuously true on an empty set);
  #   3. negative control -- a fabricated tests/build/-shaped node-id is in
  #                          NEITHER set (the sets are REAL collections, not a
  #                          degenerate "everything");
  #   4. arch scoped      -- every arch id is genuinely under tests/build/ (the
  #                          resolver scoped to the arch glob, did not leak);
  #   5. strict superset  -- whole ⊋ arch (the subset is MEANINGFUL -- whole is
  #                          strictly larger, not arch == whole).
  #
  # Mandate-13 SHAPE DECISION: Option A (a pure black-box subprocess emitting
  # BOTH scopes) is STRUCTURALLY UNAVAILABLE -- the run-contract-gate CLI surfaces
  # only an IRREVERSIBLE SHA-256 digest (--print-digest) and the verdict event
  # (--feature-id); no driving port exposes the two node-id COLLECTIONS as
  # parseable output, so a CLI black-box cannot observe the two SETS to assert
  # subset. Option B (chosen) exercises the REAL production resolvers
  # (_arch_invariant_paths + _collect_node_ids + compute_gate_scope_digest) over
  # the REAL repo. The SUT is the resolver TRIPLE -- pure functions whose public
  # signature IS their driving port (port-to-port at the CLI-helper scope). The
  # parity is a STRUCTURAL coherence invariant, not feature behaviour:
  # `from des.cli.run_contract_gate import ...` is NOT the S2-forbidden
  # `des.(domain|application|adapters)` import class; the binding is an
  # arch/contract test (test_arch_ prefix) -- the recognised S2 tolerable variant.
  #
  # The collection runs against the REAL repo (NOT a synthetic tmp repo): the
  # subset is structurally true BY the conftest auto-mark, which is live only in
  # the real repo. A synthetic tmp repo lacks that conftest, so its whole-tree run
  # drops tests/build/ and would manufacture a FALSE non-subset (verified
  # empirically during DISTILL authoring).
  #
  # GREEN-on-author honesty (atdd_pure): the subset invariant HOLDS at HEAD
  # (arch n=579 ⊆ whole n=5224, difference 0, arch non-empty). slice-03 is a
  # REGRESSION-PIN of an existing coherence property -- NOT a fabricated RED. A
  # future widening of `_arch_invariant_paths` that broke the subset would RED it.
  # The failures (if any future regression) are subset AssertionErrors, not
  # collection crashes / import errors. Not xfail-marked.
  #
  # Layer 1/2 over a real-IO collection (each _collect_node_ids spawns the real
  # worker subprocess) -> example-only (Mandate 9, 11). The domain is not unbounded
  # (it is "the real repo at HEAD" + a fixed negative control), so example-based is
  # the correct paradigm, not PBT.

  @slice-03 @driving_port @real-io @property @contract-shape:unbounded-preservation
  Scenario: The per-slice gate's architecture tier is a subset of the whole-tree contract
    Given the production contract-gate resolvers over the real repository
    When the architecture-invariant scope and the whole-tree contract scope are collected
    Then the architecture-invariant scope is a subset of the whole-tree contract scope
     And the architecture-invariant scope is not empty
     And no fabricated architecture test appears in either scope
     And every architecture-invariant test belongs to the architecture tier
     And the whole-tree contract scope is strictly larger than the architecture scope
     And the collection leaves the repository unchanged
