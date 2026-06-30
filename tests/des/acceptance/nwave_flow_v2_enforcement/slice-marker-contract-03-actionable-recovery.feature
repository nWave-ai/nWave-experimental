@feature-fix-wave-dispatch-marker-contract @slice-03
Feature: A genuine wave-bypass veto names the fix path it demands
  As an nWave operator whose dispatch was denied as a wave bypass
  I want the WAVE_MARKER_BYPASS block to tell me exactly how to fix it
  So that every veto surface is self-documenting -- matching the enforcement and
    completeness blocks that already carry recovery hints -- while a recognized
    wave-entry never carries spurious recovery state

  # slice-03 of fix-wave-dispatch-marker-contract (depends-on slice-01, RCA R-A1:
  # a hint on a false-positive block is politely wrong, so the relax must land
  # first). Root Cause C: the :159 WAVE_MARKER_BYPASS block emits no
  # recovery_suggestions, unlike its twins at :140 / :173. Additive: a
  # recovery_suggestions arg on an existing block (no new behaviour beyond the
  # hint text).
  #
  # DRIVING PORT (Mandate-13, Layer 3 composition): the REAL
  # PreToolUseService.validate via the production composition root; observable =
  # HookDecision.recovery_suggestions (alongside action + reason).
  #
  # RED-for-right-reason (active-RED scaffold, atdd_pure -- NOT @skip):
  #   AT-3a -- the :159 block passes no recovery_suggestions at HEAD, so the
  #     observable list is EMPTY where a non-empty actionable hint is expected
  #     (semantic AssertionError). GREEN once DELIVER mirrors the :140/:173 twins.
  #   AT-3b -- the no-leak invariant presupposes the slice-01 ALLOW path; until
  #     slice-01 ships, the entry is a BLOCK and AT-3b fires RED (correct -- the
  #     allow it asserts about does not yet exist). Post both slices: ALLOW with
  #     empty recovery_suggestions (no leakage).
  # No @skip, no import / collection / setup error.
  #
  # SUT STATE MACHINE (C2): see composition_slice_marker_contract_03.py --
  #   {MARKERLESS_CHILD(non-entering), WAVE_ENTERING(DES_WAVE_ONLY)} with
  #   blocked-child-carries-recovery / allowed-entry-carries-no-recovery.

  # AT-3a -- recovery present on a genuine bypass (the block names the fix path).
  #
  # CLASS-1 RE-EXPRESS (design-sanctioned, ADR-001 Amendment 2 -- fix-wave-marker-
  # bypass-benign-passthrough). The recovery-message contract's INTENT (a denied
  # bypass names its fix path) is preserved; only the TRIGGER is re-expressed from
  # fully-markerless to PARTIAL-context (a DES-* subset, no DES-VALIDATION). The K2
  # contract now ALLOWs a fully-markerless child (no BLOCK -> no recovery), so the
  # trigger is a partial-context child that STILL BLOCKs and still carries recovery.
  # The recovery contract is preserved, not weakened. See ADR-001 Amendment 2
  # retarget table (entry C3).
  @slice-03 @driving_port @real-io @us-actionable-recovery @error @contract-shape:bounded-change
  Scenario: A denied partial-context child is told how to fix the bypass
    Given the design wave is active and a partial-context non-entering child arrives for recovery
    When the partial-context in-wave child dispatch is checked for recovery
    Then the bypass block names an actionable recovery fix

  # AT-3b -- no recovery leakage onto the allow path (the recognized entry is clean).
  @slice-03 @driving_port @real-io @us-actionable-recovery @contract-shape:unbounded-preservation
  Scenario: A recognized wave-entry carries no recovery state
    Given the design wave is active and this dispatch is entering for recovery
    When the recognized entry dispatch is checked for recovery
    Then the allowed entry carries no recovery state
