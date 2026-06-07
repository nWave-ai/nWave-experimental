# slice-09 — the P3 composition-root gate, a git-free pure-AST arch-test behind
# the TestSuiteAstAdapter port (ADR-TEST-002 slice-09, Pillar 3).
#
# The gate reads a step-suite file as data and flags any pytest-bdd step body that
# HAND-WIRES the system-under-test — assembling its collaborator object graph
# inline (repo = InMemoryRepo(); svc = OrderService(repo, FakeClock(), ...)) —
# where a production composition-root entry call belongs (app = build_application()
# / compose_root()). A hand-wired step duplicates the production wiring, drifts
# from it, and exercises an object graph the user never runs (Pillar 3, "app as in
# production"). A step that builds the SUT through a composition-root entry call is
# clean and left alone.
#
# This is the MECHANIZABLE Pillar — P3 (composition-root) — only. P1
# (domain-language) and P2 (chained-narrative) are SEMANTIC judgments the AST
# cannot decide; they stay Tier-J agent-audit and are OUT of scope. The mechanism
# is the collaborator-constructing assignments of each step body
# (Capability.ASSIGNMENTS_CONSTRUCTING_TYPE) cross-checked against the
# presence/absence of a composition-root entry call (Capability.CALLS_IN_FUNCTION)
# — NO new capability is added by this slice (cap 10 pre-exists in the enum +
# cap-table; DELIVER realizes it on the adapter).
#
# Honest tagging: an in-process pure-AST source query — @component (auto-unit
# under tests/build/), NEVER @wiring_e2e/@subprocess. The gate practises the
# honesty it enforces. No spawn, no real I/O beyond reading a fixture file.

@feature-at-mandate-mechanical-enforcement @slice-09 @component
Feature: A step body hand-wiring the SUT is caught, while a composition-root call is left alone

  As the test author and the audit rotation
  I want each pytest-bdd step body mechanically checked so a step cannot assemble
  the system-under-test's collaborator object graph by hand where a production
  composition-root entry call belongs, while a step that builds the SUT through
  the composition root is cleared
  So that the composition-root discipline (Pillar 3) is enforced, not merely conventional

  Background:
    Given the composition-root gate

  @slice-09 @driving_port @contract-shape:pure-function
  Scenario: The gate catches a step body that hand-wires the SUT
    When the gate judges a step suite whose body hand-wires the system-under-test
    Then the composition-root gate rules the suite flagged
    And the gate names the offending step and the collaborator type it hand-wires
    And the judged step suite file is left untouched

  @slice-09 @contract-shape:pure-function
  Scenario: The gate clears a step body that builds the SUT through the composition root
    When the gate judges a step suite that builds the system through the composition root
    Then the composition-root gate rules the suite clean
    And the gate raises no objection to the clean composition-root step suite
