@feature-fix-wave-dispatch-marker-contract @slice-01
Feature: A wave-entering DES-WAVE-only dispatch is recognized, not bypass-blocked
  As an nWave maintainer running any wave through its command template
  I want a wave-ENTERING dispatch that carries only its DES-WAVE marker -- the
    exact shape the DISCUSS/DESIGN/DEVOPS/DISTILL templates ship -- to be
    RECOGNIZED as a legitimate entry and proceed
  So that the slice-04 markerless-bypass veto stops false-positive-blocking the
    minimal dispatch every command template emits, while a genuinely markerless
    in-wave child is still DENIED loud

  # slice-01 of fix-wave-dispatch-marker-contract -- @walking-skeleton (Root
  # Cause A, the enforcement fix). Relaxes the pre_tool_use_service.py:146 veto
  # to EXEMPT input_data.wave_entering=True; preserves the S2 DENY for a
  # non-entering markerless child (wave_entering=False). Reuses the existing
  # PreToolUseInput.wave_entering signal (no new port / wiring).
  #
  # DRIVING PORT (Mandate-13 driving-port-only, Layer 3 composition): the REAL
  # PreToolUseService.validate built via the production composition root
  # (service_factory.create_pre_tool_use_service) over a tmp project_root with a
  # real WaveActiveReader floor. The service IS the SUT; observable = the
  # HookDecision (allow vs block + the WAVE_MARKER_BYPASS reason). No
  # direct-domain import at the step boundary.
  #
  # RED-for-right-reason (active-RED scaffold, ADR-025 + ADR-028, atdd_pure --
  # NOT @skip): the wave_entering exemption does NOT exist at HEAD, so the :146
  # veto keys on has_des_markers alone (DES-WAVE is excluded from
  # _DES_MARKER_KEY) and FIRES on the DES-WAVE-only entering dispatch -> the
  # service BLOCKS WAVE_MARKER_BYPASS where AT-1a/1b expect ALLOW (semantic
  # AssertionError, never a collection / import / setup error). AT-1c is
  # PRESERVATION-GREEN at HEAD and stays GREEN post-fix (the deletion-mutation
  # guard R-A2). GREEN once DELIVER ships the exemption.
  #
  # SUT STATE MACHINE (C2): see composition_slice_marker_contract_01.py --
  #   {WAVE_ENTERING(DES_WAVE_ONLY), MARKERLESS_CHILD(non-entering)} with
  #   entering-dispatch-exempt-from-veto / markerless-non-entering-child-denied
  #   transitions, keyed on input_data.wave_entering (never prompt wording --
  #   F3 NORMATIVO).

  # AT-1a (design) + AT-1b (discuss) -- the bug, end-to-end, wave-generic
  # (RCA E7: the veto fires for every wave). discuss additionally proves the
  # gate-IN (:122-129) fall-through is SAFE post-fix (feature-delta §Code-Design
  # "DISCUSS gate-IN fall-through"): the SSOT preconditions are satisfied so the
  # gate-IN PASSES and falls through to the :146 veto under test.
  @slice-01 @walking-skeleton @driving_port @real-io @us-relax-false-positive @contract-shape:bounded-change
  Scenario Outline: A wave-entering DES-WAVE-only dispatch is recognized for <wave>
    Given the <wave> wave is active and this dispatch is entering it
    When a DES-WAVE-only entering dispatch is checked
    Then the entering dispatch is recognized and allowed
    And the allow decision carries no bypass veto

    Examples:
      | wave    |
      | design  |
      | discuss |

  # AT-1c -- S2 preserved: the veto STILL bites a PARTIAL-context NON-entering
  # in-wave child (wave_entering=False). This is the deletion-mutation guard
  # (R-A2): a mutation gutting the wave_entering exemption turns AT-1a/1b RED
  # while this stays GREEN.
  #
  # CLASS-1 RE-EXPRESS (design-sanctioned, ADR-001 Amendment 2 -- fix-wave-marker-
  # bypass-benign-passthrough). The R-A2 guard's INTENT (a non-entering in-wave
  # child still DENIED loud) is preserved; only the TRIGGER is re-expressed from
  # fully-markerless to PARTIAL-context (a DES-* subset, no DES-VALIDATION). The K2
  # contract now ALLOWs a fully-markerless child, so a markerless trigger would no
  # longer BLOCK; a partial-context child is a positively-identified bypass that
  # STILL DENIES loud. The BLOCK contract is preserved, not weakened. See ADR-001
  # Amendment 2 retarget table (entry C2).
  @slice-01 @driving_port @real-io @us-relax-false-positive @error @contract-shape:unbounded-preservation
  Scenario: A partial-context non-entering in-wave child is still denied loud
    Given the design wave is active and a partial-context non-entering child arrives
    When a partial-context in-wave child dispatch is checked
    Then the partial-context child dispatch is denied as a wave bypass
