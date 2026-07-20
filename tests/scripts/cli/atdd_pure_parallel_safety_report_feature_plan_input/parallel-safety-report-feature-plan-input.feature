@feature-parallel-by-default-feature-plan
Feature: A maintainer gets a MEASURED verdict between two features an epic declares parallel

  A maintainer about to dispatch two features an epic's `## Wave: DISCUSS / [REF] Feature Plan`
  declares parallel-safe runs `des parallel-safety-report --epic-delta` and gets the SAME
  MEASURED-SAFE / DRIFT / UNMEASURED verdict the report already gives between slices (row 3,
  `measured-parallel-safety-report`) -- now between features. The verdict is ADVISORY: it never
  refuses the plan or blocks a dispatch. A `--scope` naming a declared-serial (`depends-on`)
  Feature Plan row, or supplying both/neither of `--epic-delta`/`--feature-delta`, is a malformed
  invocation, rejected before any measurement.

  # docs/feature/parallel-by-default-feature-plan/feature-delta.md D-6/D-7, Domain Examples 4-6,
  # DESIGN [REF] Contract Tests CT-6..CT-10. Driving port: `des parallel-safety-report
  # --epic-delta <path> --repo <path> --scope <id>=<paths> [--timeout <s>]`. D-6: no new
  # measurement mechanism, no new CLI command -- `classify_pair`/`SliceBlastRadiusPort`/
  # `run_parallel_safety_report` reused UNCHANGED from row 3.

  Background:
    Given an epic-delta authored for a multi-feature epic
    And the epic-delta carries a Feature Plan declaring feature-a and feature-b parallel-safe and feature-c depends-on feature-b

  @slice-02 @driving_port @real-io @contract-shape:unbounded-preservation @covers-R6
  Scenario: Two disjoint declared-parallel features measure MEASURED-SAFE
    Given the repository's feature-a and feature-b touch disjoint files
    When the maintainer runs the parallel-safety report over the epic-delta for feature-a and feature-b
    Then the report measures the pair MEASURED-SAFE
    And the report event shape matches the feature-delta input path
    And the check leaves the epic-delta unchanged

  @slice-02 @driving_port @real-io @error @contract-shape:unbounded-preservation @covers-R7
  Scenario: Two overlapping declared-parallel features measure DRIFT, naming the overlap
    Given the repository's feature-a and feature-b touch an overlapping file
    When the maintainer runs the parallel-safety report over the epic-delta for feature-a and feature-b
    Then the report measures the pair DRIFT naming the overlapping file
    And the check leaves the epic-delta unchanged

  @slice-02 @driving_port @real-io @error @contract-shape:unbounded-preservation @covers-R8
  Scenario: A timed-out declared-parallel feature measures UNMEASURED, naming the file
    Given the repository's feature-a scope cannot be measured within the time budget
    When the maintainer runs the parallel-safety report over the epic-delta for feature-a and feature-b with a forced timeout
    Then the report measures the pair UNMEASURED naming the unmeasurable file
    And the check leaves the epic-delta unchanged

  @slice-02 @driving_port @error @contract-shape:pure-function @covers-R9
  Scenario: A scope naming a declared-serial feature row is rejected
    When the maintainer runs the parallel-safety report over the epic-delta for feature-c and feature-a
    Then the report rejects the invocation naming feature-c as not a declared-parallel Feature Plan row

  @slice-02 @driving_port @error @contract-shape:pure-function @covers-R10
  Scenario Outline: An ambiguous or missing input source is rejected
    When the maintainer runs the parallel-safety report with <input_source_case>
    Then the report rejects the invocation for an ambiguous input source

    Examples: input-source cases
      | input_source_case              |
      | both --epic-delta and --feature-delta supplied |
      | neither --epic-delta nor --feature-delta supplied |
