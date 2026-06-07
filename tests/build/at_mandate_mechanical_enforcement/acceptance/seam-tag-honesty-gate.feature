# slice-05 — the CM-I seam-tag-honesty gate, a git-free pure-AST arch-test
# behind the TestSuiteAstAdapter port (ADR-TEST-001 D-8, ADR-TEST-002 slice-05).
#
# The gate reads a test file as data and cross-checks each test's marker tags
# (its CLAIM about what it spawns) against the spawn shape of its body (what it
# ACTUALLY spawns). A test tagged @wiring_e2e or @subprocess whose body only
# drives main(argv) in-process — no real subprocess spawn — is dishonest: the
# shared dispatch/packaging/exit seam is never exercised yet the tag asserts it
# is (the labelling half of the 7 fires). A test whose tag matches its spawn
# shape is honest and left alone.
#
# Honest tagging: an in-process pure-AST source query — @component (auto-unit
# under tests/build/), NEVER @wiring_e2e/@subprocess. The gate practises the
# honesty it enforces. No spawn, no real I/O beyond reading a fixture file.

@feature-at-mandate-mechanical-enforcement @slice-05 @component
Feature: A test wearing a real-subprocess tag over an in-process body is caught

  As the test author and the audit rotation
  I want each test mechanically checked so a test cannot wear a real-subprocess
  tag while its body only drives the command in-process, while genuinely honest
  tags are left alone
  So that the seam-tag-honesty discipline is enforced, not merely conventional

  Background:
    Given the seam-tag-honesty gate

  @slice-05 @driving_port @contract-shape:pure-function
  Scenario: The gate catches a real-subprocess tag worn over an in-process body
    When the gate judges a test that claims a real subprocess but runs in-process
    Then the seam-tag-honesty gate rules the file dishonest
    And the gate names the mislabelled test and the tag it falsely wears
    And the judged test file is left untouched

  @slice-05 @contract-shape:pure-function
  Scenario: The gate clears a real-subprocess tag worn over a genuine spawn
    When the gate judges a test that claims a real subprocess and genuinely spawns one
    Then the seam-tag-honesty gate rules the file honest

  @slice-05 @contract-shape:pure-function
  Scenario: The gate clears an in-process body wearing an honest in-process tag
    When the gate judges an in-process test honestly tagged as a component test
    Then the seam-tag-honesty gate rules the file honest
    And the gate raises no objection to the honest in-process component test
