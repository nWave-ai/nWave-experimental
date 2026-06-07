# slice-07 — the M11 integration-sad-path gate, a git-free pure-AST arch-test
# behind the TestSuiteAstAdapter port (ADR-TEST-002 slice-07, Mandate 11).
#
# The gate enforces two halves of Mandate 11 (sad paths at layers 3+ stay
# example-based, every declared failure mode is tested):
#
#   * no-PBT-in-layer-3+-sad-path — it reads a sad-path test file as data and,
#     if classified at a layer-3+ file (integration/wiring_e2e/e2e — the
#     layers-3+ the adapter can actually emit), flags any property-based-test
#     construct (a @given test, a stateful-PBT import) where only enumerated
#     example-based sad paths belong. A PBT construct at its home layer (1-2) is
#     compliant and left alone. This recasts the dormant
#     check_robustness_density layer logic behind the port.
#   * failure-mode-coverage — it cross-checks a component manifest's
#     failure_modes entries against the named tests in scope, flagging a declared
#     failure mode that no named test covers.
#
# Honest tagging: an in-process pure-AST/YAML source query — @component
# (auto-unit under tests/build/), NEVER @wiring_e2e/@subprocess. The gate
# practises the honesty the suite enforces. No spawn, no real I/O beyond reading
# a fixture file off disk.

@feature-at-mandate-mechanical-enforcement @slice-07 @component
Feature: A property-based sad path at the wrong layer, or an untested failure mode, is caught

  As the test author and the audit rotation
  I want each layer-3+ sad-path file mechanically checked so a property-based
  test cannot sit where only enumerated example-based sad paths belong, and every
  failure mode a component declares to have at least one named test, while
  property tests at their home layer and fully-covered manifests are left alone
  So that the integration-sad-path discipline is enforced, not merely conventional

  Background:
    Given the integration-sad-path gate

  @slice-07 @driving_port @contract-shape:pure-function
  Scenario: The gate catches a property-based sad path stranded at a too-deep layer
    When the gate weighs a property-based sad path placed at a too-deep layer
    Then the integration-sad-path gate rules the file out of discipline
    And the gate names the stranded property sad path as a wrong-layer breach
    And the weighed sad-path file is left untouched

  @slice-07 @contract-shape:pure-function
  Scenario: The gate clears enumerated sad paths at depth, property tests at home, and survives an adversarial shape
    When the gate weighs enumerated example sad paths placed at a too-deep layer
    Then the integration-sad-path gate rules the file within discipline
    And the gate raises no objection to a property sad path kept at its home layer
    And the gate survives an adversarial sad-path file without crashing

  @slice-07 @contract-shape:bounded-change
  Scenario: The gate catches a declared failure mode that no named test covers
    When the gate cross-checks a manifest declaring a failure mode no test covers
    Then the integration-sad-path gate rules the failure-mode coverage incomplete
    And the gate names the uncovered failure mode
    And the gate raises no objection to a manifest whose every failure mode is covered
