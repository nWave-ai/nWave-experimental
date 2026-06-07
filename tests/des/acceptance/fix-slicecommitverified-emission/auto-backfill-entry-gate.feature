@feature-fix-slicecommitverified-emission @slice-01
Feature: The carpaccio entry gate auto-backfills a predecessor's missing verification
  As an nWave operator running an atdd_pure carpaccio hands-off
  I want the carpaccio entry gate, on finding a predecessor slice that was
    committed but never recorded as verified, to verify-and-record that
    predecessor automatically before deciding whether to let the next slice in
  So that a successor slice is no longer blocked out of order just because the
    predecessor's verification record was never emitted -- the manual
    orchestrator backfill becomes an automatic, un-bypassable hook action

  # slice-01 of fix-slicecommitverified-emission -- the auto-backfill happy
  # path (the un-bypassable mechanical layer; the methodology root-cause fix
  # already shipped in 835ff0bf3). Friction anchor:
  # F-CRAFTER-RELIES-ON-SUBAGENTSTOP-FOR-SLICECOMMITVERIFIED.
  #
  # RED scaffold (ADR-028): these ATs FAIL on master for the RIGHT reason --
  # `_carpaccio_order_block` (carpaccio_intercept.py:251) is a PURE READ today:
  # it finds the predecessor NOT in `verified_slices()` and immediately returns
  # `InterceptDecision.block(event="CarpaccioSliceOutOfOrder")`. No
  # `_attempt_predecessor_backfill` branch exists, so the entering slice is
  # BLOCKED (event=CarpaccioSliceOutOfOrder) and no SliceCommitVerified record
  # is appended -- a semantic AssertionError on the `is allowed` /
  # `record appended` Then. They PASS once slice-01 lands the auto-backfill
  # branch: on a predecessor with a commit-on-disk but no SliceCommitVerified,
  # the order check runs the verify-then-record CLI against the predecessor
  # commit and re-reads `verified_slices()` before deciding.
  #
  # HARD INVARIANT (driving-port-only, Mandate-13): the SUT is driven through
  # the production U1 carpaccio PreToolUse intercept
  # (`intercept_atdd_pure_dispatch`) -- the Layer-3 composition driving port,
  # exactly as the shipped atdd_pure_spine_hardening slice-01 ATs drive it. No
  # direct import of the order-block / backfill function at the step boundary.
  # The real git repo + real AtCompletionLedger are the audit SUBSTRATE the
  # hook consumes (seed precondition + read back the record), not the SUT --
  # the adjudicated real-io carve-out for this feature.
  #
  # SUT decision-table (the rows slice-01 pins -- all happy-path):
  #   predecessor COMMITTED_BUT_UNRECORDED -> backfill runs -> record appended -> ALLOW
  #   the appended record is REAL (lands in the ledger, predecessor is the one verified)
  #   predecessor COMMITTED_AND_RECORDED   -> NO re-backfill (idempotent) -> still ALLOW
  # Fail-closed rows (E2 failure / subprocess timeout / missing predecessor
  # commit) are slice-02 scope (see feature-delta [REF] Slice Plan).
  #
  # Driving port: the real `intercept_atdd_pure_dispatch` U1 PreToolUse intercept
  # against a real git repo, a real feature-delta slice plan, and a real
  # AT-completion ledger (Mandate-13 driving-port-only, Layer 3). Example-only,
  # no PBT (Mandate 9/11 -- layer 3 real-io).

  @slice-01 @walking_skeleton @driving_port @real-io @contract-shape:bounded-change
  Scenario: A committed-but-unrecorded predecessor is auto-verified so the next slice enters
    Given a carpaccio feature whose predecessor slice was committed but never recorded as verified
    And the acceptance designer dispatches the next slice into implementation
    When the carpaccio entry gate evaluates the dispatch
    Then the entry gate auto-verifies the predecessor and records it
    And the entry gate allows the next slice in

  @slice-01 @driving_port @real-io @contract-shape:bounded-change
  Scenario: The auto-verification is real and names the predecessor that was committed
    Given a carpaccio feature whose predecessor slice was committed but never recorded as verified
    And the acceptance designer dispatches the next slice into implementation
    When the carpaccio entry gate evaluates the dispatch
    Then exactly one verification record for the predecessor is present in the ledger
    And the predecessor is now recorded as verified

  @slice-01 @driving_port @real-io @contract-shape:bounded-change
  Scenario: An already-verified predecessor is not verified again
    Given a carpaccio feature whose predecessor slice was committed and already recorded as verified
    And the acceptance designer dispatches the next slice into implementation
    When the carpaccio entry gate evaluates the dispatch
    Then no additional verification record for the predecessor is added to the ledger
    And the entry gate allows the next slice in
