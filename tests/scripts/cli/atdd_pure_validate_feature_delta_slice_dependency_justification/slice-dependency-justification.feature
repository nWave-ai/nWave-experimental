@feature-parallel-by-default-slice-plan
Feature: A slice plan reads parallel-safe by default; a declared dependency must justify itself

  A Product Owner or acceptance-designer authoring a `## Wave: DISCUSS / [REF] Slice Plan`
  row leaves the Annotation cell empty when nothing blocks that slice from running alongside
  its neighbours -- the row reads parallel-safe, no Justification owed. A row that DOES carry
  `depends-on {slice-id}` makes a real claim, so it must carry its own one-line Justification
  or the plan is rejected, naming the offending row. The rule checks only that a Justification
  EXISTS when `depends-on` is present -- never whether the claim is true (that is a reviewer's
  and, eventually, `measured-parallel-safety-report`'s job).

  # docs/feature/parallel-by-default-slice-plan/feature-delta.md D-1..D-6, Domain Examples 1-3.
  # Driving port: `des validate-feature-delta --require-slice-plan --format=json` (slice-plan
  # mode) and `--require-feature-plan --format=json` (feature-plan isolation scenario).
  # Layer 3 (subprocess/FS acceptance) -- example-only, no PBT: the annotation vocabulary is a
  # finite, enumerable closed set (empty / @walking_skeleton / @infrastructure / @coupled /
  # depends-on), so a Scenario Outline over that set is the correct paradigm (Mandate 9/11).

  Background:
    Given a feature-delta authored for an atdd_pure feature

  @slice-01 @driving_port @walking_skeleton @contract-shape:pure-function
  Scenario: A slice with no declared dependency owes no Justification and reads parallel-safe
    Given the feature-delta carries a slice plan whose second row carries no annotation and an empty Justification
    When the Product Owner runs the slice-plan check on the feature-delta
    Then the slice plan is accepted
    And the check leaves the feature-delta unchanged

  @slice-01 @driving_port @contract-shape:pure-function
  Scenario Outline: A row whose Annotation makes no dependency claim stays Justification-free
    Given the feature-delta carries a slice plan whose second row carries <annotation> and an empty Justification
    When the Product Owner runs the slice-plan check on the feature-delta
    Then the slice plan is accepted

    # The DoD's closed non-dependency Annotation set (empty already covered by the walking-
    # skeleton scenario above; this Outline covers the three named tokens D-2 explicitly frees
    # of the justification burden).
    Examples: non-dependency annotation tokens
      | annotation         |
      | @walking_skeleton   |
      | @infrastructure      |
      | @coupled               |

  @slice-01 @driving_port @contract-shape:pure-function
  Scenario: A declared dependency with a one-line Justification is accepted
    Given the feature-delta carries a slice plan whose second row declares depends-on slice-01 with a non-empty Justification
    When the Product Owner runs the slice-plan check on the feature-delta
    Then the slice plan is accepted
    And the check leaves the feature-delta unchanged

  @slice-01 @driving_port @error @contract-shape:pure-function
  Scenario: A declared dependency with an empty Justification is rejected, naming the offending row
    Given the feature-delta carries a slice plan whose second row declares depends-on slice-01 with an empty Justification
    When the Product Owner runs the slice-plan check on the feature-delta
    Then the slice plan is rejected for an unjustified slice dependency
    And the rejection names the offending row
    And the check leaves the feature-delta unchanged

  @slice-01 @driving_port @error @contract-shape:pure-function
  Scenario: A structurally malformed dependency row fails loud rather than slipping through accepted
    Given the feature-delta carries a slice plan whose second row is a dependency-shaped row missing its Justification column entirely
    When the Product Owner runs the slice-plan check on the feature-delta
    Then the slice plan is rejected for a malformed slice plan
    And the check leaves the feature-delta unchanged

  @slice-01 @driving_port @contract-shape:pure-function
  Scenario: Feature Plan mode enforces its own dependency-justification rule, not the slice one
    # parallel-by-default-feature-plan slice-01 (row 4) generalizes this exact rule one
    # granularity up: the flip is real (D-1/D-2 of that feature), so this isolation scenario
    # now proves the CROSS-MODE boundary a different way -- the rejection fires with the
    # feature-plan mode's OWN token (`unjustified-feature-dependency`), never the slice
    # token (`unjustified-slice-dependency`) this suite's own rule emits. The slice rule
    # still does not leak; feature-plan mode simply grew its own sibling rule.
    Given an epic-delta whose feature plan carries a depends-on row with an empty Justification
    When the maintainer runs the feature-plan check on the epic-delta
    Then the feature plan is rejected for an unjustified feature dependency
