@feature-skill-normative-content-gate @slice-02 @real-io @driving_port
Feature: The gate rejects non-discriminating markers and checks every cardinality
  # Slice-02 (DESIGN §9): the LOUD-rejection side of the discrimination rule
  # (INDETERMINATE on a non-discriminating marker) + zero/one/N cardinality with
  # an EXPLICIT Zero (C3 zero-obligation: the empty case is the FIRST scenario,
  # named and recognizable — a skill with zero registered clauses contributes no
  # findings, which is a verdict, not an error). The positive-acceptance side of
  # the discrimination rule (a discriminating multi-word phrase loads and is
  # enforceable) lives with its boundary in slice-04.
  #
  # Driven through the real `des` dispatcher (@real-io -> example-based,
  # Mandate 11). AC-08: the N-cardinality case reads the real shipped skill
  # files; the discrimination case asserts at manifest-load before any asset is
  # read.

  @contract-shape:bounded-change @ac-03 @zero-obligation @slice-02
  Scenario: Zero registered clauses for a skill contributes no findings, not an error
    Given a manifest registering zero clauses for an as-yet-unprotected skill
    When the maintainer runs the skill-normative gate through the des dispatcher
    Then the gate verdict is PASS with exit code 0
    And the empty case is reported as a verdict, never as an error

  @contract-shape:bounded-change @ac-03 @slice-02
  Scenario: One clause and many clauses are each checked across the real corpus
    Given a manifest registering one clause for one skill and many clauses for another
    When the maintainer runs the skill-normative gate through the des dispatcher
    Then the gate verdict is PASS with exit code 0
    And every registered clause across one-skill and many-skill is checked

  @contract-shape:bounded-change @ac-04 @slice-02
  Scenario: A bare common-token marker is rejected LOUD at manifest load
    Given a manifest clause whose marker is the bare token "table"
    When the maintainer runs the skill-normative gate through the des dispatcher
    Then the gate verdict is INDETERMINATE with exit code 4
    And the verdict names the offending clause and the marker "table"
