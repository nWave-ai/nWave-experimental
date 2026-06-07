@feature-fix-carpaccio-distill-authoring-ergonomics
Feature: The carpaccio gate's human surface agrees with its verdict on a coupled clear

  A DISTILL author submits an over-ceiling slice whose every scenario is part of
  one indivisible coupled AT group, with a recorded justification. The gate
  accepts this slice (it clears to enter implementation, exit 0) via the
  coupled-AT-group escape. Before this feature, the gate's human-readable line
  contradicted that success -- it printed "carpaccio gate refused" for a slice
  that was in fact cleared, confusing every operator on every coupled clear
  (friction #4). This feature makes the human surface tell the truth: a cleared
  coupled slice reads as a success that names the escape it used.

  # ADR-002: CoupledSliceAccepted maps to a PASS-class human surface.
  # Driving port: the real `des carpaccio-slice-gate` CLI invoked as a subprocess
  # (Layer 3 / wiring_e2e). Example-only, no PBT (Mandate 9/11).

  Background:
    Given a repository for an atdd_pure feature

  @walking-skeleton @driving-port @real-io @slice-01 @contract-shape:bounded-change
  Scenario: A cleared coupled slice reads as a success that names its escape
    Given the feature carries an over-ceiling slice that is fully coupled with a recorded justification
    And the entering slice has a recorded approved AT-review verdict
    When the operator runs the carpaccio slice gate for the entering slice
    Then the slice is cleared to enter implementation
    And the operator sees a success line naming the coupled-AT-group escape
    And the operator does not see a refusal on the cleared slice
    And the gate records that the coupled slice was accepted
    And the gate writes no file in the repository
