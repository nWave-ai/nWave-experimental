# slice-03 — the M8 universe-bound-assertion gate, a git-free pure-AST arch-test
# behind the TestSuiteAstAdapter port (ADR-TEST-002 D-C, slice-03).
#
# The gate reads a test suite as data and reports whether any state-mutating
# layer-1-3 test fails the universe guard: either it never calls
# assert_state_delta at all (the assertion-free-test smell — the highest-value
# static smell), or it calls assert_state_delta but leaks a private
# underscore-prefixed name into the universe argument (coupling the test to an
# internal field a refactor would red for no functional reason). A compliant
# suite guards every mutation with assert_state_delta over port-observable names
# only.
#
# Honest tagging: an in-process pure-AST source query — @component (auto-unit
# under tests/build/), NEVER @wiring_e2e/@subprocess. No spawn, no real I/O
# beyond reading a fixture file.

@feature-at-mandate-mechanical-enforcement @slice-03 @component
Feature: A state-mutating test that skips or mis-scopes the universe guard is caught

  As the test author and the audit rotation
  I want each state-mutating test mechanically checked so a mutation cannot go
  unguarded by assert_state_delta and a universe cannot name a private field
  So that the universe-bound-assertion mandate is enforced, not merely conventional

  Background:
    Given the universe-bound-assertion gate

  @slice-03 @driving_port @contract-shape:pure-function
  Scenario: The gate catches a state-mutating test that never guards its mutation
    When the gate inspects a state-mutating test that never calls the universe guard
    Then the universe-guard gate reports the suite as flagged
    And the gate names the unguarded test as a missing-guard breach
    And the inspected test suite is left unchanged

  @slice-03 @contract-shape:pure-function
  Scenario: The gate catches a universe that names a private internal field
    When the gate inspects a state-mutating test whose universe names a private field
    Then the universe-guard gate reports the suite as flagged
    And the gate names the test and the private field leaked into the universe

  @slice-03 @contract-shape:pure-function
  Scenario: The gate clears a suite that guards every mutation over port-observable names
    When the gate inspects a suite that guards every mutation over port-observable names
    Then the universe-guard gate reports the suite as clean
    And the gate raises no objection to a read-only test that carries no guard
