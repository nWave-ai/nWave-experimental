@feature-fix-wave-marker-bypass-benign-passthrough @slice-03
Feature: A plain-line DES-VALIDATION dispatch is recognized, not false-positive-blocked
  As an nWave maintainer dispatching an in-wave sub-task that carries its required
    marker in the plain-line spelling (not only the HTML-comment form)
  I want that legitimate complete dispatch to pass the wave-bypass guard untouched
  So that a sub-dispatch carrying DES-VALIDATION in EITHER spelling is honoured,
    while a dispatch carrying NEITHER form (partial markers only) is still blocked loud

  # slice-03 of fix-wave-marker-bypass-benign-passthrough -- ADR-001 Amendment 1.
  # slice-01 shipped the corrected guard keyed on `carries_partial_wave_context`,
  # whose exclusion clause is `and not is_des_task`. `is_des_task` matches ONLY the
  # HTML-comment form `<!-- DES-VALIDATION : required -->` (des_marker_parser.py:200).
  # A legitimate sub-dispatch carrying the PLAIN-LINE `DES-VALIDATION: required` form
  # (des_marker_parser.py:76-82 documents both forms) has is_des_task=False AND
  # has_des_markers=True -> wrongly classified partial context -> false-positive BLOCK.
  # The fix (ADR-001 Amendment 1) introduces a pure derived property
  # `carries_des_validation` (True for the HTML-comment OR the plain-line form) and
  # re-points the exclusion: `carries_partial_wave_context == (has_des_markers or
  # declared_wave is not None) and not carries_des_validation`. is_des_task stays for
  # its other 17 read-sites (untouched).
  #
  # DRIVING PORT (Mandate-13 driving-port-only, Layer 3 composition): the REAL
  # PreToolUseService.validate(PreToolUseInput(...)) composition-root service, built
  # via the production composition root (Pillar 3, service_factory). The service is
  # the SUT; only the wave-active floor (a driven-internal filesystem port) is
  # arranged. The observable is the service's HookDecision -- specifically whether
  # the WAVE_MARKER_BYPASS veto fires (the exact surface a Claude Code hook
  # translates to exit 0 / exit 2). FLOOR ISOLATION (Fix-2): every scenario injects
  # its floor into a clean tmp root and drives under that root's CWD, so the
  # production WaveActiveReader reads the INJECTED floor, never the developer's live
  # working-tree floor.
  #
  # DECISION TABLE (the refined guard, under an active design floor, not entering):
  #   ARMED + plain-line DES-VALIDATION: required        -> ALLOW (carries the marker) [AT-8]
  #   ARMED + partial markers, NEITHER DES-VALIDATION form -> BLOCK (real bypass, K1)  [AT-9]
  #
  # RED-for-right-reason (at HEAD the slice-01 guard keys on `not is_des_task`):
  #   AT-8 -- a plain-line DES-VALIDATION child has is_des_task=False +
  #     has_des_markers=True, so carries_partial_wave_context is True at HEAD ->
  #     the guard BLOCKs WAVE_MARKER_BYPASS where the refined guard must ALLOW ->
  #     the not-blocked assertion fails with a semantic AssertionError.
  #   AT-9 -- a neither-form partial dispatch has carries_partial_wave_context=True
  #     under BOTH the slice-01 and the refined predicate, so it BLOCKs at HEAD and
  #     post-fix: preservation-GREEN (K1 survives the refinement).

  @slice-03 @driving_port @real-io @contract-shape:bounded-change
  Scenario: A plain-line DES-VALIDATION dispatch is recognized under an active floor
    Given a design wave floor is armed in an isolated project for the marker-form check
    When an in-wave child carrying a plain-line required marker is checked by the gate
    Then the gate does not block the dispatch as a wave-bypass

  @slice-03 @driving_port @real-io @error @contract-shape:unbounded-preservation
  Scenario: A child carrying neither DES-VALIDATION form is still blocked loud
    Given a design wave floor is armed in an isolated project for the marker-form check
    When an in-wave child carrying partial markers but neither required-marker form is checked by the gate
    Then the gate blocks the dispatch as a wave-bypass
    And the bypass block names the wave-bypass so it cannot pass as a silent success
