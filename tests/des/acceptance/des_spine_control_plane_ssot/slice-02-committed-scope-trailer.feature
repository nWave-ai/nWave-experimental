@feature-des-spine-control-plane-ssot @slice-02
# Feature: The contract gate stamps a PORTABLE commit-scope trailer on a git tree,
#          or degrades LOUD (no un-verifiable trailer) on a git-absent tree.
# Slice: 02 — committed-scope trailer (the un-verifiable-digest correctness slice,
#         Class C). Closes AD-23: the producer (`run_contract_gate._mode_run_suite`)
#         SILENTLY falls back to a WORKING-tree digest on git-absent (`:645`,
#         `digest = gate_scope_digest(repo)`) → a trailer no checkout can verify.
#         DISCUSS US-2, Slice Plan slice-02, DESIGN facet-4 (Option A), ADR-CP-001
#         (one committed-scope contract: producer == verifier) + ADR-CP-002
#         (the digest fix lands behind the already-real CommittedScopePort).
#
# THE OPERATOR VALUE (DISCUSS Slice Plan row slice-02 + US-2): "Operator gets a
# portable commit-scope trailer on a git tree, or a LOUD
# `committed-scope.indeterminate` (no un-verifiable trailer) on git-absent."
#
# Driving port (Mandate-13, invariant 1+2): the `des run-contract-gate` CLI — the
# canonical contract-gate driving surface wired at `des.cli.__main__:69` (kebab
# dispatcher), invoked exactly as the operator + the G_COMMIT exit-gate hook
# invoke it (`subagent_stop_handler._run_gate_subprocess`). Layer-3 subprocess:
# the SUT is the real CLI process; NEVER `from des.cli.run_contract_gate import
# gate_scope_digest` invoked at the test boundary, NEVER a
# `from des.adapters.driven.git.committed_scope_adapter import ...`.
#
# Integration surface (Mandate-13 invariant 4): every scenario crosses the REAL
# git-vs-git-absent seam — a real `.git/` work-tree (git as a test-harness
# dependency) for the portable path, and a plain directory with NO `.git/` for
# the degrade-LOUD path. The producer reads git through its own
# `CommittedScopePort` adapter (not a mock); the git-absent divergence is a
# genuine filesystem topology, not a stubbed predicate.
#
# Mechanical assertion (Mandate-13 invariant 5): Python-only, and GIT-FREE for the
# SUT path — the git-ABSENT topology is constructed by simply NOT creating a
# `.git/` directory (never by shelling out to `git` to "remove" version control).
# AT-02 is the target-machine-independence assertion: it proves the producer's
# git-ABSENT path degrades LOUD (`committed-scope.indeterminate`, NO trailer) —
# git is NOT a runtime dependency of the gate LOGIC; it sits behind the optional
# port and degrades LOUD when absent (the generality/agnosticism mandate).
# Cross-OS, language-agnostic.
#
# Observable sink (Mandate-13 invariant 3): the structured `ContractGateResult`
# (with or without a `gate_scope_digest`) + the `health.gate.committed-scope.
# indeterminate` marker on the gate's output stream, plus the process exit code.
# NOT internal call counts; NOT private digest-function returns.
#
# Universe (Mandate 8): {exit_code, outcome, stamped_digest, indeterminate_emitted}.
# Internal fields (Popen handle, env dict, raw stream bytes) NEVER appear.
#
# State machine the contract-gate producer enforces on the git seam (slice-02):
#   (tree is a git work-tree) -------> stamps the committed-scope digest of HEAD
#                                      → PORTABLE trailer, exit 0  (AT-01)
#   (tree is NOT a work-tree) -------> CANNOT pin a committed revision
#                                      → LOUD `committed-scope.indeterminate`,
#                                        NO trailer, suite still RUNS, exit 0  (AT-02)
#   (a stamped portable trailer) ----> verifier re-derives the SAME digest
#                                      → VERIFIED  (AT-03, the producer==verifier
#                                        round-trip proving portability)
#
# Degrade-LOUD contract (DISCUSS D1 / OSS ACL non-halting / ADR-CP-001): on
# git-absent the producer NEVER silently stamps a working-tree digest it cannot
# honor. It emits the LOUD marker and stamps NOTHING — the suite-run is a
# producer, not a fail-closed gate, so it still exits 0 (ADR-CP-001 Open: exit 0
# + LOUD marker). The fail-closed REFUSE (exit 2) belongs to the verify role,
# already shipped by the sibling `fix-gcommit-exit-gate-scoping`.
#
# Layer 3 (subprocess against tmp_path, @real-io — the driven set includes a real
# filesystem adapter + a real git work-tree): example-only (Mandate 9 v2). Sad
# path (git-absent) is one explicit named example (Mandate 11). No PBT machinery.
#
# Carpaccio ceiling = 3 (Class C, NOT a walking skeleton): 3 thin, independent
# ATs. NOT a @coupled group — each AT is independently meaningful and shippable
# (AT-01 git-tree portable trailer; AT-02 git-absent degrade-LOUD, the AD-23 RED;
# AT-03 the producer==verifier round-trip discriminator that AT-01 alone does not
# prove end-to-end).

Feature: The contract gate stamps a portable commit-scope trailer or degrades loud
  As an operator running the contract gate through the DES spine
  I want a stamped commit-scope trailer to be verifiable on any checkout
  So that I can trust a stamped verdict as a portable guarantee
  And on a tree with no revision control I am told loudly that no portable trailer exists
  Instead of trusting a trailer that no other checkout can ever verify

  # ─────────────────────────────────────────────────────────────────────────
  # AT-01 — PORTABLE TRAILER ON A GIT TREE (the positive, US-2 happy path).
  # On a real git work-tree the producer stamps the committed-scope digest of
  # HEAD — and that digest EQUALS the independent `--committed-scope-digest` of
  # the same commit (committed-scope, NOT working-tree). This is the portable,
  # verifiable trailer the operator trusts as a guarantee.
  # ─────────────────────────────────────────────────────────────────────────
  @driving_port @real-io @slice-02 @portable @contract-shape:bounded-change
  Scenario: The operator gets a portable commit-scope trailer on a git work-tree
    Given a contract tree that is a git work-tree
    When the operator runs the contract gate over that tree
    Then the contract gate stamps a portable commit-scope trailer and proceeds with exit code 0
    And the stamped trailer matches the committed scope of the tree

  # ─────────────────────────────────────────────────────────────────────────
  # AT-02 — DEGRADE LOUD ON A GIT-ABSENT TREE (the AD-23 RED, US-2 sad path).
  # On a tree with no `.git/` the producer cannot pin a committed revision, so it
  # emits the LOUD `committed-scope.indeterminate` marker and stamps NO trailer —
  # while the suite still RUNS (exit 0). This is the target-machine-independence
  # assertion: the gate degrades LOUD rather than silently stamp a working-tree
  # digest no checkout can verify (today it silently stamps one — the RED).
  # ─────────────────────────────────────────────────────────────────────────
  @driving_port @real-io @slice-02 @git-absent @degrade-loud @contract-shape:unbounded-preservation
  Scenario: The operator is told loudly that no portable trailer exists on a tree with no revision control
    Given a contract tree that is a tree that is not under revision control
    When the operator runs the contract gate over that tree
    Then the contract gate runs the suite and stamps no trailer and proceeds with exit code 0
    And the operator sees a LOUD `committed-scope.indeterminate` marker naming the missing revision control
    And no un-verifiable trailer is stamped

  # ─────────────────────────────────────────────────────────────────────────
  # AT-03 — THE PRODUCER==VERIFIER ROUND-TRIP (the portability discriminator).
  # A stamped trailer is only a GUARANTEE if the verifier independently
  # re-derives the SAME committed-scope digest (ADR-CP-001 producer==verifier).
  # Stamp the producer's portable trailer onto HEAD, then verify it: VERIFIED
  # proves the stamped digest IS the verifiable committed-scope digest, not a
  # present-but-unverifiable token. This is the irreducible end-to-end portability
  # proof AT-01 (stamp-time equality only) does not give on its own.
  # ─────────────────────────────────────────────────────────────────────────
  @driving_port @real-io @slice-02 @round-trip @contract-shape:bounded-change
  Scenario: A stamped portable trailer verifies against the same tree it was stamped on
    Given a contract tree that is a git work-tree
    When the stamped commit-scope trailer is verified against the tree it was stamped on
    Then the contract gate confirms the trailer verifies with exit code 0
