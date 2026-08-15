# slice-12 — the registry-conformance / drift-guard gate (ADR-TEST-002 D-C/D-E, D11; row 229).
#
# The drift-guard hardening makes the testarch registry self-defended: the same
# KIND of registry/vocabulary conformance this feature ships, now turned on the
# feature's OWN testarch substrate (Earned-Trust self-application). The gate covers
# two drift facets — a rule referencing a Layer value the adapter cannot produce,
# and a registered capability with no method on the real adapter.
#
# Golden-fixture recall/precision shape (ADR-TEST-002 D-E, the shape every Tier-S
# gate slices 01-09 uses; the slice-11 Tier-M meta-gate requires this gate — itself
# a gate — to carry a violation_ fixture + a clean_ fixture + this sibling .feature
# whose stem prefix-matches the fixture dir `registry_conformance`):
#
#   * RECALL (scenario 1) — drives the detectors against the FROZEN
#     violation_drifted_snapshot that PERMANENTLY carries both drift facets. Asserts
#     FLAGGED + the named offenders. Green forever — proves the gate CAN bite. (The
#     frozen fixture is never cleaned; only the LIVE substrate is cleaned by A_GREEN.)
#   * PRECISION on a frozen clean snapshot (scenario 2) — drives the detectors
#     against the FROZEN clean_conformant_snapshot (drift-free in both facets).
#     Asserts CONFORMANT — proves the gate does NOT over-fire on a conformant
#     substrate (the clean_ golden complement, the fail-closed precision bar).
#   * PRECISION on the LIVE substrate (scenario 3) — drives the detectors against
#     the LIVE production surface, read at runtime (the actual rule classification
#     sets + reference-adapter producible layers + registered Capability values +
#     real PythonAstAdapter method surface). Asserts CONFORMANT. This is the
#     production-surface analogue of the clean snapshot — green now that A_GREEN
#     dropped fs_acceptance from AUDITED_LAYERS and removed
#     the dead caps string_literals_in_call + parametrize_arg_source. It closes the
#     method-name-blind gap the slice-02 conformance check leaves (slice-02 validates
#     the CompleteFixtureAdapter double, never the production adapter).
#
# Honest tagging: an in-process introspection of the testarch substrate —
# @component (auto-unit under tests/build/), NEVER @wiring_e2e/@subprocess. No
# spawn, no real I/O. slice-12 is @infrastructure.

@feature-at-mandate-mechanical-enforcement @slice-12 @component
Feature: The methodology maintainer sees rule and adapter vocabulary drift flagged at author-time

  As the methodology maintainer
  I want a frozen drifted snapshot to be flagged by the conformance gate and both a
  frozen clean snapshot and the live testarch substrate to be conformant — every
  referenced layer value adapter-producible and every registered capability realized
  on the real adapter
  So that rule-to-adapter and registry-to-adapter vocabulary drift becomes
  red-at-author-time instead of human-caught in an audit rotation

  Background:
    Given the testarch drift-guard conformance gate

  @slice-12 @coupled @contract-shape:pure-function
  Scenario: A snapshot carrying a non-producible layer reference and an unrealized registered capability is flagged
    When the maintainer checks the frozen drifted snapshot
    Then the gate flags the layer-value drift in the snapshot
    And the gate names the non-producible layer value the snapshot references
    And the gate flags the capability drift in the snapshot
    And the gate names the registered capability the snapshot adapter does not realize

  @slice-12 @coupled @contract-shape:pure-function
  Scenario: A frozen conformant snapshot is cleared in both vocabulary dimensions
    When the maintainer checks the frozen conformant snapshot
    Then the gate reports every rule-referenced layer value as adapter-producible
    And the gate reports every registered capability as realized on the real adapter

  @slice-12 @coupled @contract-shape:pure-function
  Scenario: The live testarch substrate is conformant in both vocabulary dimensions
    When the maintainer checks the live testarch substrate
    Then the gate reports every rule-referenced layer value as adapter-producible
    And the gate reports every registered capability as realized on the real adapter
