@feature-opt-in-per-step-double-review
Feature: Priya opts one DISTILL review step into required agreement
  As Priya, an nWave operator tuning DISTILL review cost
  I want to opt ONE review step into requiring two dispatches that must agree
  So that I pay the extra review cost only where a wrong verdict is expensive

  # slice-01 (@walking-skeleton): Priya sets `require_agreement=true` on Eclipse
  # and the registry resolves it as requiring agreement -- while every other
  # step, and Eclipse itself when no override is set, still resolves to
  # `False` exactly as today (DD-4 strict opt-in, no profile-level cascade).
  # This slice proves the RESOLUTION half only (does the registry correctly
  # compute the boolean); the DISPATCH half (actually firing the step twice
  # and applying the DD-3 agreement predicate) is slice-02 scope -- ABSENT
  # from this file until slice-02 enters (atdd_pure per-slice JIT, ADR-025).
  #
  # Driving surface: the real `DESConfig.resolve_review_steps()` read over a
  # real `.nwave/des-config.json` under `tmp_path` (in-process, real-IO --
  # Layer 3 composition per Mandate-13; no interpreter fork warranted, same
  # driving surface as the sibling `rigor-review-step-toggles` feature).
  #
  # Active-RED topology (nw-distill-red-scaffolding P1-P4, mirrors the
  # sibling's slice-04 `is_always_on` pattern exactly): `DESConfig` and
  # `ReviewStepResolver.resolve()` already exist and already return a real
  # `ResolvedReviewStepSet` today (shipped, sealed) -- P1/P2 clean, no
  # ImportError. The RED is that `ResolvedReviewStepSet` does NOT yet expose
  # a `requires_agreement(step_id)` accessor (P3: absent behaviour reached at
  # RUNTIME via a `getattr`-guard); the guard converts the absence into a
  # semantic `AssertionError` (P4), never a raw `AttributeError`. Every
  # scenario below carries at least one `Then` on this not-yet-present
  # accessor, so every scenario in this slice is active-RED today -- the
  # membership (`active reviewers`) and hard-pin (`hard-pinned always-on`)
  # `Then`s reused from the sibling feature are GREEN-today regression locks
  # (those accessors already ship), mirroring the sibling's own mixed
  # RED-not-BROKEN + regression-lock shape.

  @slice-01 @coupled @walking_skeleton @driving_port @real-io @JOB-028 @contract-shape:pure-function
  Scenario: Opting Eclipse into required agreement marks it for double-dispatch
    Given a project rigor config that requires agreement for the "eclipse" review step
    When the active review steps are resolved for that project
    Then the resolved set reports the "eclipse" review step as requiring agreement

  @slice-01 @coupled @driving_port @real-io @JOB-028 @contract-shape:pure-function
  Scenario: A config with no per-step toggles requires agreement from no review step
    Given a project rigor config with review enabled and no per-step toggles
    When the active review steps are resolved for that project
    Then the resolved set does not report the "eclipse" review step as requiring agreement
    And the "eclipse" review step is among the active reviewers

  @slice-01 @coupled @driving_port @real-io @JOB-028 @contract-shape:pure-function
  Scenario: Explicitly declining required agreement behaves exactly like leaving it unset
    Given a project rigor config that explicitly does not require agreement for the "eclipse" review step
    When the active review steps are resolved for that project
    Then the resolved set does not report the "eclipse" review step as requiring agreement

  @slice-01 @coupled @driving_port @real-io @JOB-028 @contract-shape:pure-function
  Scenario: Opting Eclipse into required agreement leaves every other review step untouched
    Given a project rigor config that requires agreement for the "eclipse" review step
    When the active review steps are resolved for that project
    Then the resolved set does not report the "architect" review step as requiring agreement
    And the resolved set does not report the "forge" review step as requiring agreement
    And the resolved set does not report the "sentinel" review step as requiring agreement

  @slice-01 @coupled @driving_port @real-io @JOB-028 @contract-shape:pure-function
  Scenario: Sentinel can be opted into required agreement without losing its hard-pinned status
    Given a project rigor config that requires agreement for the "sentinel" review step
    When the active review steps are resolved for that project
    Then the resolved set reports the "sentinel" review step as requiring agreement
    And the resolved set reports the "sentinel" review step as hard-pinned always-on
    And the "sentinel" review step is among the active reviewers

  @slice-01 @coupled @driving_port @real-io @JOB-028 @contract-shape:pure-function
  Scenario: Sentinel stays hard-pinned always-on even when required agreement is never set for it
    Given a project rigor config with review enabled and no per-step toggles
    When the active review steps are resolved for that project
    Then the resolved set does not report the "sentinel" review step as requiring agreement
    And the resolved set reports the "sentinel" review step as hard-pinned always-on

  @slice-01 @coupled @driving_port @real-io @JOB-028 @contract-shape:pure-function
  Scenario: Requiring agreement for a disabled review step still resolves regardless of whether it fires
    Given a project rigor config that disables the "eclipse" review step and requires agreement for it
    When the active review steps are resolved for that project
    Then the resolved set reports the "eclipse" review step as requiring agreement
    And the "eclipse" review step is not among the active reviewers

  @slice-01 @coupled @driving_port @real-io @JOB-028 @contract-shape:pure-function
  Scenario: Two review steps can each independently require agreement in the same config
    Given a project rigor config that requires agreement for the "eclipse" and "architect" review steps
    When the active review steps are resolved for that project
    Then the resolved set reports the "eclipse" review step as requiring agreement
    And the resolved set reports the "architect" review step as requiring agreement
    And the resolved set does not report the "forge" review step as requiring agreement
