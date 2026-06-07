@feature-fix-atdd-pure-spine-phase-count-reduction
Feature: An operator can read the atdd_pure spine's delivery phase model

  The atdd_pure per-slice DELIVER carpaccio was designed to collapse from seven
  phases to three canonical phases — A_GREEN, C_REVIEWER_AUDIT,
  D_REFACTOR_COMMIT (ADR-001). The runtime still carries the old seven-phase
  vocabulary, and there is no operator-observable projection of the phase model
  at all — so an operator cannot see how many phases the spine runs, nor which
  transitions are legal. This slice ships that projection AND the reduction:
  an operator asks the spine to report its delivery phases and reads back
  exactly the three canonical phases with their three-link transition map.

  The phase model is observed through a real operator diagnostic — the spine's
  phase-report command — never by reading the phase model's internals directly
  (Mandate-13). The report is derived from the live phase model, not a
  hand-restated copy, so it cannot drift from what the spine actually runs.

  @slice-01 @walking-skeleton @driving_port @real-io @contract-shape:pure-function
  Scenario: The operator reads exactly three canonical delivery phases
    Given the operator asks the spine to report its delivery phases
    Then the spine reports exactly three delivery phases
    And the reported phases are exactly the canonical set "A_GREEN, C_REVIEWER_AUDIT, D_REFACTOR_COMMIT"
    And none of the retired phases "B_COVERAGE_CLEANUP, D_GAP_ROUTING, E_BATCH_REFACTOR, F_FINAL_REVIEW, G_COMMIT" appears in the report

  @slice-01 @driving_port @real-io @contract-shape:pure-function
  Scenario: The operator reads the three-link delivery transition map
    Given the operator asks the spine to report its delivery phases
    Then the spine reports the legal transition from "A_GREEN" to "C_REVIEWER_AUDIT"
    And the spine reports the legal transition from "C_REVIEWER_AUDIT" to "D_REFACTOR_COMMIT"
    And the spine reports the legal transition from "D_REFACTOR_COMMIT" to "TERMINAL"
    And the spine reports no transition out of the retired phase "D_GAP_ROUTING"
