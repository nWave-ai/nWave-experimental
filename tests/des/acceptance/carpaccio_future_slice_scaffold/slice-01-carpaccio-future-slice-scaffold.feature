@feature-fix-carpaccio-future-slice-scaffold-blocks-commit
Feature: The E2 contract gate scopes its collection to shipped+entering slices

  A non-final carpaccio slice must commit even with a future slice's active-RED
  scaffold already authored on disk. The E2 feature-scoped contract gate
  (run_contract_gate --entering-slice) scopes its `.feature` scenario collection
  to the shipped+entering slice set, excluding not-yet-entered future scaffolds.
  The scope lives in the gate, never in the AT files -- no @skip pollution.

  @slice-01 @driving_port @real-io @contract-shape:bounded-change
  Scenario: A non-final slice's gate scope omits the future slice's scaffold
    Given a feature with slice-01 entering and a slice-02 active-RED scaffold on disk
    When the E2 contract gate runs for entering slice "slice-01"
    Then the contract gate passes
    And the gate collects only the 1 shipped+entering slice node, not the future scaffold

  @slice-01 @driving_port @real-io @contract-shape:bounded-change
  Scenario: The future slice's scenario is excluded from the collected scope
    Given a feature with slice-01 entering and a slice-02 active-RED scaffold on disk
    When the E2 contract gate runs for entering slice "slice-01"
    Then the collected scope excludes the future slice "slice-02"
    And the collected scope includes the entering slice "slice-01"

  @slice-01 @driving_port @real-io @contract-shape:unbounded-preservation
  Scenario: The final single slice still collects every shipped slice
    Given a feature whose single shipped slice "slice-01" is the final entering slice
    When the E2 contract gate runs for entering slice "slice-01"
    Then the gate collects only the 1 shipped+entering slice node, not the future scaffold
    And the contract gate passes

  @slice-01 @real-io @contract-shape:unbounded-preservation
  Scenario: The fix adds no skip marker to any future slice feature file
    Given a feature with slice-01 entering and a slice-02 active-RED scaffold on disk
    When the E2 contract gate runs for entering slice "slice-01"
    Then no skip marker is added to the future slice feature file
