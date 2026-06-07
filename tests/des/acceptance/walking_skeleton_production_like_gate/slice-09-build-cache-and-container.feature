@feature-walking-skeleton-production-like-gate
Feature: Feature-end stays fast and the container tier runs the real artifact
  As an nWave framework developer
  I want a second gate run on an unchanged tree to reuse the cached build, and
    the container runner to install the real artifact in a real image
  So that the gate is fast enough never to be disabled, and the container tier
    is real fidelity

  # carpaccio slice-09 (DESIGN slice-04, part 3 of 3). RM-9: the build is
  # reused when the repository tree hash is unchanged -- disabling the gate to
  # save time has no payoff. The T2 real-Docker contract smoke proves the
  # container runner installs and runs the real artifact; it is fenced behind
  # @requires_external and skipped when Docker is absent. Layer 3 (subprocess /
  # FS acceptance) + layer 5 for the @real-io smoke. Example-only, no PBT
  # (Mandate 9/11).
  #
  # Driving port: `des.cli.walking_skeleton_gate`.

  # RM-9 -- the build is reused when the repository tree is unchanged.
  @slice-09 @driving_port @contract-shape:unbounded-preservation
  Scenario: A second gate run on an unchanged tree reuses the cached build
    Given a feature whose walking-skeleton gate has already built the delivered artifact
    And the repository tree is unchanged since that build
    When the feature-end gate verifies the walking skeleton again
    Then the gate reuses the cached delivered artifact without rebuilding it
    And the walking-skeleton gate reports PASS at tier of record T1

  # T2 real-Docker contract smoke -- skipped when Docker is absent.
  @slice-09 @driving_port @requires_external @real-io @adapter-integration @contract-shape:bounded-change
  Scenario: The container runner installs and runs the artifact in a real image
    Given a feature that ships a packaged CLI module with a walking-skeleton acceptance test
    And a real container runtime is available
    When the container runner installs the delivered artifact into a clean image and runs the walking-skeleton test
    Then the walking-skeleton gate reports PASS at tier of record T2
