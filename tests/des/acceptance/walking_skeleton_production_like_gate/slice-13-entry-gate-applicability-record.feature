@feature-walking-skeleton-production-like-gate
Feature: The entry gate records the applicability decision as a single source of truth
  As an nWave framework developer
  I want the entry gate to write an applicability record naming the paths it
    checked, so the feature-end gate consumes it rather than re-deriving it
  So that a stale set of changed files cannot flip the verdict later

  # carpaccio slice-13 (DESIGN slice-06, part 2 of 2). B3: the entry-gate
  # WalkingSkeletonApplicability record is the SSOT the feature-end gate
  # consumes -- never a re-derivation from a possibly-stale set of changed
  # files. Layer 3 (subprocess / FS acceptance): real composition root,
  # example-only, no PBT (Mandate 9/11). State-mutating steps assert via
  # assert_state_delta over a port-exposed ledger universe (Mandate 8).
  #
  # Driving port: the carpaccio entry-gate (`des.cli.carpaccio_slice_gate`).

  @slice-13 @driving_port @contract-shape:bounded-change
  Scenario: The entry gate writes an applicability record naming the paths it checked
    Given a feature that ships a packaged CLI module
    And the feature carries a walking-skeleton acceptance test
    When the carpaccio entry gate evaluates the feature at slice-one entry
    Then the entry gate writes an applicability record naming the paths it checked and the matched rule
