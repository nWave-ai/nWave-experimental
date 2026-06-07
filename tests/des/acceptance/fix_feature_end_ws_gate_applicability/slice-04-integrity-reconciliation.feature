@feature-fix-feature-end-ws-gate-applicability @slice-04 @coupled @real-io @contract-shape:bounded-change
Feature: The done-gate accepts a not-applicable record in place of a verified one, yet still catches a silently skipped check

  An operator who has run the feature-end cycle on a feature whose checks were not
  applicable wants the done-gate to certify the feature complete -- the not-applicable
  records the cycle left behind must reconcile the same checks a verified record
  would. But the operator equally wants the done-gate to keep catching a check that
  was silently skipped, leaving neither a verified record nor a not-applicable one --
  the not-applicable mechanism must not become a hole through which a missing check
  slips by.

  The done-gate stays honest by accepting, for each applicable check, either its
  verified record OR its not-applicable record -- and nothing else. A check that
  left a not-applicable record reconciles. A check that left neither is still named
  as missing and the feature is still blocked from being certified complete.

  # Driving port (Mandate-13, Layer 3 subprocess): the real `des feature-end run`
  # command (the cycle that mints the records) followed by the real
  # `des verify-integrity` command (the done-gate that reconciles them), both
  # invoked end-to-end over the real `des` single entry point as subprocesses. The
  # observable is the done-gate's reconcile/incomplete verdict and the set of
  # records it names as missing -- read back from the command output, not the SUT.
  # No production module is imported and called at the step boundary (S2
  # driving-port-only boundary holds). The cycle mints every record itself through
  # its production writer, so the records are genuine, never hand-seeded.

  @reconciliation @slice-04 @coupled
  Scenario: A feature whose checks were not applicable has those checks reconciled by the done-gate
    Given a feature whose real-environment and coverage checks were both not applicable
    When the operator runs the done-gate on that feature
    Then the done-gate does not name the real-environment check among the missing records
    And the done-gate does not name the coverage check among the missing records

  @reconciliation @anti-vacuity @slice-04 @coupled
  Scenario: A check that left neither a verified nor a not-applicable record is still caught as missing
    Given a feature whose coverage check left neither a verified nor a not-applicable record
    When the operator runs the done-gate on that feature
    Then the done-gate reports the feature-end cycle as incomplete
    And the done-gate names the coverage check among the missing records
