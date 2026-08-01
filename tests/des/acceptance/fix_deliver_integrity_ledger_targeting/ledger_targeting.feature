@feature-fix-deliver-integrity-ledger-targeting @atdd_pure @verify_integrity @ledger_targeting @real-io
Feature: deliver-integrity reconciliation is scoped to the feature's own slices

  Only the feature's own slices may participate in reconciliation. A second
  feature whose commits also carry Slice-Id trailers in the shared git history
  must not leak into this feature's reconciliation. The bug under repair
  reconciled the repo-global set of Slice-Id trailers against a feature-scoped
  verified set, so another feature's slices were reported as this feature's
  unreconciled slices (cross-feature false positive).

  The fix starts from the loud-safe `shipped - verified` and SUBTRACTS only
  slices POSITIVELY owned by OTHER features' ledgers (foreign_owned). Two
  properties must hold together: a co-resident feature's slice is excluded
  (AT-1, it is foreign-owned), AND an own-feature slice with no ledger record is
  still caught (AT-2 — no other feature owns it, so it survives; the loud-safe
  done-gate the prior fix regressed by intersecting against own-ledger membership).

  # AT-1 — cross-feature slice IGNORED. The own unshipped slice "slice-03"
  # (reviewed but not verified) is correctly reported; the co-resident feature's
  # slice "<foreign_slice>" is NOT. RED at HEAD: the whole-history scan reports
  # the foreign slice as this feature's unreconciled work.
  @slice-01 @contract-shape:bounded-change
  Scenario Outline: A co-resident feature's slice is excluded from this feature's reconciliation
    Given a shared git history carrying this feature's slices "slice-01, slice-02, slice-03"
    And the same history also carries another feature's slice "<foreign_slice>"
    And this feature's ledger reviewed slices "slice-01, slice-02, slice-03"
    And this feature's ledger verified slices "slice-01, slice-02"
    When the operator verifies deliver integrity for this feature
    Then the verifier reports the feature has unreconciled work
    And the only unreconciled slice reported is "slice-03"
    And the reconciliation excludes the foreign slice "<foreign_slice>"

    Examples: foreign slices from a co-resident feature
      | foreign_slice |
      | slice-14      |
      | slice-09      |
      | slice-99      |

  # AT-2 — own-feature no-record slice STILL reported (regression-pin).
  # A slice committed for THIS feature with a Slice-Id trailer but NO ledger
  # record for that slice (skipped exit gate: not reviewed, not verified) must
  # still be flagged unreconciled. The feature ledger exists (a complete
  # feature-end cycle was recorded) so the reconciliation sweep runs, but the
  # committed slice itself has no record. Single-feature repo, no foreign
  # slices: foreign_owned is empty, so the formula degenerates to the loud-safe
  # (shipped - verified) and the done-gate is preserved.
  # GREEN-pin at HEAD: the loud-safe `shipped - verified` already catches it.
  # The fix MUST keep it GREEN (this is the safety property ebb1f4cca regressed).
  @slice-01 @regression_pin @contract-shape:bounded-change
  Scenario: An own-feature slice shipped with no ledger record is reported unreconciled
    Given a shared git history carrying this feature's slices "slice-01"
    And this feature's ledger recorded a complete feature-end cycle
    When the operator verifies deliver integrity for this feature
    Then the verifier reports the feature has unreconciled work
    And the only unreconciled slice reported is "slice-01"

  # AT-3 (F-PUSH-GATE-SLICE-ATTRIBUTION, the real swarm defect): a co-resident
  # feature's slice lands in the shared git history but that feature's ledger
  # does NOT exist on disk in THIS worktree (per-worktree telemetry, gitignored
  # -- unlike AT-1 above, which seeds a visible foreign ledger). Before the fix,
  # `foreign_owned` cannot subtract a ledger it cannot see, so the pollutant
  # survived as this feature's "unreconciled" debt. The fix keys ownership on
  # this feature's OWN declared Slice-Plan (data that travels with THIS
  # feature's tree, not on which ledgers happen to be on disk): a shipped slice
  # this feature never declared is the distinct could-not-attribute state, named
  # but non-blocking, never silently dropped and never silently blamed.
  @slice-01 @contract-shape:bounded-change
  Scenario: A co-resident feature's slice with no visible ledger is not misattributed
    Given a shared git history carrying this feature's slices "slice-01"
    And the same history also carries another feature's slice "slice-07" with no visible ledger
    And this feature declares a Slice-Plan naming "slice-01"
    And this feature's ledger verified slices "slice-01"
    And this feature's ledger recorded a complete feature-end cycle
    When the operator verifies deliver integrity for this feature
    Then the verifier reports the feature is reconciled
    And the verifier names "slice-07" as unattributable, not blocking

  # AT-4 (regression-pin, plan-aware): the Slice-Plan filter narrows attribution
  # -- it must NEVER weaken genuine own-feature detection. A slice THIS
  # feature's own plan declares, shipped with no ledger record, still fails.
  @slice-01 @regression_pin @contract-shape:bounded-change
  Scenario: An own-feature declared slice shipped with no ledger record still fails with a Slice-Plan present
    Given a shared git history carrying this feature's slices "slice-01"
    And this feature declares a Slice-Plan naming "slice-01"
    And this feature's ledger recorded a complete feature-end cycle
    When the operator verifies deliver integrity for this feature
    Then the verifier reports the feature has unreconciled work
    And the only unreconciled slice reported is "slice-01"
