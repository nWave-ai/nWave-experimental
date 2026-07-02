@feature-rigor-review-step-toggles
Feature: Priya cannot disable the Sentinel structural-correctness reviewer
  As Priya, an nWave operator tuning DISTILL review cost
  I want the Sentinel structural-correctness reviewer to be un-disable-able
  So that no profile default or per-step override can silence the one reviewer
     that guards Gherkin antipatterns, hexagonal boundary, and scaffold integrity

  # slice-04: Sentinel (`nw-acceptance-designer-reviewer`) is `always_on=True` in
  # the registry (slice-01 design). The hard-pin must hold against EVERY disabling
  # attempt: a per-step `rigor.review_steps.sentinel.enabled=false`, a profile-level
  # lean `rigor.review_enabled=false`, and BOTH together. The lean floor case also
  # covers the C3-GAP-001 "all cost-driven off" scenario from slice-03 -- with the
  # profile flag off, only Sentinel survives. Driving surface unchanged: the real
  # in-process `DESConfig.resolve_review_steps().active()` over a real
  # `.nwave/des-config.json` under `tmp_path` (no interpreter fork).
  #
  # The membership scenarios (#1-#3) are GREEN-today (the always_on short-circuit
  # already makes `sentinel.enabled=false` inert), so they are regression locks.
  # The active-RED of the slice is the EXPLICIT hard-pin observable (#4-#5): a
  # not-yet-present `ResolvedReviewStepSet.is_always_on(step_id)` accessor that
  # turns the implicit short-circuit into an inspectable contract -- "no config can
  # report Sentinel as anything but always-on". RED is a semantic AssertionError
  # on the absent accessor (getattr-guarded), NOT an AttributeError.

  @slice-04 @driving_port @real-io @JOB-001 @contract-shape:pure-function
  Scenario: A per-step override disabling Sentinel has no effect
    Given a project rigor config that disables the "sentinel" review step
    When the active review steps are resolved for that project
    Then the "sentinel" review step is among the active reviewers

  @slice-04 @driving_port @real-io @JOB-001 @contract-shape:pure-function
  Scenario: Disabling review at the profile level leaves Sentinel as the floor
    Given a project rigor config with review disabled at the profile level
    When the active review steps are resolved for that project
    Then the "sentinel" review step is among the active reviewers
    And the "eclipse" review step is not among the active reviewers
    And the "architect" review step is not among the active reviewers
    And the "forge" review step is not among the active reviewers

  @slice-04 @driving_port @real-io @JOB-001 @contract-shape:pure-function
  Scenario: Disabling Sentinel and the profile together still keeps Sentinel
    Given a project rigor config that disables review and the "sentinel" review step
    When the active review steps are resolved for that project
    Then the "sentinel" review step is among the active reviewers

  @slice-04 @driving_port @real-io @JOB-001 @contract-shape:pure-function
  Scenario: The resolved set hard-pins Sentinel as always-on even when disabled
    Given a project rigor config that disables the "sentinel" review step
    When the active review steps are resolved for that project
    Then the resolved set reports the "sentinel" review step as hard-pinned always-on

  @slice-04 @driving_port @real-io @JOB-001 @contract-shape:pure-function
  Scenario: The hard-pin is specific to Sentinel and not the cost-driven reviewers
    Given a project rigor config with review enabled and no per-step toggles
    When the active review steps are resolved for that project
    Then the resolved set reports the "sentinel" review step as hard-pinned always-on
    And the resolved set does not report the "eclipse" review step as hard-pinned always-on
