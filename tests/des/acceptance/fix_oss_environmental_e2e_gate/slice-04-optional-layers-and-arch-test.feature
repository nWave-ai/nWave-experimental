@feature-fix-oss-environmental-e2e-gate
Feature: Optional defense-in-depth layers are offered, never mandated
  As an nWave framework developer installing nWave on any machine
  I want the optional git pre-push hook offered only when git is present, and
    an architecture test that keeps the gate wired into the floor
  So that a customer with no git still gets the full floor and the gate
    cannot be silently removed from feature-end

  # carpaccio slice-04 (DESIGN [REF] Slice Plan, [REF] Optional Layers, R10).
  # Optional-layer install-time offer (offer-never-mandate) + the CREATE-NEW
  # arch test that statically asserts the gate stays wired.
  #
  # CONTRACT SOURCE: NORMATIVE-FROZEN L1.4 governs the CLI; this slice governs
  # the layers AROUND it. The git pre-push hook wraps the same frozen CLI --
  # it is optional defense-in-depth, never the floor (DESIGN [REF] Optional
  # Layers). The floor is the DELIVER feature-end orchestration step (slice-02).
  #
  # The git-present / interactivity / opt-out matrix is FINITE -> parametrize-
  # collapse, NOT PBT. The arch test sad paths are example-based (layer 3).
  #
  # Layer 3 (FS acceptance) for the install-offer; layer 3 (pytest collection)
  # for the arch test. Example-based per Mandate 11.
  #
  # Driving port: the `nwave install` doctor-style offer step; the arch test
  # `tests/build/test_environmental_gate_wiring.py` via pytest collection.

  @slice-04 @driving_port @real-io @contract-shape:bounded-change
  Scenario Outline: The git pre-push hook is offered only when the environment permits it
    Given an install environment that "<git_state>" git and runs "<interactivity>"
    When nWave offers its optional defense-in-depth layers
    Then the git pre-push hook is "<hook_outcome>"
    And the environmental e2e gate floor is installed regardless

    Examples:
      | git_state | interactivity            | hook_outcome   |
      | has       | interactively            | offered        |
      | lacks     | interactively            | not offered    |
      | has       | non-interactively        | not offered    |
      | has       | with the no-git-hooks opt-out | not offered    |

  @slice-04 @driving_port @real-io @contract-shape:bounded-change
  Scenario: A machine without git still installs the gate floor
    Given an install environment that lacks git entirely
    When nWave offers its optional defense-in-depth layers
    Then no git pre-push hook is offered
    And the environmental e2e gate floor is installed regardless

  @slice-04 @driving_port @real-io @error @contract-shape:bounded-change
  Scenario: The architecture test goes red when the gate is unwired from the floor
    Given the environmental e2e gate is registered as a shipped command and named in the feature-end orchestration step
    When the gate command is dropped from the shipped command set or its token is removed from the feature-end orchestration step
    Then the gate-wiring architecture test fails
    And the failure diagnostic names which wiring point lost the gate
