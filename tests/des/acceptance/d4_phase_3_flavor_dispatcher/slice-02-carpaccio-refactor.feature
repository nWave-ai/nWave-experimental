@feature-d4-phase-3-flavor-dispatcher
Feature: carpaccio intercept becomes a thin caller of the flavor dispatcher

  As D4 Phase 3 slice-02 author of the carpaccio refactor
  I want `evaluate_atdd_pure_dispatch()` to delegate gate composition to the
  flavor dispatcher reading `atdd_pure.yaml`, while preserving the public
  InterceptDecision shape byte-for-byte
  So that future workflow changes to the atdd_pure dispatch.pre composition
  are YAML edits to the flavor file, not Python edits to the intercept
  (INV-12 future workflow change = reconfiguration; INV-4 workflow IS data)

  Background:
    Given the carpaccio intercept composition is available

  @slice-02 @driving_port @real-io @contract-shape:unbounded-preservation
  Scenario: A recognised atdd_pure dispatch yields an allow decision
    Given a dispatch prompt carrying valid atdd_pure markers for feature "f-x" entering "slice-01" in phase "A_GREEN_ATS"
    And the carpaccio gate is programmed to clear the entering slice
    When the intercept evaluates the dispatch
    Then the intercept verdict is an allow decision
    And the intercept verdict is recognised as atdd_pure

  @slice-02 @driving_port @real-io @error @contract-shape:unbounded-preservation
  Scenario: A defective atdd_pure dispatch yields a marker-incomplete block decision
    Given a dispatch prompt carrying the atdd_pure mode marker but missing the slice marker
    When the intercept evaluates the dispatch
    Then the intercept verdict is a block decision
    And the intercept verdict is recognised as atdd_pure
    And the block event name is "AtddPureMarkerSetIncomplete"
    And the block reason mentions the missing slice marker

  @slice-02 @driving_port @real-io @contract-shape:unbounded-preservation
  # Was "a non-atdd_pure dispatch yields a passthrough decision". Since the
  # classic removal there is no other workflow to pass through TO, so a prompt
  # with no mode marker is REFUSED rather than waved past. The property this
  # scenario protects is unchanged -- the intercept must reach a DECISION on
  # every dispatch and never wave one through unexamined -- but the honest
  # decision for an absent mode is now a block that names it.
  Scenario: A dispatch with no mode marker is refused, never waved through
    Given a dispatch prompt carrying no DES markers at all
    When the intercept evaluates the dispatch
    Then the intercept verdict is a block decision
    And the block event name is "DispatchModeUnresolved"
