@feature-rigor-review-step-toggles
Feature: Priya pins a cheaper model for a review step she keeps
  As Priya, an nWave operator shipping a low-stakes change
  I want to choose which model a review step I keep runs on
  So that I control what each quality level costs without dropping the step

  # slice-02: Priya keeps the Eclipse (PO) review step but pins it to a cheaper
  # model, and sees that step's RESOLVED model honour her choice. A step with no
  # per-step model still resolves to the profile-level reviewer model (additive
  # back-compat, DD-D5). Per-step `model` resolves through the SAME registry
  # entry as enable/disable (DD-D1, DSN-3 model precedence:
  # ``model = override.model if present else profile reviewer_model``).
  # Driving surface: the real ``DESConfig.resolve_review_steps()`` over a real
  # ``.nwave/des-config.json`` (in-process, real-IO); the resolved set is asked
  # for each active step's model (``.model_for(step_id)``, slice-02 target).

  @slice-02 @driving_port @real-io @JOB-002 @contract-shape:pure-function
  Scenario: A per-step model override resolves that step onto the chosen model
    Given a project rigor config with reviewer model "haiku" that pins the "sonnet" model for the "eclipse" review step
    When the active review steps are resolved for that project
    Then the "eclipse" review step resolves to the "sonnet" model

  @slice-02 @driving_port @real-io @JOB-002 @contract-shape:pure-function
  Scenario: A step with no per-step model resolves to the profile reviewer model
    Given a project rigor config with reviewer model "haiku" and no per-step model overrides
    When the active review steps are resolved for that project
    Then the "eclipse" review step resolves to the "haiku" model

  @slice-02 @driving_port @real-io @JOB-002 @contract-shape:pure-function
  Scenario: A model-only override keeps the step active per profile and on the override model
    Given a project rigor config with reviewer model "haiku" that pins the "sonnet" model for the "eclipse" review step without toggling it
    When the active review steps are resolved for that project
    Then the "eclipse" review step is among the active reviewers
    And the "eclipse" review step resolves to the "sonnet" model
