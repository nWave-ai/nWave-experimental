@feature-fix-verify-wave-dispatch-exemption-ssot
Feature: verify-wave-dispatch agrees with the PreToolUse AT-3 BLOCK (one exemption SSOT)

  Two dispatch-exemption checks decide whether an Agent/Task dispatch is exempt
  from the wave-floor denial: the PreToolUse AT-3 floor check (production runtime
  enforcement) and the `des verify-wave-dispatch` gate. Today they DISAGREE on the
  collision case -- AT-3 BLOCKs, verify-wave-dispatch ALLOWs -- so a spine driver
  is told ALLOW by one gate and BLOCK by the other on the SAME dispatch. The
  ratified model is AT-3-BLOCK (Ale 2026-06-23): verify-wave-dispatch is brought
  into AGREEMENT with AT-3's BLOCK for the collision case. The deliberately-closed
  bypass is NOT reopened; every existing ALLOW path is preserved.

  # --- AC-1 + AC-5: the new collision-BLOCK behavior (ACTIVE-RED at HEAD) -------

  @slice-01 @driving_port @contract-shape:bounded-change @AC-1
  Scenario: A non-entering partial-marker in-wave dispatch under an active floor is blocked
    Given a wave-owner dispatch under an active wave floor that is not entering the wave
    And the dispatch carries only the matching wave marker without the validation marker
    When verify-wave-dispatch evaluates the dispatch
    Then verify-wave-dispatch blocks the dispatch

  @slice-01 @driving_port @property @contract-shape:bounded-change @AC-5
  Scenario Outline: The two exemption checks present one consistent verdict on the collision matrix
    Given the wave owner "<owner>" is dispatched under an active non-entering floor
    And the dispatch carries only the matching wave marker without the validation marker
    When both exemption checks evaluate the dispatch
    Then the PreToolUse floor check blocks the dispatch
    And the two exemption checks agree on the verdict

    Examples: collision matrix across wave owners
      | owner               |
      | acceptance-designer |
      | solution-architect  |
      | product-owner       |

  # --- AC-2: legit on-spine wave-entering author dispatch -> still ALLOW --------

  @slice-01 @driving_port @contract-shape:bounded-change @AC-2
  Scenario: A genuine wave-entering author dispatch is still allowed
    Given a wave-owner dispatch entering the wave with the matching wave marker
    When verify-wave-dispatch evaluates the dispatch
    Then verify-wave-dispatch allows the dispatch

  # --- AC-3: non-owner / reviewer -> still ALLOW (exempt control) ---------------

  @slice-01 @driving_port @contract-shape:bounded-change @AC-3
  Scenario: A reviewer dispatch under an active floor is still allowed (exempt control)
    Given a reviewer dispatch under an active wave floor that is not entering the wave
    When verify-wave-dispatch evaluates the dispatch
    Then verify-wave-dispatch allows the dispatch

  # --- AC-4: skip-authorization paths -> preserved (parametrized) ---------------

  @slice-01 @driving_port @contract-shape:bounded-change @AC-4
  Scenario Outline: Marker-less skip-authorization paths keep their preserved verdict
    Given a wave-owner dispatch under an active wave floor that is not entering the wave
    And the dispatch carries no wave marker
    And the dispatch carries a <authorization> skip authorization
    When verify-wave-dispatch evaluates the dispatch
    Then verify-wave-dispatch <expected> the dispatch

    Examples: skip-authorization matrix
      | authorization       | expected |
      | form-valid witness  | allows   |
      | valid pre-grant     | allows   |
      | expired pre-grant   | blocks   |
