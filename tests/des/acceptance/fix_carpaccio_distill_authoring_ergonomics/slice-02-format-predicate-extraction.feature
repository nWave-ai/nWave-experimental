@feature-fix-carpaccio-distill-authoring-ergonomics
Feature: The gate's format checks live in one shared place the pre-check can reuse

  The gate's format requirements (slice-size ceiling, per-scenario slice tagging,
  slice-plan parsing, feature binding) must be reusable by a new designer-facing
  pre-check WITHOUT a second, divergent checker that could disagree with the gate
  (ADR-001). To make that reuse possible the format predicates move into one
  shared place that both the gate and the pre-check read. The move must not change
  what the gate does: the same slice that cleared before still clears, and the
  same slice that was refused before is still refused, with the same verdict.

  # ADR-001: single shared format-predicate module; the gate reuses it.
  # Driving port: the real `des carpaccio-slice-gate` CLI invoked as a subprocess
  # (Layer 3 / wiring_e2e). Example-only, no PBT (Mandate 9/11). The shared
  # predicate module's existence + the gate's reuse of it is the new contract;
  # the existing untouched gate AT suite is the byte-identity regression net.

  Background:
    Given a repository for an atdd_pure feature

  @driving-port @real-io @slice-02 @contract-shape:bounded-change
  Scenario: A reviewed in-size slice still clears, drawing on the shared format checks
    Given the shared format checks are available as one reusable place
    And the feature carries a well-formed in-size slice plan
    And the entering slice has a recorded approved AT-review verdict
    When the operator runs the carpaccio slice gate for the entering slice
    Then the slice is cleared to enter implementation
    And the shared format checks resolve from a single reusable module
    And the gate writes no file in the repository

  @driving-port @real-io @slice-02 @contract-shape:bounded-change
  Scenario: An over-ceiling un-coupled slice is still refused, drawing on the shared format checks
    Given the shared format checks are available as one reusable place
    And the feature carries an over-ceiling slice that is not coupled
    And the entering slice has a recorded approved AT-review verdict
    When the operator runs the carpaccio slice gate for the entering slice
    Then the slice is refused as exceeding the carpaccio ceiling
    And the shared format checks resolve from a single reusable module
    And the gate writes no file in the repository
