@feature-classic-spine-decommission
Feature: The atdd_pure spine runs on a feature installed for real
  As an nWave framework developer making atdd_pure the default DELIVER spine
  I want the AT-completion ledger to accept records from both the review-verdict
    writer and the completion-ledger writer without rejecting either
  So that an installed atdd_pure dispatch is not hard-blocked by a ledger that
    two writers disagree about (F-13)

  # slice-02 of classic-spine-decommission -- F-13 closure, the HARD
  # PREREQUISITE. `at_review_verdict` writes `ATReviewVerdict` records via the
  # M7 `AtCompletionLedger` API so every record carries `seq` + `record_hash`;
  # U1's M8 carpaccio-order read then has one schema to satisfy. F-13 fix
  # candidate (a) -- single-schema by construction.
  #
  # M4: the @wiring_e2e scenario exercises the REAL multi-writer interleave --
  # the real `at_review_verdict` CLI and the real `AtCompletionLedger` write the
  # SAME ledger file, then U1's order read consumes the mixed result. A
  # fixture-uniform-schema ledger proves NOTHING -- F-13 IS the interleave. The
  # reviewer vetoes a uniform-ledger test here.
  #
  # Layer 5 (WS @wiring_e2e): real stack, subprocess. Example-only (Mandate 11).
  #
  # Driving port: `at_review_verdict` CLI + `AtCompletionLedger` M7 API + the
  # carpaccio-order read; installed feature layout, subprocess-real.

  @slice-02 @wiring_e2e @driving_port @contract-shape:bounded-change
  Scenario: The carpaccio order read accepts a ledger written by two writers
    Given an installed feature "f13-target" with a shared ledger
    And the completion-ledger writer appends a gate event for slice "slice-01"
    And the review verdict writer appends a verdict record for slice "slice-01"
    And the completion-ledger writer appends a gate event for slice "slice-02"
    When the carpaccio order read consumes the shared ledger
    Then the carpaccio order read accepts the mixed-writer ledger
    And no ledger integrity violation is raised

  @slice-02 @wiring_e2e @driving_port @contract-shape:bounded-change
  Scenario: A verdict record interleaved between gate events does not break the read
    Given an installed feature "f13-target" with a shared ledger
    And the review verdict writer appends a verdict record for slice "slice-01"
    And the completion-ledger writer appends a gate event for slice "slice-01"
    And the review verdict writer appends a verdict record for slice "slice-02"
    When the carpaccio order read consumes the shared ledger
    Then the carpaccio order read accepts the mixed-writer ledger
    And no ledger integrity violation is raised

  @slice-02 @wiring_e2e @driving_port @contract-shape:bounded-change
  Scenario: An atdd_pure dispatch completes against the installed feature
    Given an installed feature "f13-target" with a shared ledger
    And the completion-ledger writer appends a gate event for slice "slice-01"
    And the review verdict writer appends a verdict record for slice "slice-01"
    When an atdd_pure dispatch runs against the installed feature
    Then the installed atdd_pure dispatch completes successfully
