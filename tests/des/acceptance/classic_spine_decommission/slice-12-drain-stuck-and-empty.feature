@feature-classic-spine-decommission
Feature: An architect's drain completes deterministically around stuck features
  As a solution architect retiring the classic roadmap spine
  I want a drain with a stuck feature to park it and still convert the rest, and
    an all-stuck drain to complete with an empty conversion set
  So that no stuck legacy feature ever blocks release N

  # slice-12 of classic-spine-decommission. The drain's decoupled-completion
  # behaviour: a stuck feature is parked while the rest convert; an all-stuck
  # drain completes deterministically (M6). `classic` staying present makes
  # parking safe -- a parked feature still has a spine.
  #
  # Layer 3 (subprocess / FS acceptance). Example-only (Mandate 11).
  # state-delta + Universe assertions (Mandate 8).
  #
  # Driving port: `des.cli.convert_to_atdd_pure` (drain mode).

  @slice-12 @driving_port @contract-shape:bounded-change
  Scenario: A drain with one stuck feature parks it and converts the rest
    Given a classic feature "drain-a" that carries a recovered slice plan
    And the legacy feature "drain-d" is a classic feature with a corrupt roadmap
    When the architect drains the features "drain-a drain-d"
    Then the features "drain-d" are parked for follow-up
    And the features "drain-a" are converted

  @slice-12 @driving_port @contract-shape:bounded-change
  Scenario: A drain with no convertible features completes with an empty conversion set
    Given the legacy feature "drain-d" is a classic feature with a corrupt roadmap
    When the architect drains the features "drain-d"
    Then the features "drain-d" are parked for follow-up
