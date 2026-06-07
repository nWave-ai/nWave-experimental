@feature-classic-spine-decommission
Feature: An architect drains convertible features and parks the unconvertible ones
  As a solution architect retiring the classic roadmap spine
  I want the drain to convert every convertible feature in one sequential pass
    and park an untagged or manual-review feature without losing it
  So that the epic completes deterministically even when a feature needs human
    attention

  # slice-11 of classic-spine-decommission. The drain's core behaviour: convert
  # every convertible feature sequentially; a feature with untagged scenarios or
  # one needing manual review is PARKED on `migration-parked.json` (M6).
  #
  # Layer 3 (subprocess / FS acceptance). Example-only (Mandate 11).
  # state-delta + Universe assertions (Mandate 8).
  #
  # Driving port: `des.cli.convert_to_atdd_pure` (drain mode).

  @slice-11 @driving_port @contract-shape:bounded-change
  Scenario: A drain converts every convertible feature in one sequential pass
    Given a classic feature "drain-a" that carries a recovered slice plan
    And a classic feature "drain-b" that carries a recovered slice plan
    When the architect drains the features "drain-a drain-b"
    Then the conversion is converted onto the atdd_pure spine
    And the features "drain-a drain-b" are converted

  @slice-11 @driving_port @error @contract-shape:bounded-change
  Scenario: A feature with untagged scenarios is parked, not converted
    Given a classic feature "drain-c" that carries a recovered slice plan
    And the feature's acceptance scenarios carry no slice tags
    When the architect drains the features "drain-c"
    Then the conversion is blocked pending DISTILL tagging
    And the features "drain-c" are parked for follow-up

  @slice-11 @driving_port @error @contract-shape:bounded-change
  Scenario: A feature flagged for manual review is parked, and the drain still completes
    Given the legacy feature "drain-d" is a classic feature with a corrupt roadmap
    When the architect drains the features "drain-d"
    Then the conversion is blocked pending manual review
    And the features "drain-d" are parked for follow-up
