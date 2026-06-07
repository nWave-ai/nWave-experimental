@feature-fix-reverify-p4-tracked-before-fallback @driving_port @real-io @error
@contract-shape:pure-function
Feature: P4 still refuses a slice whose acceptance test is absent or disowned
  As an operator re-verifying an orphaned carpaccio slice
  I want the reverify precondition to keep refusing a slice whose acceptance
  test was never authored, or whose acceptance test the commit modified to
  drop the slice tag
  So that the tracked-before fallback recovers genuine orphans only, and
  never degrades into a blanket accept.

  # The two refusal states share one verdict shape (REFUSE) -- the Scenario
  # Outline parametrize-collapses them. Each row asserts P4 refuses for the
  # right mechanical cause: never-authored (no .feature anywhere) and
  # tag-dropped-by-commit (clause-3 unmodified-by-commit fails).

  @slice-02
  Scenario Outline: A slice whose acceptance test is <presence_state> is refused
    Given a buried slice whose acceptance test is <presence_state>
    When the operator re-verifies the slice
    Then the slice's acceptance-test presence is refused
    And the slice is not recorded as verified in the completion ledger

    Examples:
      | presence_state        |
      | never-authored        |
      | tag-dropped-by-commit |
