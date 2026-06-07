@feature-fix-slicecommitverified-emission @slice-02
Feature: The carpaccio entry gate refuses to backfill on bad or missing evidence
  As an nWave operator running an atdd_pure carpaccio hands-off
  I want the carpaccio entry gate's auto-backfill to refuse a predecessor whose
    commit evidence is absent, stale/forged, or missing entirely, leaving the
    out-of-order block standing and recording no verification
  So that a successor slice is never let in on the strength of evidence the
    predecessor never honestly produced -- the auto-backfill closes the
    out-of-order gap WITHOUT opening a false-allow hole

  # slice-02 of fix-slicecommitverified-emission -- the auto-backfill
  # FAIL-CLOSED rows (the anti-false-allow safety witness). slice-01 (happy
  # path) shipped the backfill in c995b66dd; this slice WITNESSES that the
  # shipped backfill is fail-closed BY CONSTRUCTION on bad/missing E2-evidence.
  # Friction anchor: F-CRAFTER-RELIES-ON-SUBAGENTSTOP-FOR-SLICECOMMITVERIFIED.
  #
  # The anti-false-allow KEYSTONE (HARD invariant): every scenario asserts BOTH
  #   (a) the entering slice is BLOCKED (out of order, not allowed), AND
  #   (b) NO SliceCommitVerified record was appended for the predecessor (the
  #       on-disk ledger count for the predecessor stays 0).
  # A gate that false-allowed on bad evidence would fail (b). This is the
  # adversarial safety property -- the load-bearing reason the backfill VERIFIES
  # the predecessor's digest (recompute + compare) rather than trusting a
  # trailer the crafter could fabricate.
  #
  # PROBE RESULT (DISTILL, against shipped c995b66dd): these ATs are
  # GREEN-REGRESSION-PINS, not RED-new. The shipped `_attempt_predecessor_backfill`
  # (carpaccio_intercept.py:381) is fail-closed by construction --
  #   * Gate-Scope absent / stale -> `_verify_gate_scope` returns False -> no record
  #   * no predecessor commit on disk -> `_predecessor_commit_sha` returns None -> no record
  # so the block stands and no record is appended for all three rows. They pin
  # the existing safety against regression (like slice-01's AT-3 idempotent pin).
  # Authored skip-scaffolded per ADR-028; on unskip they GREEN against shipped code.
  #
  # SUT decision-table (the rows slice-02 pins -- all FAIL-CLOSED, all no-false-allow):
  #   predecessor committed, Gate-Scope ABSENT   -> GateScopeUnverified(absent)   -> BLOCK STANDS, no record
  #   predecessor committed, Gate-Scope STALE    -> GateScopeUnverified(mismatch) -> BLOCK STANDS, no record  [anti-RCA-Branch-B]
  #   predecessor NOT committed on disk          -> backfill cannot run           -> BLOCK STANDS, no record
  # (Subprocess-timeout is the remaining fail-closed row -- noted as owned
  # residue, not authored: it cannot be witnessed deterministically without a
  # flaky timeout fixture. See feature-delta [REF] Slice Plan + DISTILL gaps.)
  #
  # HARD INVARIANT (driving-port-only, Mandate-13): the SUT is driven through
  # the production U1 carpaccio PreToolUse intercept (`intercept_atdd_pure_dispatch`)
  # -- the Layer-3 composition driving port, exactly as slice-01. No direct
  # import of the order-block / backfill function at the step boundary. The real
  # git repo + real AtCompletionLedger are the audit SUBSTRATE the hook consumes
  # (seed precondition + read back the record), not the SUT.
  #
  # Driving port: the real `intercept_atdd_pure_dispatch` U1 PreToolUse intercept
  # against a real git repo, a real feature-delta slice plan, and a real
  # AT-completion ledger (Mandate-13 driving-port-only, Layer 3). Example-only,
  # no PBT (Mandate 9/11 -- layer 3 real-io).

  @slice-02 @driving_port @real-io @contract-shape:unbounded-preservation
  Scenario: A predecessor with no recorded gate scope is refused and the block stands
    Given a carpaccio feature whose predecessor slice was committed without a recorded gate scope
    And the next carpaccio slice is dispatched into implementation for the fail-closed gate
    When the fail-closed carpaccio entry gate evaluates the dispatch
    Then the entry gate refuses to verify the predecessor
    And no verification record for the predecessor is present in the ledger
    And the entry gate keeps the next slice blocked out of order

  @slice-02 @driving_port @real-io @contract-shape:unbounded-preservation
  Scenario: A predecessor with a stale recorded gate scope is refused and the block stands
    Given a carpaccio feature whose predecessor slice was committed with a stale recorded gate scope
    And the next carpaccio slice is dispatched into implementation for the fail-closed gate
    When the fail-closed carpaccio entry gate evaluates the dispatch
    Then the entry gate refuses to verify the predecessor
    And no verification record for the predecessor is present in the ledger
    And the entry gate keeps the next slice blocked out of order

  @slice-02 @driving_port @real-io @contract-shape:unbounded-preservation
  Scenario: A predecessor that was never committed is refused and the block stands
    Given a carpaccio feature whose predecessor slice was never committed
    And the next carpaccio slice is dispatched into implementation for the fail-closed gate
    When the fail-closed carpaccio entry gate evaluates the dispatch
    Then the entry gate refuses to verify the predecessor
    And no verification record for the predecessor is present in the ledger
    And the entry gate keeps the next slice blocked out of order
