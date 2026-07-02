@feature-rigor-review-step-toggles
Feature: Priya turns each cost-driven DISTILL reviewer off independently
  As Priya, an nWave operator shipping a low-stakes change
  I want to disable any of the cost-driven DISTILL review steps on its own
  So that I tune review cost step-by-step without touching the others or the profile

  # slice-03: the registry now carries all three cost-driven DISTILL reviewers --
  # Eclipse (PO, `nw-product-owner-reviewer`), Architect
  # (`nw-solution-architect-reviewer`) and Forge (`nw-platform-architect-reviewer`)
  # -- alongside always-on Sentinel. Priya disables Architect and Forge while
  # keeping Eclipse, and each per-step toggle is INDEPENDENT (disabling one does
  # not move the others). A config with no per-step toggles still runs all three
  # cost-driven reviewers (additive back-compat, DD-D5). Driving surface: the real
  # ``DESConfig.resolve_review_steps().active()`` over a real
  # ``.nwave/des-config.json`` (in-process, real-IO -- the nw-distill review
  # dispatch reads this method, not a CLI, so no interpreter fork).

  @slice-03 @driving_port @real-io @JOB-002 @contract-shape:pure-function
  Scenario: With no per-step toggles all three cost-driven review steps fire
    Given a project rigor config with review enabled and no per-step toggles
    When the active review steps are resolved for that project
    Then the "eclipse" review step is among the active reviewers
    And the "architect" review step is among the active reviewers
    And the "forge" review step is among the active reviewers

  @slice-03 @driving_port @real-io @JOB-001 @contract-shape:pure-function
  Scenario: Disabling the Architect review step leaves Forge and Eclipse firing
    Given a project rigor config that disables the "architect" review step
    When the active review steps are resolved for that project
    Then the "architect" review step is not among the active reviewers
    And the "forge" review step is among the active reviewers
    And the "eclipse" review step is among the active reviewers

  @slice-03 @driving_port @real-io @JOB-001 @contract-shape:pure-function
  Scenario: Disabling the Forge review step leaves Architect and Eclipse firing
    Given a project rigor config that disables the "forge" review step
    When the active review steps are resolved for that project
    Then the "forge" review step is not among the active reviewers
    And the "architect" review step is among the active reviewers
    And the "eclipse" review step is among the active reviewers

  @slice-03 @driving_port @real-io @JOB-001 @contract-shape:pure-function
  Scenario: Disabling both Architect and Forge keeps Eclipse and Sentinel firing
    Given a project rigor config that disables the "architect" and "forge" review steps
    When the active review steps are resolved for that project
    Then the "eclipse" review step is among the active reviewers
    And the "sentinel" review step is among the active reviewers
    And the "architect" review step is not among the active reviewers
    And the "forge" review step is not among the active reviewers
