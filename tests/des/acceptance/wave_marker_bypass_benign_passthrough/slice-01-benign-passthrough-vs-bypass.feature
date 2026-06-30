@feature-fix-wave-marker-bypass-benign-passthrough @slice-01
Feature: A benign markerless prompt passes through under an active floor while a real bypass is still blocked
  As an nWave maintainer running concurrent wave and non-wave work
  I want a benign, markerless prompt to pass through untouched while a wave floor
    is armed in my working tree
  So that my non-wave work is never blocked by a co-located wave, while a genuine
    in-wave child that drops its required markers is still blocked loud

  # slice-01 of fix-wave-marker-bypass-benign-passthrough -- the CORRECTED guard
  # (ADR-001). The S2 WAVE_MARKER_BYPASS guard is re-pointed from the floor-presence
  # predicate (markers.wave is not None and not has_des_markers) to the POSITIVE
  # bypass-signal predicate (carries_partial_wave_context): BLOCK only on positive
  # evidence of a wave-owned child that dropped its required marker; ALLOW a fully
  # markerless dispatch.
  #
  # DRIVING PORT (Mandate-13 driving-port-only, Layer 3 composition): the REAL
  # PreToolUseService.validate(PreToolUseInput(...)) composition-root service, built
  # via the production composition root (Pillar 3, service_factory). The service is
  # the SUT; only the wave-active floor (a driven-internal filesystem port) is
  # arranged. The assertion is on the service's HookDecision (allow vs block) -- the
  # exact observable a Claude Code hook translates to exit 0 / exit 2.
  #
  # FLOOR ISOLATION (Fix-2): every scenario injects its floor state EXPLICITLY into a
  # clean tmp root and drives the service under that root's CWD, so the production
  # WaveActiveReader reads the INJECTED floor -- never the developer's live
  # .nwave/wave-active/active.json. Each scenario asserts the hook's INTRINSIC
  # decision for a CONTROLLED floor, independent of the working tree. (The test-arrange
  # ISOLATION INVARIANT itself, AT-7, is hardened in slice-02.)
  #
  # DECISION TABLE (the corrected guard, under an active floor unless stated):
  #   ARMED  + fully markerless          -> ALLOW (K2 benign passthrough)  [AT-1]
  #   ARMED  + partial markers (no -VAL) -> BLOCK (K1 bypass loud)         [AT-2]
  #   ARMED  + DES-WAVE only (no -VAL)   -> BLOCK (collision closed)       [AT-3]
  #   NO floor + markerless              -> ALLOW (S1 ad-hoc, unchanged)   [AT-4]
  #   ARMED  + wave_entering             -> ALLOW (entering, unchanged)    [AT-5]
  #
  # RED-for-right-reason (at HEAD the OLD floor-presence guard is live):
  #   AT-1 -- old guard BLOCKS a markerless prompt under a floor where the corrected
  #     guard must ALLOW -> the ALLOW assertion fails with a semantic AssertionError.
  #   AT-2 -- has_des_markers is True for partial markers, so the OLD guard does NOT
  #     block where the corrected guard must BLOCK -> the BLOCK assertion fails RED.
  #   AT-3/AT-4/AT-5 -- preservation-GREEN at HEAD; they pin that the DES-WAVE
  #     collision stays closed, S1 stays untouched, and the entering exemption holds
  #     end-to-end through DELIVER (regression guards, not vacuous greens).

  @slice-01 @walking_skeleton @driving_port @real-io @contract-shape:bounded-change
  Scenario: A benign markerless prompt passes through while the design wave is active
    Given a design wave floor is armed in an isolated project
    When a fully markerless prompt is checked by the gate
    Then the gate allows the dispatch
    And the gate leaves the benign dispatch completely untouched

  @slice-01 @walking_skeleton @driving_port @real-io @contract-shape:bounded-change
  Scenario: A partial-context in-wave child missing its required marker is blocked loud
    Given a design wave floor is armed in an isolated project
    When an in-wave child carrying partial wave context but missing its required marker is checked by the gate
    Then the gate blocks the dispatch
    And the block names the wave-bypass so it cannot pass as a silent success

  @slice-01 @driving_port @real-io @contract-shape:bounded-change
  Scenario: A DES-WAVE-only child is still blocked because the wave declaration is partial context
    Given a design wave floor is armed in an isolated project
    When a child carrying only a wave declaration but missing its required marker is checked by the gate
    Then the gate blocks the dispatch
    And the block names the wave-bypass so it cannot pass as a silent success

  @slice-01 @driving_port @real-io @contract-shape:bounded-change
  Scenario: A markerless prompt with no wave active is allowed unchanged
    Given no wave floor is armed in an isolated project
    When a fully markerless prompt is checked by the gate
    Then the gate allows the dispatch
    And the gate leaves the benign dispatch completely untouched

  @slice-01 @driving_port @real-io @contract-shape:bounded-change
  Scenario: A wave-entering dispatch is allowed even with partial markers
    Given a design wave floor is armed in an isolated project
    And the dispatch is the wave-entering dispatch
    When an in-wave child carrying partial wave context but missing its required marker is checked by the gate
    Then the gate allows the dispatch
