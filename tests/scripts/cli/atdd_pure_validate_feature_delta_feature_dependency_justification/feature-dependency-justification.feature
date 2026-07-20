@feature-parallel-by-default-feature-plan
Feature: A Feature Plan row reads parallel-safe by default; a declared feature dependency must justify itself

  A Product Owner or maintainer authoring an epic's `## Wave: DISCUSS / [REF] Feature Plan`
  row leaves the Annotation cell empty when nothing blocks that feature from running alongside
  its neighbours -- the row reads parallel-safe, no Justification owed. A row that DOES carry
  `depends-on {feature-id}` makes a real claim, so it must carry its own one-line Justification
  or the plan is rejected, naming the offending feature row. The rule checks only that a
  Justification EXISTS when `depends-on` is present -- never whether the claim is true (that is
  a reviewer's and, eventually, `measured-parallel-safety-report`'s job). Same rule the Slice
  Plan already enforces (row 1, `parallel-by-default-slice-plan`), one granularity up.

  # docs/feature/parallel-by-default-feature-plan/feature-delta.md D-1..D-7, Domain Examples 1-3,
  # CT-1..CT-5. Driving port: `des validate-feature-delta --require-feature-plan --format=json`
  # (feature-plan mode) and `--require-slice-plan --format=json` (slice-plan isolation scenario,
  # CT-4). Layer 3 (subprocess/FS acceptance) -- example-only, no PBT: the Annotation vocabulary is
  # a finite, enumerable closed set (empty / @walking_skeleton / @infrastructure / depends-on), so a
  # Scenario Outline over that set is the correct paradigm (Mandate 9/11).

  Background:
    Given an epic-delta authored for a multi-feature epic

  @slice-01 @driving_port @walking_skeleton @contract-shape:pure-function @covers-R1
  Scenario: A feature with no declared dependency owes no Justification and reads parallel-safe
    Given the epic-delta carries a Feature Plan whose second row carries no annotation and an empty Justification
    When the maintainer runs the feature-plan check on the epic-delta
    Then the Feature Plan is accepted
    And the check leaves the epic-delta unchanged

  @slice-01 @driving_port @contract-shape:pure-function @covers-R1
  Scenario Outline: A row whose Annotation makes no dependency claim stays Justification-free
    Given the epic-delta carries a Feature Plan whose second row carries <annotation> and an empty Justification
    When the maintainer runs the feature-plan check on the epic-delta
    Then the Feature Plan is accepted

    # The DoD's closed non-dependency Annotation set for feature-plan mode (empty already covered
    # by the walking-skeleton scenario above; this Outline covers the two remaining tokens the
    # slice-01 Value statement names explicitly: "every other Annotation shape (empty,
    # @walking_skeleton, @infrastructure) is unaffected and owes no justification").
    Examples: non-dependency annotation tokens
      | annotation         |
      | @walking_skeleton   |
      | @infrastructure      |

  @slice-01 @driving_port @contract-shape:pure-function @covers-R2
  Scenario: A declared feature dependency with a one-line Justification is accepted
    Given the epic-delta carries a Feature Plan whose second row declares depends-on webhook-retry-core with a non-empty Justification
    When the maintainer runs the feature-plan check on the epic-delta
    Then the Feature Plan is accepted
    And the check leaves the epic-delta unchanged

  @slice-01 @driving_port @error @contract-shape:pure-function @covers-R3
  Scenario: A declared feature dependency with an empty Justification is rejected, naming the offending feature row
    Given the epic-delta carries a Feature Plan whose second row declares depends-on webhook-retry-core with an empty Justification
    When the maintainer runs the feature-plan check on the epic-delta
    Then the Feature Plan is rejected for an unjustified feature dependency
    And the rejection names the offending feature row
    And the check leaves the epic-delta unchanged

  @slice-01 @driving_port @error @contract-shape:pure-function @covers-R4
  Scenario: A structurally malformed feature-dependency row fails loud as a malformed Feature Plan, never a malformed Slice Plan
    Given the epic-delta carries a Feature Plan whose second row is a dependency-shaped row missing its Justification column entirely
    When the maintainer runs the feature-plan check on the epic-delta
    Then the Feature Plan is rejected for a malformed Feature Plan
    And the check leaves the epic-delta unchanged

  @slice-01 @driving_port @contract-shape:pure-function @covers-R5
  Scenario: The Slice Plan mode is unaffected by the new feature-dependency rule
    Given a feature-delta whose slice plan carries a depends-on row with an empty Justification
    When the Product Owner runs the slice-plan check on the feature-delta
    Then the slice plan is rejected for an unjustified slice dependency
