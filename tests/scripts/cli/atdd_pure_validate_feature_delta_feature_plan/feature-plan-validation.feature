@slice-01 @discuss-epic-mode
Feature: The feature-plan validator clears or rejects an epic's Feature Plan

  A maintainer decomposing a request bigger than one feature authors an
  epic-delta -- the `docs/epic/{id}/epic-delta.md` document whose
  `## Wave: DISCUSS / [REF] Feature Plan` section is a five-column table
  (Feature, Value statement, Status, Annotation, Justification) mirroring the
  carpaccio Slice Plan. Before that epic-delta drives any feature pickup, the
  maintainer runs the feature-plan check to confirm the section is present and
  structurally well formed, so a missing or malformed Feature Plan is caught
  mechanically -- the keystone abstraction every later epic-mode slice hangs on.

  The feature-plan check is the structural half of feature-plan validation: it
  asserts the section exists and the table carries the five required columns.
  Keystone designation, dependency order, and Status-token semantics belong to
  later slices (the dogfood ATs and the linkage/status-flip contract), a
  separate concern held out to keep this walking skeleton thin.

  # discuss-epic-mode R1 (Feature Plan heading reuses the D2 grammar verbatim) +
  # the slice-01 code-design (--require-feature-plan parametrizes the shared
  # five-column parser over (heading, columns); never forks). Driving port: the
  # production validate-feature-delta CLI invoked with --require-feature-plan
  # --format=json (`des.cli.validate_feature_delta.main`). Layer 3
  # (subprocess/FS acceptance) -- example-only, no PBT (Mandate 9/11): the
  # Feature Plan shapes form a finite, enumerable closed set, so the
  # falsifier-gate forbids PBT here.

  Background:
    Given an epic-delta authored for a multi-feature epic

  @slice-01 @walking_skeleton @driving_port @contract-shape:pure-function
  Scenario: A well-formed Feature Plan clears the structural check
    Given the epic-delta carries a well-formed Feature Plan
    When the maintainer runs the feature-plan check on the epic-delta
    Then the Feature Plan is accepted
    And the check leaves the epic-delta unchanged

  @slice-01 @driving_port @error @contract-shape:pure-function
  Scenario: An epic-delta with no Feature Plan section is rejected
    Given the epic-delta carries no Feature Plan section
    When the maintainer runs the feature-plan check on the epic-delta
    Then the Feature Plan is rejected for a missing Feature Plan
    And the check leaves the epic-delta unchanged

  @slice-01 @driving_port @error @contract-shape:pure-function
  Scenario Outline: An epic-delta whose Feature Plan table is malformed is rejected
    Given the epic-delta carries <feature plan>
    When the maintainer runs the feature-plan check on the epic-delta
    Then the Feature Plan is rejected for a malformed Feature Plan
    And the check leaves the epic-delta unchanged

    # R1 reuses the D2 "fixed order" contract verbatim for the Feature Plan, so
    # both a dropped column and a column re-order violate the fixed five-column
    # header. These are the two named malformed defects from the DESIGN slice-01
    # code-design (C1 detail-string table T3). The rejection diagnostic names
    # the cause so the maintainer knows what to repair.
    Examples: structurally unsound Feature Plans
      | feature plan                                            |
      | a Feature Plan with only four columns                   |
      | a Feature Plan whose table has the columns reordered    |
