@feature-atdd-pure-spine-hardening @slice-04
Feature: Feature-end terminal intercept and hook-version skew contract

  U4 + D6 of F-DES-ATDD-PURE-HOOK-GATES. The U4 feature-end terminal
  SubagentStop intercept fires when an atdd_pure F_FINAL_REVIEW agent returns
  and every planned slice is shipped (derived from the U3 AT-completion ledger
  under the M7 fail-closed read contract). A corrupt ledger blocks with
  LedgerIntegrityViolation rather than degrading to the markdown fallback. The
  D6 hook-version contract stamps nwave_hook_version atomically at install
  time; the skew detector classifies behind / ahead / stamp-absent.

  slice-05 revision (Finding 1): feature-end no longer passes merely on
  "every slice shipped". The feature-end cycle must have written an
  EBatchRefactorCompleted record AND a FeatureEndReviewVerdict record into the
  U3 ledger; absent either, U4 blocks FeatureEndCycleIncomplete.

  @wiring_e2e @walking_skeleton @driving_port
  Scenario: A feature-end return with a complete cycle runs the integrity gate
    Given an atdd_pure feature whose every planned slice is verified in the ledger
    And the feature-end cycle recorded its refactor and review verdict
    And the feature-end review agent returns from the F_FINAL_REVIEW phase
    When the SubagentStop hook processes the return
    Then the feature-end intercept is allowed
    And the hook exits with code zero

  @driving_port @error
  Scenario Outline: A feature-end return is blocked when the cycle is incomplete
    Given an atdd_pure feature whose every planned slice is verified in the ledger
    And the feature-end cycle is missing its <missing_record> record
    And the feature-end review agent returns from the F_FINAL_REVIEW phase
    When the SubagentStop hook processes the return
    Then the feature-end intercept is blocked
    And the intercept reports event FeatureEndCycleIncomplete
    And the hook exits with code zero

    Examples:
      | missing_record          |
      | EBatchRefactorCompleted |
      | FeatureEndReviewVerdict |

  @driving_port @error
  Scenario Outline: A feature-end return is blocked when the ledger is unusable
    Given an atdd_pure feature whose ledger is <ledger_shape>
    And the feature-end review agent returns from the F_FINAL_REVIEW phase
    When the SubagentStop hook processes the return
    Then the feature-end intercept is blocked
    And the intercept reports event <decision_event>
    And the hook exits with code zero

    Examples:
      | ledger_shape          | decision_event             |
      | corrupt               | LedgerIntegrityViolation   |
      | fault-injected        | AtddPureHookInternalError  |

  @driving_port @property
  Scenario Outline: The hook-version skew detector classifies the three cases
    Given an installed hook stamp <installed> and a running checkout <checkout>
    When the session-start skew detector classifies the hook version
    Then the skew case is <skew_case>

    Examples:
      | installed | checkout | skew_case    |
      | 3.13.0    | 3.13.0   | none         |
      | 3.12.0    | 3.13.0   | behind       |
      | 3.14.0    | 3.13.0   | ahead        |
      | absent    | 3.13.0   | stamp-absent |
      | garbled   | 3.13.0   | stamp-absent |
