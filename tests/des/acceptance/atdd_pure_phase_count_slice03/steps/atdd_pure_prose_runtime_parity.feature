@feature-fix-atdd-pure-spine-phase-count-reduction
Feature: The delivery skill documents the same spine the system actually runs

  The operator learns the atdd_pure delivery spine by reading the nw-deliver
  skill. If the skill describes a different set of phases than the one the
  running system executes, the operator is taught a spine that no longer exists.
  The skill's documented phase model must agree with the live runtime's
  canonical phase model, and must no longer teach the retired phase vocabulary.

  @slice-03 @coupled @contract-shape:unbounded-preservation
  Scenario: The delivery skill names every phase the running system executes
    Given the running system's canonical delivery phases
    And the delivery skill the operator reads
    Then the delivery skill names every phase the running system executes

  @slice-03 @coupled @contract-shape:unbounded-preservation
  Scenario: The delivery skill no longer teaches the retired phase vocabulary
    Given the running system's canonical delivery phases
    And the delivery skill the operator reads
    Then the delivery skill mentions no delivery phase the running system retired
    And the delivery skill makes no stale claim about the number of phases
