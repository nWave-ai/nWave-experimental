@feature-atdd-pure-spine-hardening @slice-02
Feature: G_COMMIT exit-gate SubagentStop intercept

  U2 of F-DES-ATDD-PURE-HOOK-GATES. An atdd_pure crafter returning from the
  G_COMMIT phase is intercepted at the SubagentStop boundary. The intercept
  runs the slice-commit completeness exit gate (E1) and the contract gate (E2)
  against a pinned commit SHA; on either failure it stops the orchestrator via
  a {decision: block} JSON body and exit 0 -- never a bare exit 1. A handler
  exception inside the atdd_pure branch is itself a fail-closed block.

  @wiring_e2e @walking_skeleton @driving_port
  Scenario: A G_COMMIT return with a complete slice commit is allowed
    Given an atdd_pure crafter has committed a complete slice commit
    And the crafter returns from the G_COMMIT phase
    When the SubagentStop hook processes the return
    Then the G_COMMIT intercept is allowed
    And the intercept records a verified slice commit in the ledger

  @driving_port @error
  Scenario Outline: A G_COMMIT return is blocked when an exit gate fails
    Given an atdd_pure crafter has committed <commit_shape>
    And the crafter returns from the G_COMMIT phase
    When the SubagentStop hook processes the return
    Then the G_COMMIT intercept <gate_outcome>
    And the intercept records <ledger_event> in the ledger

    Examples:
      | commit_shape                     | gate_outcome | ledger_event              |
      | a multi-slice batched commit     | is allowed   | a verified slice commit   |
      | an incomplete slice commit       | is blocked   | a blocked slice commit    |
      | a commit with no slice trailer   | is blocked   | a blocked slice commit    |

  @driving_port @error
  Scenario: A handler fault inside the atdd_pure branch is a fail-closed block
    Given an atdd_pure crafter has committed a complete slice commit
    And the crafter returns from the G_COMMIT phase
    And a fault is injected inside the G_COMMIT intercept
    When the SubagentStop hook processes the return
    Then the G_COMMIT intercept is blocked
    And the intercept reports an internal hook error
    And the hook exits with code zero

  @wiring_e2e @driving_port
  Scenario: A two-block transcript resolves the last G_COMMIT dispatch
    Given an atdd_pure crafter has committed a complete slice commit
    And the crafter transcript carries a stale earlier dispatch block
    When the SubagentStop hook processes the return
    Then the G_COMMIT intercept is allowed
    And the intercept records a verified slice commit in the ledger
