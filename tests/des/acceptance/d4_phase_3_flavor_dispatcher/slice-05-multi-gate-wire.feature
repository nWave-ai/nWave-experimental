@feature-d4-phase-3-flavor-dispatcher
Feature: dispatch.pre composes verify-readiness ahead of carpaccio (multi-gate wire)

  As D4 Phase 3 slice-05 author of the multi-gate dispatch wire
  I want the carpaccio intercept's gate invoker to dispatch on each gate id in
  the atdd_pure dispatch.pre YAML composition (verify-readiness-pre-dispatch
  then carpaccio-slice-gate), so that the slice-03 readiness gate auto-fires
  ahead of carpaccio per friction #57 cascade closure
  So that adding or reordering gates on dispatch.pre is a YAML edit to the
  flavor file, never a Python edit to the intercept invoker
  (INV-2 composable, INV-12 future workflow change = reconfiguration,
  INV-4 workflow IS data, OSS hook-only mandate)

  Background:
    Given a tmp_path flavors directory monkey-patched onto the intercept

  @slice-05 @coupled @walking_skeleton @driving_port @real-io @contract-shape:bounded-change
  Scenario: A multi-gate dispatch.pre clears when both gates clear
    Given the atdd_pure flavor wires verify-readiness-pre-dispatch ahead of carpaccio-slice-gate on dispatch.pre
    And the readiness gate runner is programmed to clear the dispatch
    And the carpaccio gate runner is programmed to clear the entering slice
    And a dispatch prompt carrying valid atdd_pure markers for a fresh slice
    When the multi-gate intercept evaluates the dispatch
    Then the dispatch verdict is a multi-gate allow decision
    And the invocation log records verify-readiness-pre-dispatch then carpaccio-slice-gate

  @slice-05 @coupled @driving_port @real-io @error @contract-shape:bounded-change
  Scenario: A readiness block halts dispatch before carpaccio is invoked
    Given the atdd_pure flavor wires verify-readiness-pre-dispatch ahead of carpaccio-slice-gate on dispatch.pre
    And the readiness gate runner is programmed to block the dispatch
    And the carpaccio gate runner is programmed to clear the entering slice
    And a dispatch prompt carrying valid atdd_pure markers for a fresh slice
    When the multi-gate intercept evaluates the dispatch
    Then the block event names the readiness rejection
    And the invocation log records verify-readiness-pre-dispatch only

  @slice-05 @coupled @driving_port @real-io @regression-pin @contract-shape:bounded-change
  Scenario: A carpaccio block preserves the pre-existing carpaccio rejection event
    Given the atdd_pure flavor wires verify-readiness-pre-dispatch ahead of carpaccio-slice-gate on dispatch.pre
    And the readiness gate runner is programmed to clear the dispatch
    And the carpaccio gate runner is programmed to block the entering slice
    And a dispatch prompt carrying valid atdd_pure markers for a fresh slice
    When the multi-gate intercept evaluates the dispatch
    Then the block event names the carpaccio rejection
    And the invocation log records verify-readiness-pre-dispatch followed by carpaccio-slice-gate

  @slice-05 @coupled @driving_port @real-io @regression-pin @contract-shape:bounded-change
  Scenario: A slice-02-shaped dispatch (no readiness runner) preserves slice-02 single-gate behaviour
    Given a dispatch prompt carrying valid atdd_pure markers for a fresh slice
    When the multi-gate intercept evaluates the dispatch in the slice-02 single-gate call shape
    Then the dispatch verdict is a multi-gate allow decision
    And the invocation log records carpaccio-slice-gate only
