@feature-fix-distill-human-signoff @slice-02
Feature: The anti-omission check refuses a coverage map that silently drops a manifest domain

  Slice-01 proved the renderer emits a coverage map from a real manifest +
  real tagged scenarios. This slice delivers the mechanical anti-omission
  check: the renderer computes the manifest's declared domains MINUS the
  tag-covered domains, and refuses fail-closed if any residual domain is
  silently absent from the not-covered table. An acceptance designer cannot
  quietly drop a domain.

  This slice also delivers the not-applicable branch -- the §4.2 fail-
  functional escape for legacy features and genuinely-finite SUTs. A
  not-applicable feature still authors a degenerate coverage map and a human
  still co-signs; neither bricks legacy nor opens a two-gate bypass.

  And a lean cap (CAP = 7) on the not-covered surface: a coverage map a human
  cannot evaluate in one sitting is itself a defect signal, refused with
  CoverageMapOverCap.

  # Driving port: derive_coverage_map (anti-omission + cap + §4.2 branch).
  # Layer 3 (subprocess / FS acceptance) -- example-only sad paths (Mandate 11).
  # AT3 enumerates the cap/not-applicable equivalence classes as Scenario
  # Outline rows -- closed finite domain (the falsifier-gate selects
  # examples, not @given; Mandate 9 -- this is layer 3).

  Background:
    Given a feature whose design wave has produced a component manifest

  @slice-02 @driving_port @error @contract-shape:bounded-change
  Scenario: A manifest domain silently dropped from the coverage map is refused
    Given a manifest domain is left uncovered by every acceptance scenario tag
    And the acceptance designer suppresses that domain from the not covered table
    When the acceptance designer renders the coverage map
    Then the renderer refuses for an undeclared omission
    And no coverage map is written to the feature distill directory

  @slice-02 @driving_port @contract-shape:bounded-change
  Scenario: A coverage map that lists every uncovered domain is accepted
    Given a manifest domain is left uncovered by every acceptance scenario tag
    When the acceptance designer renders the coverage map
    Then a coverage map is written to the feature distill directory
    And the not covered table places the domain on the dimension row matching its category

  @slice-02 @property @error @driving_port @contract-shape:bounded-change
  Scenario Outline: The lean cap and the not-applicable branch are each enforced
    Given the feature is in <state> with respect to the cap and the not-applicable branch
    When the acceptance designer renders the coverage map
    Then the renderer responds with <verdict>

    Examples:
      | state                                                                                                    | verdict                                                    |
      | more than seven uncovered manifest domains are present                                                    | the renderer refuses for an over cap surface               |
      | the manifest carries a not-applicable marker and the human attestation line is present in the signoff    | a coverage map is written to the feature distill directory |
      | the manifest carries a not-applicable marker and the human attestation line is missing from the signoff  | the renderer refuses for a missing signoff                 |
