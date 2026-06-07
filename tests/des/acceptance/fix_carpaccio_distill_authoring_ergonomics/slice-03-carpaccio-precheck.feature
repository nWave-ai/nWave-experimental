@feature-fix-carpaccio-distill-authoring-ergonomics
Feature: A DISTILL author can pre-check a feature's format before recording the verdict

  Today the gate's format requirements are invisible to a DISTILL author until
  the gate refuses the slice mid-spine, after authoring, reviewer-pairing, and
  verdict-recording. This feature gives the author a read-only pre-check they run
  BEFORE recording the verdict. It reports every format violation the gate would
  later raise -- in one pass, not one-at-a-time -- so the author fixes them all in
  a single round trip. The pre-check only reads and reports; it never records a
  verdict and never touches the review ledger.

  # ADR-001: the pre-check reuses the SAME shared format checks as the gate.
  # Principle 12: read/write driving-port split -- the pre-check has no record path.
  # Driving port: the real `python -m des.cli.carpaccio_precheck` CLI invoked
  # module-direct as a subprocess (Layer 3 / wiring_e2e). A non-gate designer
  # tool is invoked module-direct, NOT via the `des` dispatcher (its registry is
  # parity-pinned to the gate catalog -- F-DES-AT-REVIEW-VERDICT-SUBCOMMAND-
  # SURFACE). Example-only, no PBT (Mandate 9/11).

  Background:
    Given a repository for an atdd_pure feature

  @driving-port @real-io @slice-03 @contract-shape:unbounded-preservation
  Scenario: The pre-check tells the author when no feature file is bound to the feature
    Given the feature's scenario files carry no feature-binding tag
    When the operator runs the carpaccio pre-check for the feature
    Then the pre-check reports that no scenario file is bound to the feature
    And the pre-check names the expected feature-binding tag
    And the pre-check warns about the hyphen-versus-underscore legacy directory
    And the pre-check reports violations without recording any verdict

  @driving-port @real-io @slice-03 @contract-shape:unbounded-preservation
  Scenario: The pre-check distinguishes an over-ceiling slice that has the coupled escape from one that lacks it
    Given the feature carries an over-ceiling slice without the coupled escape
    And the feature also carries an over-ceiling slice with the coupled escape satisfied
    When the operator runs the carpaccio pre-check for the feature
    Then the pre-check reports the slice over the ceiling as lacking the coupled escape
    And the pre-check reports the other over-ceiling slice as having the coupled escape satisfied
    And the pre-check reports violations without recording any verdict

  @driving-port @real-io @slice-03 @contract-shape:unbounded-preservation
  Scenario: The pre-check reports every format defect in one pass instead of stopping at the first
    Given the feature carries a missing feature-binding tag, a slice-tag mismatch, and an over-ceiling slice
    When the operator runs the carpaccio pre-check for the feature
    Then the pre-check reports the missing feature-binding tag
    And the pre-check reports the slice-tag mismatch
    And the pre-check reports the over-ceiling slice
    And the pre-check reports an advisory verdict that violations were found
    And the pre-check reports violations without recording any verdict
