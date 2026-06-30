@feature-carpaccio-handoff-no-manual-steps
Feature: The DISTILL to DELIVER carpaccio handoff needs no manual steps

  The three historical frictions at the carpaccio handoff are each locked
  closed by a regression scenario, so a future change cannot silently reopen
  the discovery-tag gap, weaken the per-scenario slice-tag mandate, or break
  the AT-review verdict round-trip.

  @slice-01 @contract-shape:unbounded-preservation
  Scenario: A feature-tagged scenario file is discovered by the gate
    Given an authored scenario file that self-identifies with the feature tag
    When the carpaccio gate discovers the feature's scenarios
    Then the gate finds at least one scenario

  @slice-01 @contract-shape:unbounded-preservation
  Scenario: A scenario carrying no per-scenario slice tag is rejected
    Given an authored scenario that carries no per-scenario slice tag
    When the carpaccio gate checks total slice-tag coverage
    Then the gate rejects the handoff naming the missing-slice-tag mandate

  @slice-01 @contract-shape:unbounded-preservation
  Scenario: An approved AT-review verdict round-trips without a manual ledger edit
    Given the reviewer records an approved AT-review verdict through the recorder
    When the carpaccio gate reads back the AT-review verdict for the slice
    Then the gate accepts the slice as approved with no manual ledger edit
