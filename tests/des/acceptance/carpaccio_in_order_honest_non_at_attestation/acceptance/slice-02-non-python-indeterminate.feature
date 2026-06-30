@feature-carpaccio-in-order-honest-non-at-attestation
Feature: A non-Python target's slice chain un-wedges on a degrade

  A beta-tester (Raj) drives `des commit-slice` on a non-Python target (Rust /
  Go) where no pytest interpreter resolves. Today the committed-scope digest
  step degrades LOUD (InterpreterUnavailable) and `commit-slice` lands the
  commit with its trailers but appends NO ledger record -- so the successor
  slice wedges ("predecessor has no SliceCommitVerified record"). slice-02
  routes that degrade path to MINT the EXISTING SliceCommitIndeterminate record
  (with an honest free-text reason), which the in-order gate already accepts, so
  the chain progresses instead of wedging. The degrade is never silent, and a
  fabricated SliceCommitVerified is NEVER written (US-03).

  # CODE slice (not the walking skeleton) -- Layer 3 composition, in-process:
  # drives the production `des commit-slice` argv `main` over a real git repo +
  # real AtCompletionLedger on tmp_path, with the committed-scope digest value
  # forced to its InterpreterUnavailable refusal (the non-Python-target degrade).
  # Driving ports: the production `des commit-slice` CLI (mint) + the production
  # `evaluate_atdd_pure_dispatch` live hook (gate-accept). @in-memory tag is NOT
  # used -- the ledger I/O is real (@real-io).

  @slice-02 @driving_port @real-io @US-03 @contract-shape:bounded-change
  Scenario: A degraded commit-slice mints an indeterminate record so the successor proceeds
    Given a committed predecessor slice on a non-Python target where the interpreter is unavailable
    And the successor slice is wedged because the predecessor carries no honest record
    When the operator commits the predecessor slice with des commit-slice
    And the operator dispatches the successor slice into delivery
    Then the in-order gate accepts the indeterminate predecessor and the successor proceeds

  @slice-02 @driving_port @real-io @US-03 @contract-shape:bounded-change
  Scenario: The degraded commit-slice lands the commit and records the degrade loudly
    Given a committed predecessor slice on a non-Python target where the interpreter is unavailable
    When the operator commits the predecessor slice with des commit-slice
    Then the predecessor commit lands carrying its slice trailers
    And the ledger carries one indeterminate record naming the degrade reason

  @slice-02 @driving_port @real-io @US-03 @error @contract-shape:bounded-change
  Scenario: The degraded commit-slice never fabricates a verified record
    Given a committed predecessor slice on a non-Python target where the interpreter is unavailable
    When the operator commits the predecessor slice with des commit-slice
    Then the ledger carries no fabricated verified record for the degraded predecessor
    And the indeterminate record is honest with no real gate-scope digest
