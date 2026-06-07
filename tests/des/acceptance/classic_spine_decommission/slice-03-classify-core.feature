@feature-classic-spine-decommission
Feature: An architect gets the correct spine state for every classification class
  As a solution architect retiring the classic roadmap spine
  I want the detection CLI to classify a feature into its correct spine state
    and survive a corrupt roadmap
  So that the conversion drain has a deterministic, crash-free worklist

  # slice-03 of classic-spine-decommission. The classify CLI's core
  # classification behaviour: every spine-state class is assigned correctly,
  # and a corrupt roadmap yields a manual-review row rather than a crash.
  #
  # Layer 3 (subprocess / FS acceptance). Example-only -- sad paths enumerated
  # explicitly (Mandate 11). state-delta + Universe assertions (Mandate 8).
  #
  # Driving port: `des.cli.classify_features` (python -m subprocess).

  # --- C1/C3 cardinality + happy-path per class --------------------------------

  @slice-03 @driving_port @contract-shape:pure-function
  Scenario Outline: The classifier assigns each feature its correct spine state
    Given the legacy feature "scan-target" is <feature_state>
    When the architect classifies the feature tree
    Then the manifest classifies "scan-target" as <feature_state>
    And the classifier did not crash

    Examples: the five classification states
      | feature_state                                |
      | a classic feature mid-implementation          |
      | a classic feature whose DISTILL is done       |
      | a feature already on the atdd_pure spine      |
      | a feature that has not reached DISTILL        |

  @slice-03 @driving_port @error @contract-shape:pure-function
  Scenario: A feature whose roadmap is corrupt is flagged for manual review, not crashed
    Given the legacy feature "scan-target" is a classic feature mid-implementation
    And the feature "scan-target" has a truncated roadmap
    When the architect classifies the feature tree
    Then the manifest classifies "scan-target" as a classic feature with a corrupt roadmap
    And the classifier did not crash
