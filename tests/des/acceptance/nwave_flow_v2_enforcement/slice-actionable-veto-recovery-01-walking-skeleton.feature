@feature-fix-actionable-veto-recovery @slice-01
Feature: Every spine veto tells a blocked dispatch how to fix it
  As an LLM whose Task dispatch is vetoed by the nWave spine
  I want every veto block to name the concrete fix on the SAME block
  So that I learn-by-doing how to repair the dispatch instead of staying
    suspended on a bare error code -- matching the enforcement / completeness /
    wave-bypass blocks that already carry recovery hints

  # slice-01 of fix-actionable-veto-recovery (walking skeleton, JOB-019). At HEAD
  # six spine veto sites call HookDecision.block(reason=...) WITHOUT
  # recovery_suggestions, leaving a blocked LLM stuck. Additive fix: a
  # recovery_suggestions arg on each existing block (no behaviour beyond the hint
  # text), mirroring the shipped fix-wave-dispatch-marker-contract slice-03 pattern.
  #
  # DRIVING SURFACE (Mandate-13, Layer 3 composition): the REAL spine services via
  # the production composition root --
  #   * 5 sites -> PreToolUseService.validate (service_factory.create_pre_tool_use_service)
  #   * 1 site  -> SubagentStopService.validate (service_factory.create_subagent_stop_service)
  # observable = HookDecision.recovery_suggestions (alongside action + reason).
  # The scenario drives on the SEAM / error-code (the VetoSite enum value), never
  # a line number.
  #
  # The 6 bare-veto SITES (error-code each veto's reason carries at HEAD):
  #   WAVE_ACTIVE_INDETERMINATE    -- corrupt wave-active floor
  #   CLASSIC_PROMPT_INVALID       -- classic dispatch missing mandatory sections
  #   ATDD_PURE_DISPATCH_DEFECTIVE -- atdd_pure markers incoherent (phase XOR scope)
  #   ATDD_PURE_PROMPT_INVALID     -- valid atdd_pure markers, missing sections
  #   DISCUSS_GATE_IN              -- discuss entry, product SSOT present but incomplete
  #                                   (MISSING_SSOT; the MIGRATION_UNMET case is now a
  #                                    slice-05 soft advisory, no longer a veto)
  #   DISCUSS_GATE_OUT             -- discuss return, slice plan rejected
  #
  # RED-for-right-reason (active-RED scaffold, atdd_pure -- NOT @skip): at HEAD
  # each of the 6 blocks passes no recovery_suggestions, so the observed list is
  # EMPTY where a non-empty actionable hint is expected (semantic AssertionError).
  # GREEN once DELIVER adds a recovery_suggestions= arg to each of the 6 blocks.
  # No @skip, no import / collection / setup error.
  #
  # SUT STATE MACHINE (C2): see composition_actionable_veto_recovery.py --
  #   each VetoSite arms a precondition that steers the REAL service down exactly
  #   that veto's BLOCK branch; every branch must reach
  #   BLOCK + non-empty actionable recovery_suggestions (self-documenting surface).

  @slice-01 @walking_skeleton @driving_port @real-io @us-actionable-recovery @error @contract-shape:bounded-change
  Scenario Outline: A vetoed dispatch is told how to fix the <site> block
    Given the spine is armed for the <site> veto
    When the vetoed dispatch is checked for recovery
    Then the <site> veto still blocks the dispatch
    And the block carries a non-empty recovery list
    And the recovery names the fix specific to the <site> veto

    Examples:
      | site                         |
      | WAVE_ACTIVE_INDETERMINATE    |
      | CLASSIC_PROMPT_INVALID       |
      | ATDD_PURE_DISPATCH_DEFECTIVE |
      | ATDD_PURE_PROMPT_INVALID     |
      | DISCUSS_GATE_IN              |
      | DISCUSS_GATE_OUT             |
