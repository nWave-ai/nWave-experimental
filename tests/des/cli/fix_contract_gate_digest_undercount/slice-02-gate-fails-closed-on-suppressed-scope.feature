@feature-fix-contract-gate-digest-undercount
Feature: Contract gate fails closed when the collected scope is suppressed

  The `des run-contract-gate` exit gate must refuse to produce a verdict when a
  tree presents a populated suite at collection time but suppresses every
  per-test identity before the scope is fingerprinted. Such a tree must fail the
  gate closed -- it must never be accepted as if it were genuinely empty. An
  honest tree must still let the gate reach a verdict on the same exit-gate path.

  @slice-02 @real-io @contract-shape:unbounded-preservation
  Scenario: The gate fails closed for a tree that suppresses its collected scope
    # The lying tree: a populated suite is collected, then its per-test
    # identities are emptied before the scope is fingerprinted. Driven through
    # the real CLI subprocess on the exit-gate (verify) path the commit gate
    # actually runs -- NOT only --print-digest (Mandate-13).
    Given the contract gate is asked to verify a tree that suppresses its collected scope
    When the operator verifies the gate scope through the commit gate
    Then the contract gate fails closed

  @slice-02 @real-io @contract-shape:unbounded-preservation
  Scenario: The gate reaches a verdict for an honest tree on the same path
    # Regression pin: the honest tree must keep reaching a verdict on the
    # exit-gate (verify) path -- the fail-closed guard must not red the honest
    # commit gate.
    Given the contract gate is asked to verify a tree with an honest collected scope
    When the operator verifies the gate scope through the commit gate
    Then the contract gate reaches a verdict
