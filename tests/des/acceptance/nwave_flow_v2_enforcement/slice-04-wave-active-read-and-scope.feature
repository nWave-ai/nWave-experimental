@feature-nwave-flow-v2-enforcement @slice-04
Feature: The gate scopes enforcement to the active wave without interfering with ad-hoc work
  As an nWave maintainer who trusts the spine to be deterministic
  I want a sub-dispatch that drops its wave markers WHILE a wave is active to be
    denied, while a bare non-wave dispatch is never touched
  So that a wave bypass is made loud (not a silent green) yet my ad-hoc agent
    calls outside a wave run completely uninterrupted

  # slice-04 of nwave-flow-v2-enforcement -- the READ + SCOPE half of the anchor
  # (DESIGN slice-04 code-design: the pre_tool_use_service.py hinge becomes
  # wave-aware). The walking skeleton proves the WRITE (arm the floor); these two
  # scenarios prove the READ side: PreToolUseService reads wave-state through the
  # injected WaveActiveReader and the §95 hinge resolves S1 (allow) vs S2 (deny).
  #
  # DRIVING PORT (Mandate-13 driving-port-only, Layer 3 composition): the REAL
  # PreToolUseService.validate(PreToolUseInput(...)) composition-root service,
  # built via the production composition root (Pillar 3) with a real
  # WaveActiveReader pointed at a real wave-active floor under tmp_path. The
  # service is the SUT; only the wave-active floor (driven-internal port) is
  # arranged as precondition state. The domain VOs (WaveActiveRecord /
  # NoWaveActive) and DesMarkerParser are NEVER imported-and-called at the step
  # boundary -- the assertion is on the service's HookDecision (allow vs block).
  #
  # DORMANT-SEAM RECONCILIATION (D11 / S3): the DESIGN driving-surface declares
  # the WaveActiveReader.read seam threaded INTO the existing PreToolUseService
  # hinge as net-new load-bearing. These scenarios name THAT exact seam (the
  # reader feeding the §95 wave-aware branch) as the port they drive, drive it
  # through the real PreToolUseService.validate entry point, and assert the
  # observable effect (the allow/deny decision differs by wave-active state). The
  # reader-into-service seam is witnessed, not dormant.
  #
  # DECISION TABLE (C5 mode-flag coverage -- read+scope is 2 materially-distinct
  # rows, coupled on the single reader seam):
  #   wave-active ARMED  + child FULLY MARKERLESS -> ALLOW (K2 benign passthrough)
  #   wave-active ARMED  + child has MARKERS -> ALLOW (in-wave child is honoured)
  #   wave-active ABSENT + bare non-wave child -> ALLOW (S1: zero interference)
  # The S1 row is its own scenario below (non-interference invariant).
  #
  # CLASS-1 RETARGET (design-sanctioned, ADR-001 Amendment 2 -- fix-wave-marker-
  # bypass-benign-passthrough): the first row was `markerless -> DENY` before the
  # K2 contract landed. ADR-001 (positive-bypass-signal) deliberately flips a
  # FULLY-MARKERLESS in-wave child under an active floor from DENY to ALLOW
  # (floor-in-the-tree is NOT in-the-wave; a wave-owned child SHOULD carry at least
  # its DES markers). This is NOT silent test-weakening: the markerless->DENY
  # assertion is replaced by the now-correct ALLOW, and the bypass-DENY contract it
  # used to encode is preserved by the slice-01 partial-context ATs of the
  # fix-wave-marker-bypass-benign-passthrough feature (a PARTIAL-context child still
  # DENIES loud). See the ADR-001 Amendment 2 cross-feature retarget table (entry C1).
  #
  # RED-for-right-reason: at HEAD the shipped guard already keys on
  # carries_partial_wave_context (slice-01 of fix-wave-marker-bypass-benign-
  # passthrough), so a fully-markerless child under an active floor ALLOWs -- this
  # retargeted ALLOW assertion is GREEN now. (The marked-child + bare-non-wave rows
  # below stay preservation guards.)

  @slice-04 @driving_port @real-io @coupled @contract-shape:unbounded-preservation
  Scenario: A fully markerless sub-dispatch while the discuss wave is active passes through
    Given the discuss wave is active in the project
    When a sub-dispatch that dropped its wave markers is checked by the gate
    Then the gate allows the markerless sub-dispatch as benign passthrough
    And the gate leaves the markerless sub-dispatch completely untouched

  # PRESERVATION-INVARIANT (AT-review H2): this scenario asserts the marked-child
  # allow() path is NOT regressed -- it does NOT independently witness the
  # WaveActiveReader being invoked. The reader+§95-hinge seam is witnessed by
  # AT-2a's RED->GREEN transition (markerless in-wave -> DENY requires a live
  # reader); making AT-2a GREEN proves the reader is wired for ALL read+scope
  # branches including this one. So this is a regression guard, not a vacuous green.
  @slice-04 @driving_port @real-io @coupled @contract-shape:unbounded-preservation
  Scenario: A sub-dispatch carrying the wave markers while the discuss wave is active is allowed
    Given the discuss wave is active in the project
    When a sub-dispatch carrying the wave markers is checked by the gate
    Then the gate allows the sub-dispatch

  # PRESERVATION-INVARIANT (AT-review H2): S1 non-interference -- pins that a bare
  # non-wave dispatch is never blocked (K2). Like AT-2b, this asserts no-regression,
  # not reader-invocation; the live-reader witness is AT-2a's RED->GREEN.
  @slice-04 @driving_port @real-io @contract-shape:unbounded-preservation
  Scenario: A bare non-wave dispatch is never blocked when no wave is active
    Given no wave is active in the project
    When a bare non-wave dispatch is checked by the gate
    Then the gate allows the dispatch
    And the gate leaves the bare dispatch completely untouched
