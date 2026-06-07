# slice-02 — the adapter-capability-registry SSOT (ADR-TEST-002 D-C, D11).
#
# The methodology maintainer reads ONE registry that enumerates EXACTLY every
# AST capability a per-language adapter must implement to satisfy all the gates.
# A per-language adapter is conformant iff it implements every required
# capability; an adapter missing a required capability is rejected as
# non-conformant, named. A registry that omits a capability a gate consumes is
# incomplete (fail-closed) — so adding a new target language is implementing
# against this single checklist, not hunting the requirement across N gates.
#
# Honest tagging: an in-process query of the registry catalog — @component
# (auto-unit under tests/build/), NEVER @wiring_e2e/@subprocess. No spawn, no
# real I/O. slice-02 is @infrastructure (slice-01 was the walking skeleton).

@feature-at-mandate-mechanical-enforcement @slice-02 @component
Feature: A new-language implementer reads one registry to learn every capability to build

  As the methodology maintainer
  I want the adapter-capability registry to enumerate the complete contract and
  to judge any adapter conformant only when it implements every required capability
  So that adding a target language is implementing against one checklist, not
  hunting the requirement across separate gates

  Background:
    Given the adapter-capability registry

  @slice-02 @coupled @contract-shape:pure-function
  Scenario: The registry enumerates every capability the gates require
    When the maintainer reads the required capabilities from the registry
    Then the registry names the complete capability contract for a language adapter
    And every capability any registered gate-rule consumes is named in the contract
    And the registry catalog is left unchanged

  @slice-02 @coupled @contract-shape:pure-function
  Scenario: The reference adapter is judged conformant for the capabilities the gates consume
    When the maintainer checks the reference language adapter against the capabilities the gates consume so far
    Then the registry reports the reference adapter as conformant
    And the registry names no missing capability for the reference adapter

  @slice-02 @coupled @contract-shape:pure-function
  Scenario: The complete reference adapter is judged conformant against the full contract
    When the maintainer checks a complete adapter against the full capability contract
    Then the registry reports the reference adapter as conformant
    And the registry names no missing capability for the reference adapter

  @slice-02 @coupled @contract-shape:pure-function
  Scenario: An adapter missing a required capability is rejected as non-conformant
    When the maintainer checks an adapter that is missing a required capability
    Then the registry reports the adapter as non-conformant
    And the registry names the missing capability the implementer must still build

  @slice-02 @coupled @contract-shape:pure-function
  Scenario: The registry is the single place a new-language implementer reads the contract
    When the maintainer reads the required capabilities from the registry
    Then no gate-rule consumes a capability that the contract leaves out
