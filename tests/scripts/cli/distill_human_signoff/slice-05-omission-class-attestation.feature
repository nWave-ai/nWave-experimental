@feature-fix-distill-human-signoff
Feature: The signoff attests against every named omission class, cardinality-agnostic and non-empty

  The omission classes are the finer attestation checklist the human signs
  against — a versioned list imported verbatim from the sister-tree single
  source of truth. The verify gate asserts the signoff block attests every
  class identifier present in the imported list — N classes, not a hard-
  coded count. Adding a class to the imported list raises the attestation
  surface with no gate code change; an empty or unparseable list is refused
  fail-closed as malformed, never silently passed as a vacuous attestation.

  # Driving port: verify_coverage_map verify (omission-class branch). Layer 3
  # (subprocess / FS acceptance) -- example-only sad paths (Mandate 11). The
  # @property-tagged AT3 outline enumerates the cardinality-agnostic surface
  # and the non-empty floor.

  Background:
    Given a feature whose design wave has produced a component manifest
    And a coverage map has been authored and signed by a human

  @slice-05 @driving_port @error @contract-shape:bounded-change
  Scenario: A signoff that omits an attested omission class is refused
    Given the imported omission class list names a class the signoff did not attest
    When the reviewer verifies the coverage map
    Then the verify gate refuses for a missing signoff

  @slice-05 @driving_port @contract-shape:pure-function
  Scenario: Changing the content of an omission class in the imported list propagates without a gate code change
    Given the imported omission class list has its content edited for one class
    When the reviewer verifies the coverage map
    Then the verify gate consults the imported list and produces a verdict consistent with the edited content
    And no gate code was changed between the unedited and edited verifications

  @slice-05 @property @driving_port @contract-shape:pure-function
  Scenario Outline: The attestation is cardinality-agnostic and refuses an empty or unparseable list
    Given the imported omission class list is <list_shape>
    When the reviewer verifies the coverage map
    Then the verify gate responds with <verdict>

    Examples:
      | list_shape                                | verdict                                          |
      | a list of five named classes              | the verify gate accepts the coverage map         |
      | a list of seven named classes             | the verify gate accepts the coverage map         |
      | an empty list with zero entries           | the verify gate refuses for a malformed input    |
      | a list that cannot be parsed              | the verify gate refuses for a malformed input    |
