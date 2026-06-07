@feature-fix-distill-human-signoff
Feature: The verify coverage map gate blocks the DISTILL exit and re-checks at the DELIVER exit

  The verify gate runs at two touchpoints: at the DISTILL-exit handoff to
  DELIVER, and again at the DELIVER-exit handoff to feature-end. The DISTILL
  touchpoint catches an absent / unsigned / structurally-incomplete coverage
  map. The DELIVER touchpoint catches a coverage map that went stale during
  DELIVER — distinguishing a coverage-map body edit (signoff stale) from a
  .feature AT-population change (omission detected after the fact). Two
  distinct sensors, two distinct exit names — they must not be conflated.

  # Driving port: the PreToolUse-style hook intercept wiring (per ADR-030
  # there is no native exit_gates YAML key). Layer 3 (subprocess / FS
  # acceptance) wiring proof; example-only (Mandate 11).

  Background:
    Given a feature whose design wave has produced a component manifest

  @slice-06 @walking_skeleton @wiring_e2e @driving_port @error @contract-shape:bounded-change
  Scenario Outline: The DISTILL exit handoff is blocked when the coverage map is not trustworthy
    Given the coverage map is in <unsigned_state> at the DISTILL exit
    When the workflow attempts the DISTILL to DELIVER handoff
    Then the handoff is blocked at the DISTILL exit

    Examples:
      | unsigned_state                                  |
      | absent from the feature distill directory       |
      | present but not signed by any human             |
      | present and signed but missing a mandatory section |

  @slice-06 @driving_port @error @contract-shape:bounded-change
  Scenario Outline: The DELIVER exit re-check blocks a coverage map that went stale during DELIVER
    Given a signed coverage map was approved at the DISTILL exit
    And during DELIVER <staleness_cause>
    When the workflow attempts the DELIVER to feature end handoff
    Then the handoff is blocked at the DELIVER exit with verdict <verdict>

    Examples:
      | staleness_cause                                                         | verdict                                          |
      | the acceptance designer edited a signed section of the coverage map    | the verify gate refuses for a stale signoff      |
      | an acceptance scenario carrying a covers tag was dropped               | the verify gate refuses for an undeclared omission |

  @slice-06 @driving_port @contract-shape:bounded-change
  Scenario: Both touchpoints pass when the signed coverage map remains valid and current
    Given a signed coverage map was approved at the DISTILL exit
    And during DELIVER the signed sections of the coverage map are unchanged
    And during DELIVER no acceptance scenario carrying a covers tag was dropped
    When the workflow runs the DISTILL exit handoff and the DELIVER exit re-check
    Then the workflow proceeds past both touchpoints
