@feature-classic-spine-decommission
Feature: An architect's classification survives every malformed classic artifact
  As a solution architect retiring the classic roadmap spine
  I want the detection CLI to survive every malformed artifact it meets and
    never mistake a roadmap+slice-plan feature for atdd_pure
  So that the conversion drain has a robust, crash-free worklist

  # slice-04 of classic-spine-decommission. The classify CLI's Earned-Trust
  # probe() fault-injection set: every malformed classic artifact yields a
  # manual-review row, and the S21 false-negative guard (a feature with both a
  # roadmap and a slice plan is classified classic, never atdd_pure).
  #
  # The classifier NEVER crashes -- a malformed artifact yields a
  # classic-needs-manual-review row, never an exception (DESIGN probe contract).
  #
  # Layer 3 (subprocess / FS acceptance). Example-only -- sad paths enumerated
  # explicitly (Mandate 11). state-delta + Universe assertions (Mandate 8).
  #
  # Driving port: `des.cli.classify_features` (python -m subprocess).

  # --- C6 robustness: the probe() fault-injection set --------------------------

  @slice-04 @driving_port @error @contract-shape:pure-function
  Scenario Outline: The classifier survives every malformed classic artifact
    Given the legacy feature "scan-target" is a classic feature mid-implementation
    And the feature "scan-target" has <corruption>
    When the architect classifies the feature tree
    Then the manifest classifies "scan-target" as a classic feature with a corrupt roadmap
    And the classifier did not crash

    Examples: malformed-artifact fault injection
      | corruption                                          |
      | a roadmap that is not valid JSON                    |
      | a hand-edited roadmap inconsistent with its log     |
      | an execution log with mixed-version events          |
      | an empty execution log                              |

  @slice-04 @driving_port @error @contract-shape:bounded-change
  Scenario: A feature with both a roadmap and a slice plan is not mistaken for atdd_pure
    Given the feature "scan-target" carries both a roadmap and a slice plan
    When the architect classifies the feature tree
    Then the manifest classifies "scan-target" as a classic feature mid-implementation
    And the manifest records "scan-target" as having a slice plan
    And the classifier did not crash
