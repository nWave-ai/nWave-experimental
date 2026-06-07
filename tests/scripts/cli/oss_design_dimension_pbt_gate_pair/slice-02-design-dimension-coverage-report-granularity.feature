@feature-oss-design-dimension-pbt-gate-pair @slice-02
Feature: The design-dimension coverage check tells the acceptance designer WHICH behavior axis is uncovered

  slice-01 proved the gate joins declared dimensions against witnessing
  properties and reports a bare verdict (PASS / INDETERMINATE / MALFORMED).
  slice-02 makes the report COMPREHENSIBLE: when a dimension is flagged, the
  acceptance designer must be able to read WHICH behavior axis is uncovered,
  not just that some count is short.

  Three report-granularity guarantees, all on top of slice-01's bare verdict:

  - The report resolves every flagged dimension to its summary text
    (the comprehension-key), never the bare identifier alone (DIM-4).
  - A dimension identifier mentioned only in a prose / rationale cell does NOT
    satisfy the join -- the dimension stays uncovered and the report still
    names it by its summary, so a prose mention can never silently witness a
    behavior axis (DIM-6).
  - A dimensions block whose only rows carry a blank or garbage identifier
    column is reported malformed -- never a silent zero-dimensions pass -- and
    the report names the vacuous-identifier reason rather than an
    undifferentiated either/or (DIM-7).

  # Driving port: scripts/cli/check_design_dimension_coverage.py invoked via
  # main(argv) (Mandate-13 driving-port-only -- never a direct-domain import
  # of the parser functions). Layer 3 (in-process / FS acceptance) -- example
  # only, no PBT (Mandate 9/11): the report-granularity observables (a flagged
  # dimension's summary appears; the malformation reason is named) are a finite
  # enumerable closed set of operator-facing report tokens.
  #
  # dimension: DIM-4
  # dimension: DIM-6
  # dimension: DIM-7

  Background:
    Given a feature whose design wave has declared a dimensions block for its report

  @slice-02 @coupled @error @driving_port @contract-shape:unbounded-preservation
  Scenario: An uncovered dimension is named by its summary in the report, not by its bare identifier
    Given the design wave declared a declared dimension named in the block that no property witnesses
    When the acceptance designer runs the design-dimension coverage report on the feature
    Then the report names the uncovered dimension by its summary text
    And the report does not name the uncovered dimension by its bare identifier alone
    And running the design-dimension coverage report leaves the feature-delta and the corpus unchanged

  @slice-02 @coupled @error @driving_port @contract-shape:unbounded-preservation
  Scenario: A dimension identifier mentioned only in a prose cell does not silently witness the behavior axis
    Given the design wave declared a declared dimension whose identifier also appears only in a prose cell
    When the acceptance designer runs the design-dimension coverage report on the feature
    Then the report names the uncovered dimension by its summary text
    And running the design-dimension coverage report leaves the feature-delta and the corpus unchanged

  @slice-02 @coupled @error @driving_port @contract-shape:unbounded-preservation
  Scenario: A block whose identifier column is blank is reported malformed with the vacuity reason named
    Given the design wave declared a dimensions block whose only rows carry a blank identifier column
    When the acceptance designer runs the design-dimension coverage report on the feature
    Then the feature is reported malformed because its identifier column is vacuous
    And running the design-dimension coverage report leaves the feature-delta and the corpus unchanged
