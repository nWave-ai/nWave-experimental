@feature-walking-skeleton-production-like-gate
Feature: When no environment can verify the artifact, the deferral is fail-closed
  As an nWave framework developer in a constrained environment
  I want a feature that cannot be verified locally to be deferred with a machine
    marker carrying a closed reason, never silently passed
  So that an unverifiable feature is deferred, not silently declared done

  # carpaccio slice-04 (DESIGN slice-03, part 1 of 3). Fail-mode D: when no
  # tier is provisionable the gate writes a `walking-skeleton-unverified`
  # marker and blocks "feature done". RM-6 classifies every fixture failure
  # with a closed reason; RM-3 ST-19 fails the gate closed when even the marker
  # cannot be written. Layer 3 (subprocess / FS acceptance): real composition
  # root, example-only, no PBT (Mandate 9/11). State-mutating steps assert via
  # assert_state_delta over a port-exposed marker+ledger universe (Mandate 8).
  #
  # Driving port: `des.cli.walking_skeleton_gate`.

  @slice-04 @driving_port @error @contract-shape:bounded-change
  Scenario: No provisionable environment writes a deferral marker and blocks done
    Given a feature that ships a packaged CLI module with a walking-skeleton acceptance test
    And the environment reports no provisionable environment
    When the feature-end gate attempts to verify the walking skeleton
    Then the walking-skeleton gate reports UNVERIFIED at tier of record T1
    And the gate writes a walking-skeleton-unverified marker naming the feature and the reason
    And the feature is not marked done

  # RM-6 -- the staged-install fixture fails with a classified reason, never an
  # uncaught traceback. Parametrize-collapse: one behavioural shape (a
  # classified UNVERIFIED), one row per RM-6 failure classification.
  @slice-04 @driving_port @error @infrastructure-failure @contract-shape:bounded-change
  Scenario Outline: A classified provisioning failure writes a marker with a closed reason
    Given a feature that ships a packaged CLI module with a walking-skeleton acceptance test
    And <provisioning_failure>
    When the feature-end gate attempts to verify the walking skeleton
    Then the walking-skeleton gate reports UNVERIFIED at tier of record T1
    And the deferral marker records a closed reason rather than free prose
    And the feature is not marked done

    Examples: every fixture failure is a classified deferral, not a crash
      | provisioning_failure                  |
      | the artifact build fails              |
      | the install prefix is not writable    |
      | the install prefix forbids execution  |
      | the disk is exhausted                 |
      | the install prefix is not clean       |

  # RM-3 ST-19 -- the failure of the fail-safe must itself fail closed.
  @slice-04 @driving_port @error @infrastructure-failure @contract-shape:bounded-change
  Scenario: A marker that cannot be written fails the gate closed
    Given a feature that ships a packaged CLI module with a walking-skeleton acceptance test
    And the environment reports no provisionable environment
    And the marker cannot be written to disk
    When the feature-end gate attempts to verify the walking skeleton
    Then the walking-skeleton gate exits non-zero with the marker-write-failed reason
    And the feature is not marked done
