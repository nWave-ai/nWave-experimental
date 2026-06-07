@feature-walking-skeleton-production-like-gate
Feature: The arch test proves the gate itself ships and its hooks are wired
  As an nWave framework developer
  I want the distribution-completeness check to also verify the gate's own
    commands ship, its hook branches are registered, and its marker directories
    travel to CI
  So that the gate that catches the bug class cannot itself fall off the build

  # carpaccio slice-11 (DESIGN slice-05, part 2 of 2). The arch test's
  # self-coverage assertions: RM-1 (the gate's own commands are in the shipped
  # enumeration), RM-2 (the hook branches are statically registered -- the
  # structural layer that catches hook un-wiring without running a hook), and
  # RM-3 ST-21 (the marker directories are git-tracked so a deferral can travel
  # to CI). Layer 4 (integration): example-pinned, traditional assertions
  # permitted (Mandate 8).
  #
  # Driving port: the `pytest` distribution-completeness arch test.

  # RM-1 -- the gate that catches F-11 must survive its own arch test.
  @slice-11 @contract-shape:bounded-change
  Scenario: The walking-skeleton gate's own commands are in the shipped-set enumeration
    Given the distribution-completeness check enumerates the hook-invoked command set
    Then the walking-skeleton gate command is in the enumeration and survives the whitelist
    And the walking-skeleton done-gate command is in the enumeration and survives the whitelist

  # RM-2 -- the structural layer: catch hook un-wiring without running a hook.
  @slice-11 @error @contract-shape:bounded-change
  Scenario: The check fails when a required hook branch is not registered
    Given the feature-end hook handler is missing its walking-skeleton branch
    When the distribution-completeness check verifies the registered hook branches
    Then the check fails naming the unregistered hook branch

  # RM-3 ST-21 -- a deferral that cannot travel to CI is a silent pass.
  @slice-11 @error @contract-shape:bounded-change
  Scenario: The check fails when a marker directory is not git-tracked
    Given the walking-skeleton-unverified marker directory carries no explicit un-ignore rule
    When the distribution-completeness check verifies the marker directories travel to CI
    Then the check fails naming the gitignored marker directory
