@feature-fix-atdd-pure-spine-phase-count-reduction
Feature: The delivery runtime speaks the canonical three-phase vocabulary

  After the seven-phase vocabulary collapses to the canonical three
  (A_GREEN, C_REVIEWER_AUDIT, D_REFACTOR_COMMIT), the runtime must still read
  a historical record written in the old seven-phase words: every legacy phase
  name replays losslessly onto its canonical phase, and a name the runtime has
  never spoken is refused outright rather than quietly mapped to a wrong phase.

  @slice-02 @coupled @driving_port @real-io @contract-shape:pure-function
  Scenario: The runtime recognises each canonical delivery phase it now speaks
    Given the delivery runtime exposes its phase-resolution port
    When the operator resolves the phase name "D_REFACTOR_COMMIT"
    Then the resolution succeeds
    And the resolved canonical phase is "D_REFACTOR_COMMIT"
    And every canonical phase resolves to itself

  @slice-02 @coupled @driving_port @real-io @contract-shape:pure-function
  Scenario Outline: A legacy phase name replays onto its canonical phase
    Given the delivery runtime exposes its phase-resolution port
    When the operator resolves the phase name "<legacy>"
    Then the resolution succeeds
    And the resolved canonical phase is "<canonical>"

    Examples:
      | legacy             | canonical         |
      | A_GREEN_ATS        | A_GREEN           |
      | B_COVERAGE_CLEANUP | A_GREEN           |
      | E_BATCH_REFACTOR   | D_REFACTOR_COMMIT |
      | F_FINAL_REVIEW     | D_REFACTOR_COMMIT |
      | G_COMMIT           | D_REFACTOR_COMMIT |

  @slice-02 @coupled @driving_port @real-io @error @contract-shape:pure-function
  Scenario: An unknown phase name is refused while known phases still resolve
    Given the delivery runtime exposes its phase-resolution port
    And every canonical phase resolves to itself
    When the operator resolves the phase name "TOTALLY_BOGUS_PHASE"
    Then the phase name is rejected as unknown
    And the unknown phase name does not silently map to a canonical phase

  @slice-02 @coupled @driving_port @real-io @contract-shape:pure-function
  Scenario: The retired routing marker is recognised as a routing event, not a phase
    Given the delivery runtime exposes its phase-resolution port
    And every canonical phase resolves to itself
    When the operator resolves the phase name "D_GAP_ROUTING"
    Then the resolution is recognised as a routing event
    And the routing event carries no canonical phase
    And the routing event is not rejected as unknown

  @slice-02 @coupled @wiring_e2e @real-io @contract-shape:bounded-change
  Scenario: A returning commit step is gated whether it speaks the canonical or legacy word
    Given a returning delivery agent in a workspace with no verified slice commit
    When the agent reports it has finished the canonical commit step
    Then the feature-end commit gate stops the agent from closing the slice
    When the agent reports it has finished the legacy commit step
    Then the feature-end commit gate stops the agent from closing the slice
