# slice-08 — the M2 technical-call-smell gate, a git-free pure-AST arch-test
# behind the TestSuiteAstAdapter port (ADR-TEST-002 slice-08, Mandate 2).
#
# The gate reads a step-suite file as data and flags any pytest-bdd step body
# that issues a TECHNICAL call — an HTTP client call (requests.* / httpx.*) or a
# DB call (db.execute / cursor.execute / session.execute), including a technical
# call nested inside an assertion (assert requests.get(url).status_code == 200) —
# where only domain-language delegation belongs (the Mystery-Guest / Eager-Test
# smell family, research C1; Mandate 2 three-abstraction-layer model). A step
# that delegates to a domain service and asserts a domain outcome is clean and
# left alone.
#
# This is the MECHANIZABLE half of M2 only — the call-shape DENYLIST. The
# ubiquitous-language SEMANTIC judgment ("does the step speak the domain?") stays
# Tier-J agent-audit and is OUT of scope. The mechanism is the dotted callee of
# each call site (Capability.CALLS_IN_FUNCTION, already produced by the
# production adapter — NO new capability is added by this slice).
#
# Honest tagging: an in-process pure-AST source query — @component (auto-unit
# under tests/build/), NEVER @wiring_e2e/@subprocess. The gate practises the
# honesty the suite enforces. No spawn, no real I/O beyond reading a fixture
# file off disk.

@feature-at-mandate-mechanical-enforcement @slice-08 @component
Feature: A step body issuing a technical call is caught, while domain delegation is left alone

  As the test author and the audit rotation
  I want each pytest-bdd step body mechanically checked so a step cannot issue an
  HTTP or DB call where only domain-language delegation belongs, while a
  legitimate domain-delegating step is cleared
  So that the technical-call-smell discipline is enforced, not merely conventional

  Background:
    Given the technical-call-smell gate

  @slice-08 @driving_port @contract-shape:pure-function
  Scenario: The gate catches step bodies that issue HTTP and DB calls
    When the gate judges a step suite whose bodies issue an HTTP call and a DB call
    Then the technical-call-smell gate rules the suite flagged
    And the gate names each offending step and the technical call it issues
    And the judged step suite file is left untouched

  @slice-08 @contract-shape:pure-function
  Scenario: The gate catches a step body asserting on a technical call
    When the gate judges a step suite whose assertion is driven by an HTTP call
    Then the technical-call-smell gate rules the suite flagged
    And the gate names the asserting step and the technical call it issues

  @slice-08 @contract-shape:pure-function
  Scenario: The gate clears a step suite that always delegates to domain services
    When the gate judges a step suite that always delegates to domain services
    Then the technical-call-smell gate rules the suite clean
    And the gate raises no objection to the clean domain-delegating step suite
