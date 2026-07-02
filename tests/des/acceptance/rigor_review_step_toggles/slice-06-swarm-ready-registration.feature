@feature-rigor-review-step-toggles
Feature: A new review step registers into the registry with no resolver change
  As Priya, an nWave operator anticipating the end-of-epic adversarial swarm
  I want a brand-new review step to register through the same catalog
  So that future reviewers (swarm, per-wave) slot in as data, never as new code

  # slice-06 (FINAL slice, DD-D4/DSN-5): a representative new review step --
  # `swarm` (placeholder identity for the upcoming `F-EPIC-END-SWARM-REVIEW` /
  # per-wave reviewers, agent="nw-epic-end-swarm-reviewer") -- proves the
  # registry absorbs a NEW catalog member through the EXACT SAME resolver path
  # already shipped (slices 01-04): enable/disable (DSN-3 precedence), per-step
  # model (slice-02), and independence from the other registered steps
  # (eclipse/architect/forge/sentinel unaffected by swarm's presence). Driving
  # surface unchanged: the real `DESConfig.resolve_review_steps()` over a real
  # `.nwave/des-config.json` (in-process, real-IO -- no resolver code path is
  # swarm-specific, so no fork/CLI is warranted).
  #
  # RED-for-right-reason: `swarm` is not yet a `REVIEW_STEP_CATALOG` member, so
  # scenarios asserting its presence/model fail with a semantic AssertionError
  # (membership/value mismatch), NOT an ImportError/KeyError. Scenario #4 is a
  # GREEN-today regression lock: disabling an unknown id alongside a real one
  # (architect) does not perturb the other registered steps' independent
  # resolution -- proving registration-readiness does not require touching the
  # resolver (DSN-5).

  @slice-06 @driving_port @real-io @JOB-002 @contract-shape:pure-function
  Scenario: A newly registered swarm review step defaults active per profile like any catalog member
    Given a project rigor config with review enabled and no per-step toggles
    When the active review steps are resolved for that project
    Then the "swarm" review step is among the active reviewers

  @slice-06 @driving_port @real-io @JOB-002 @contract-shape:pure-function
  Scenario: An explicit per-step override enables the swarm review step on a pinned model
    Given a project rigor config with reviewer model "haiku" that pins the "sonnet" model for the "swarm" review step
    When the active review steps are resolved for that project
    Then the "swarm" review step is among the active reviewers
    And the "swarm" review step resolves to the "sonnet" model

  @slice-06 @driving_port @real-io @JOB-002 @contract-shape:pure-function
  Scenario: A model-only override keeps the swarm review step active per profile and on the pinned model
    Given a project rigor config with reviewer model "haiku" that pins the "sonnet" model for the "swarm" review step without toggling it
    When the active review steps are resolved for that project
    Then the "swarm" review step is among the active reviewers
    And the "swarm" review step resolves to the "sonnet" model

  @slice-06 @driving_port @real-io @JOB-001 @contract-shape:pure-function
  Scenario: Disabling the swarm review step alongside an existing toggle leaves the other registered reviewers unaffected
    Given a project rigor config that disables the "swarm" and "architect" review steps
    When the active review steps are resolved for that project
    Then the "swarm" review step is not among the active reviewers
    And the "architect" review step is not among the active reviewers
    And the "eclipse" review step is among the active reviewers
    And the "forge" review step is among the active reviewers
    And the "sentinel" review step is among the active reviewers
