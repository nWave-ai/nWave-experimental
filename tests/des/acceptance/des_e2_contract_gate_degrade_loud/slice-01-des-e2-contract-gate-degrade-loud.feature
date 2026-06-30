@feature-fix-des-e2-contract-gate-degrade-loud
Feature: E2 contract gate degrades LOUD on interpreter absence

  A non-Python target whose contract gate has no usable interpreter must not
  hard-block the carpaccio spine. The gate degrades LOUD to an honest
  INDETERMINATE-and-proceed, verify-slice-commit records that honest outcome
  (never a fabricated pass), and the in-order guard accepts the INDETERMINATE
  predecessor so the next slice dispatches -- while a Python target with a
  usable interpreter still earns a genuine verified record.

  @slice-01 @real-io @contract-shape:bounded-change
  Scenario: Contract gate degrades loud instead of hard-refusing when no interpreter is available
    Given a target whose contract gate cannot resolve a usable interpreter
    When the contract gate runs for the slice
    Then the contract gate reports an indeterminate outcome
    And the contract gate does not hard-refuse the slice

  @slice-01 @real-io @contract-shape:bounded-change
  Scenario: Verify-slice-commit records an honest indeterminate result instead of a fabricated pass
    Given a target whose contract gate cannot resolve a usable interpreter
    When verify-slice-commit runs the exit gate for the slice
    Then the completion ledger gains an indeterminate slice-commit record
    And the completion ledger gains no verified slice-commit record

  @slice-01 @real-io @contract-shape:bounded-change
  Scenario: The in-order guard accepts an indeterminate predecessor so the next slice dispatches
    Given the predecessor slice carries an indeterminate slice-commit record
    When the next carpaccio slice is dispatched into implementation
    Then the carpaccio in-order guard clears the next slice to enter

  @slice-01 @real-io @contract-shape:unbounded-preservation
  Scenario: A Python target with a usable interpreter still earns a genuine verified record
    Given a target whose contract gate can resolve a usable interpreter
    When verify-slice-commit runs the exit gate for the slice with the gate passing
    Then the completion ledger gains a verified slice-commit record
    And verify-slice-commit reports success
