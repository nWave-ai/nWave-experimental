@feature-f-distill-wiring-to-registry
Feature: The DISTILL gate-out boundary resolves all four gates from the live registry

  The DISTILL return is mechanically checked by the gates the spine resolves from
  the canonical wave-contract registry. self-attest (the verdict-validity layer)
  and verify-test-runner (the test-execution witness) must fire from that LIVE
  registry alongside the AT-completeness check and the design-coherence gate -- not
  sit catalogued-but-dormant in a flavor block the spine never reads. The dormant
  flavor co-tenant that false-credited the closure scorecard is removed, and the
  GOAL CONTRACT is tightened so no dead flavor block can ever false-credit a wired
  module again. Then f-coherence-and-attestation's DONE is honest by construction.

  @slice-01 @walking-skeleton @driving_port @contract-shape:bounded-change @CT-1
  Scenario: The DISTILL gate-out boundary resolves all four gates in declared order
    Given the DISTILL gate-out boundary
    When the gate-out stack is resolved from the live registry
    Then the boundary resolves the four gates in declared order

  @slice-01 @driving_port @contract-shape:bounded-change @CT-2
  Scenario: The two newly wired gates do not veto a record-absent DISTILL return
    Given the DISTILL gate-out boundary
    When the gate-out stack is resolved from the live registry
    Then both newly wired gates surface their objection without vetoing the return

  @slice-01 @driving_port @contract-shape:bounded-change @CT-3
  Scenario: The dormant flavor co-tenant is removed once the registry carries the gates
    Given the DISTILL gate-out boundary
    When the flavor file is inspected for the dormant DISTILL co-tenant
    Then the dormant flavor co-tenant is absent

  @slice-01 @driving_port @contract-shape:bounded-change @CT-4
  Scenario: The coherence feature's three wired modules all live-resolve honestly
    Given the closure scorecard goal contract
    When the scorecard evaluates the coherence feature's wired modules
    Then every coherence wired module is counted wired from live resolution

  @slice-01 @driving_port @contract-shape:bounded-change @CT-5
  Scenario: A gate present only as a flavor string is no longer false-credited as wired
    Given the closure scorecard goal contract
    When the scorecard evaluates a gate present only as a flavor string
    Then the flavor-only gate is not counted wired
