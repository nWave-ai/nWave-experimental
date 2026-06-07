# slice-01 — the M1 driving-port-boundary gate, recast as a git-free pure-AST
# arch-test behind the TestSuiteAstAdapter port (ADR-TEST-002, walking skeleton).
#
# The gate reads a step suite as data and reports whether any driving-port
# action (a @when step) reaches for a driven adapter directly — a Mandate-1
# hexagonal-boundary breach. It is the cheapest already-written gate (the
# dormant check_driving_port_boundary.py), recast to prove the WHOLE enforcement
# pattern end-to-end: rule + port + Python adapter + golden fixtures + self-AT.
#
# Honest tagging: an in-process pure-AST source query — @component (auto-unit
# under tests/build/), NEVER @wiring_e2e/@subprocess. No spawn, no real I/O
# beyond reading a fixture file.

@feature-at-mandate-mechanical-enforcement @slice-01 @component
Feature: A driving-port action that reaches for a driven adapter is caught

  As the methodology maintainer
  I want each step suite mechanically checked so a @when action cannot quietly
  enter through a driven adapter instead of the driving port
  So that the hexagonal-boundary mandate is enforced, not merely conventional

  Background:
    Given the driving-port-boundary gate

  @slice-01 @walking_skeleton @driving_port @contract-shape:pure-function
  Scenario: The gate catches a step that enters through a driven adapter
    When the gate inspects a step suite that reaches for a driven adapter inside an action
    Then the gate reports the suite as flagged
    And the gate names the offending action and the driven adapter it reached for
    And the inspected step suite is left unchanged

  @slice-01 @contract-shape:pure-function
  Scenario: The gate clears a step suite that always enters through the driving port
    When the gate inspects a step suite that enters only through the driving port
    Then the gate reports the suite as clean
    And the gate raises no objection to setup that touches an adapter outside an action
