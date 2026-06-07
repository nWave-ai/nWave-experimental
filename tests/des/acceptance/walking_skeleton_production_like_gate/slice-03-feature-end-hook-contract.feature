@feature-walking-skeleton-production-like-gate
Feature: A gate run that produces no honest verdict cannot pass for verification
  As an nWave framework developer
  I want the feature-end cycle to treat a crashed or timed-out gate run as a
    block, and a documentation-only feature as a recorded outcome
  So that a non-installed or no-op gate is never mistaken for a real pass

  # carpaccio slice-03 (DESIGN slice-02, part 2 of 2). The RM-1 fail-closed
  # hook-exit contract + the B3 recorded NOT_APPLICABLE path. Layer 3
  # (subprocess / FS acceptance): real composition root, example-only, no PBT
  # (Mandate 9/11). State-mutating steps assert via assert_state_delta over a
  # port-exposed ledger universe (Mandate 8).
  #
  # Driving port: the DES feature-end SubagentStop hook branch.

  # RM-1 fail-closed hook-exit contract -- the gate subprocess can fail to
  # produce an honest verdict three distinct ways; the hook branch must treat
  # each as a block. Parametrize-collapse: one behavioural shape, three rows.
  @slice-03 @driving_port @error @infrastructure-failure @contract-shape:bounded-change
  Scenario Outline: A gate subprocess that produces no honest verdict blocks feature-end
    Given a feature that ships a packaged CLI module with a walking-skeleton acceptance test
    And the walking-skeleton gate subprocess <subprocess_outcome>
    When the feature-end cycle reaches the walking-skeleton gate
    Then the feature-end cycle treats the run as <treated_as>
    And the feature is not marked done

    Examples: the gate subprocess fails to deliver a verdict
      | subprocess_outcome | treated_as |
      | exits non-zero     | FAIL       |
      | never exits        | FAIL       |
      | times out          | UNVERIFIED |

  # B3 -- NOT_APPLICABLE is a recorded outcome cross-checked against the
  # entry-gate SSOT, never a silent self-exoneration from a stale predicate.
  @slice-03 @driving_port @contract-shape:bounded-change
  Scenario: A documentation-only feature records a not-applicable verdict
    Given a feature that ships only documentation with no walking-skeleton acceptance test
    And the entry-gate recorded the feature as not shipping an installer artifact
    When the feature-end cycle reaches the walking-skeleton gate
    Then the walking-skeleton gate reports NOT_APPLICABLE at tier of record T1
    And the gate records a not-applicable ledger entry naming the paths it checked
    And feature-end proceeds

  @slice-03 @driving_port @error @contract-shape:bounded-change
  Scenario: A feature-end not-applicable that contradicts the entry-gate record is rejected
    Given a feature that ships a packaged CLI module with a walking-skeleton acceptance test
    And the entry-gate recorded the feature as shipping an installer artifact
    When the feature-end cycle reaches a gate that self-classifies the feature as not applicable
    Then the walking-skeleton gate reports FAIL at tier of record T1
    And the gate diagnostic states the applicability record was contradicted
    And the feature is not marked done
