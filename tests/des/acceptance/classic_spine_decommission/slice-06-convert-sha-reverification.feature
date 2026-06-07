@feature-classic-spine-decommission
Feature: An architect's conversion re-verifies committed work against git
  As a solution architect retiring the classic roadmap spine
  I want the converter to re-verify every committed step against git history
    rather than trusting the COMMIT/PASS log event
  So that no slice is ever marked shipped without working code behind it

  # slice-06 of classic-spine-decommission. M2: the converter re-verifies each
  # COMMIT/PASS SHA (exists, reachable, tests green now) and applies the N:1
  # cardinality rule -- a slice ships only if ALL its constituent steps
  # re-verify; otherwise pending, with committed SHAs recorded as provenance.
  #
  # Layer 3 (subprocess / FS acceptance). Example-only -- sad paths enumerated
  # explicitly (Mandate 11). state-delta + Universe assertions (Mandate 8).
  #
  # Driving port: `des.cli.convert_to_atdd_pure` (main(argv)).

  # --- M2: re-verify the SHA, never trust the COMMIT/PASS log event ------------

  @slice-06 @driving_port @contract-shape:bounded-change
  Scenario Outline: A slice whose committed step fails re-verification stays pending
    Given a classic feature "convert-target" that carries a recovered slice plan
    And the classic feature has 12 roadmap steps
    And roadmap steps "02-01" constitute slice "slice-02"
    And step "02-01" was committed at "bbbb222" whose commit <sha_verdict>
    When the architect converts the feature
    Then slice "slice-02" is reconciled as pending
    And slice "slice-02" records the committed work as provenance "bbbb222"

    Examples: SHA re-verification failure modes
      | sha_verdict                  |
      | was reverted                 |
      | does not exist in history    |
      | has red tests now            |

  # --- HIGH-5 N:1 cardinality: a slice ships only if ALL its steps re-verify ---

  @slice-06 @driving_port @contract-shape:bounded-change
  Scenario: A slice with one missing constituent step is reconciled pending with provenance
    Given a classic feature "convert-target" that carries a recovered slice plan
    And the classic feature has 12 roadmap steps
    And roadmap steps "03-01 03-02" constitute slice "slice-03"
    And step "03-01" was committed at "cccc333" whose commit exists and is reachable with green tests
    When the architect converts the feature
    Then slice "slice-03" is reconciled as pending
    And slice "slice-03" records the committed work as provenance "cccc333"
