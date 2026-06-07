@feature-walking-skeleton-production-like-gate
Feature: A customer project inherits the production-like walking-skeleton pattern
  As a developer building a product with nWave
  I want nWave to scaffold a CI job that installs my own delivered artifact and
    runs my walking-skeleton test against it
  So that I adopt the production-like gate by filling one image reference, not
    by designing the gate

  # carpaccio slice-14 (DESIGN slice-07). US-05 / persona A2: the
  # customer-project CI scaffold. nWave cannot know A2's production
  # environment -- it hands A2 the pattern: a generated walking-skeleton CI job
  # with a wired first-tier clean-prefix install step and a documented
  # placeholder for the customer's own prod-like image. The scaffolded job
  # inherits the fail-closed deferral semantics for free.
  #
  # Layer 3 (FS acceptance): real composition root over the scaffold step;
  # example-only, no PBT (Mandate 9/11). State-mutating steps assert via
  # assert_state_delta over a port-exposed scaffolded-files universe
  # (Mandate 8).
  #
  # Driving port: the nWave walking-skeleton scaffold step (DEVOPS surface).

  @slice-14 @driving_port @contract-shape:bounded-change
  Scenario: The scaffold writes a walking-skeleton CI job for a customer project
    Given a customer project with no walking-skeleton CI job
    When the developer runs the walking-skeleton scaffold step
    Then the scaffold writes a walking-skeleton CI job with a clean-prefix install of the project's delivered artifact
    And the CI job carries a documented placeholder for the developer's own prod-like image
    And the CI job inherits the fail-closed deferral semantics

  @slice-14 @driving_port @contract-shape:bounded-change
  Scenario: A scaffolded project runs the first tier without a prod-like image filled in
    Given a customer project with the scaffolded walking-skeleton CI job
    And the developer has not filled the prod-like image placeholder
    When the walking-skeleton CI job runs
    Then the clean-prefix walking-skeleton check runs and gates the build
    And the container tier is recorded as not configured rather than silently passed

  @slice-14 @driving_port @contract-shape:bounded-change
  Scenario: The scaffold explains the three-facet rule to the customer developer
    Given a customer project with no walking-skeleton documentation
    When the developer runs the walking-skeleton scaffold step
    Then the scaffold writes a walking-skeleton explanation describing why the delivered artifact is installed rather than the source
