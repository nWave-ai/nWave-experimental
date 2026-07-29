@feature-fix-wave-bypass-recovery-truthful @slice-01
Feature: A wave-bypass veto tells a blocked dispatch how to truly get unblocked
  As an LLM whose Task dispatch is vetoed by the wave-bypass spine veto
  I want every recovery item to be followable-to-unblock -- no add-DES-WAVE loop
  So that I repair the dispatch and proceed, instead of looping on a hint that
    does nothing, or staying suspended on a stale wave I am not even in

  # slice-01 of fix-wave-bypass-recovery-truthful (walking skeleton, JOB-019,
  # OB-A=A2). At HEAD the WAVE_MARKER_BYPASS recovery list has TWO items; the
  # second is UNTRUTHFUL: "ensure <!-- DES-WAVE: <wave> --> is present so it is
  # recognized as a legitimate wave-entering dispatch." Following it does NOTHING
  # -- DES-WAVE is excluded from _DES_MARKER_KEY (has_des_markers stays False) and
  # wave_entering is floor-state never set by the prompt -- so the LLM loops.
  #
  # Additive bounded-change fix (DESIGN SHAPE slice-01): replace the untruthful
  # second item with a stale-floor clear hint naming `des wave-clear` (landed by
  # slice-02). The veto STILL blocks; only the hint text changes.
  #
  # DRIVING SURFACE (Mandate-13, Layer 3 composition): the REAL spine service via
  # the production composition root --
  #   PreToolUseService.validate (service_factory.create_pre_tool_use_service).
  # observable = HookDecision.recovery_suggestions (alongside action + reason).
  # The scenario drives on the SEAM / error-code (WAVE_MARKER_BYPASS), never a
  # line number.
  #
  # ARMED PRECONDITION (the empirically-hit case): a STALE, days-old
  # {"wave":"distill","provenance":"inferred"} floor + a PARTIAL-context
  # sub-dispatch (a DES-* subset, no DES-VALIDATION) + wave_entering=False -> the
  # REAL service takes the WAVE_MARKER_BYPASS branch.
  #
  # CLASS-1 RE-EXPRESS (design-sanctioned, ADR-001 Amendment 2 -- fix-wave-marker-
  # bypass-benign-passthrough). The JOB-019 truthful/followable recovery oracle's
  # INTENT is preserved VERBATIM; only the TRIGGER is re-expressed from fully-
  # markerless to PARTIAL-context. The K2 contract now ALLOWs a fully-markerless
  # dispatch, so a markerless trigger would no longer fire the veto (no recovery to
  # inspect); a partial-context dispatch STILL fires WAVE_MARKER_BYPASS, so the
  # deny-preserved / item-1-followable / item-2-`des wave-clear` / no-phantom
  # oracle is unchanged. See ADR-001 Amendment 2 retarget table (entry C4).
  #
  # ORACLE (tightened per DESIGN SHAPE invariants -- NOT a loose "names a fix"):
  #   * deny preserved -- the veto STILL blocks, reason still WAVE_MARKER_BYPASS.
  #   * item 1 followable -- names a real _DES_MARKER_KEY marker AND a prompt
  #     carrying it (through the REAL parser) yields has_des_markers=True.
  #   * item 2 followable -- names literal `des wave-clear` AND clearing the floor
  #     yields markers.wave is None on the next REAL read.
  #   * NO phantom -- no item proposes the verified-impossible "make this
  #     wave-entering via the prompt" action.
  #
  # RED-for-right-reason (active-RED scaffold, atdd_pure -- NOT @skip): at HEAD the
  # second item is the DES-WAVE-only loop item, so the followable-item-2 and
  # no-phantom assertions fire a semantic AssertionError. GREEN once DELIVER lands
  # the A2 stale-floor clear hint. No @skip, no import / collection / setup error.

  @slice-01 @walking_skeleton @driving_port @real-io @us-truthful-recovery @error @contract-shape:bounded-change
  Scenario: A wave-bypass veto names a recovery a blocked LLM can actually follow
    Given a stale declared wave floor the dispatch is not entering
    When a partial-context in-wave dispatch is vetoed for the bypass
    Then the wave-bypass veto still blocks the dispatch
    And the block reason still names the wave-bypass error
    And the first recovery item carries the wave's real markers
    And the second recovery item names the sanctioned wave-clear command
    And no recovery item proposes the phantom wave-entry action
