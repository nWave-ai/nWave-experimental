# slice-04 — the M9/9-v2 PBT-layer-mode gate, a git-free pure-AST arch-test
# behind the TestSuiteAstAdapter port (ADR-TEST-002 D-C, slice-04).
#
# The gate reads a test file as data and reports whether it places a
# property-based-test construct (a @given-decorated test, or a
# RuleBasedStateMachine import/subclass) at a layer-3-or-deeper file — where only
# example-based tests belong (Mandate 9: PBT machinery is the default ONLY at
# layers 1-2; at layers 3+ each generated example is real-I/O-heavy, so PBT
# runtime cost is incompatible with the layer). A compliant file either keeps its
# PBT at layers 1-2 (PBT's home), or carries only example-based tests at layer 3+.
#
# Honest tagging: an in-process pure-AST source query — @component (auto-unit
# under tests/build/), NEVER @wiring_e2e/@subprocess. No spawn, no real I/O
# beyond reading a fixture file.

@feature-at-mandate-mechanical-enforcement @slice-04 @component
Feature: A property-based test stranded at the wrong layer is caught

  As the test author and the audit rotation
  I want each test file mechanically checked so a property-based test cannot sit
  at a layer where only example-based tests belong, while legitimate property
  tests at their home layer are left alone
  So that the PBT-layer-mode discipline is enforced, not merely conventional

  Background:
    Given the PBT-layer-mode gate

  @slice-04 @driving_port @contract-shape:pure-function
  Scenario: The gate catches a property test placed at a too-deep layer
    When the gate weighs a property test placed at a too-deep layer
    Then the PBT-layer-mode gate rules the file out of discipline
    And the gate names the stranded property test as a wrong-layer breach
    And the weighed test file is left untouched

  @slice-04 @contract-shape:pure-function
  Scenario: The gate catches a state-machine model placed at a too-deep layer
    When the gate weighs a state-machine model placed at a too-deep layer
    Then the PBT-layer-mode gate rules the file out of discipline
    And the gate names the stranded state-machine model as a wrong-layer breach

  @slice-04 @contract-shape:pure-function
  Scenario: The gate clears property tests at their home layer and example tests at depth
    When the gate weighs property tests kept at their home layer
    Then the PBT-layer-mode gate rules the file within discipline
    And the gate raises no objection to an example-based test placed at a deep layer
