@feature-rigor-review-step-toggles
Feature: Priya turns one DISTILL review step off and sees it stop running
  As Priya, an nWave operator shipping a low-stakes change
  I want to disable a specific review step under rigor
  So that I ship proportionally to the risk without abandoning the profile

  # slice-01 (@walking-skeleton): Priya disables ONE review step (Eclipse, the
  # PO reviewer) and sees it excluded from the active DISTILL reviewers, while a
  # config with no per-step toggle still runs exactly the profile's default set
  # unchanged (additive back-compat, DD-D5). Driving surface: the real
  # ``DESConfig.resolve_review_steps().active()`` over a real
  # ``.nwave/des-config.json`` (in-process, real-IO). One step, on/off only.

  @slice-01 @walking_skeleton @driving_port @real-io @JOB-001 @contract-shape:pure-function
  Scenario: Disabling the Eclipse review step removes it from the active reviewers
    Given a project rigor config that disables the "eclipse" review step
    When the active review steps are resolved for that project
    Then the "eclipse" review step is not among the active reviewers

  @slice-01 @driving_port @real-io @JOB-002 @contract-shape:pure-function
  Scenario: A config with no per-step toggles runs the profile default set unchanged
    Given a project rigor config with review enabled and no per-step toggles
    When the active review steps are resolved for that project
    Then the "eclipse" review step is among the active reviewers

  @slice-01 @driving_port @real-io @JOB-002 @contract-shape:pure-function
  Scenario: Explicitly enabling the Eclipse review step keeps it in the active reviewers
    Given a project rigor config that enables the "eclipse" review step
    When the active review steps are resolved for that project
    Then the "eclipse" review step is among the active reviewers
