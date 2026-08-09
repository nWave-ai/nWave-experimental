# E7 — install preserves neighbours and fails safe (ADR-CA-006/CA-007; Q5 from
# the prior soft-attribution feature: skip when ~/.claude is absent).
#
# Attribution commit rewriting is now driven by the shared PreToolUse dispatch
# (exercised by the sibling real-adapter acceptance slice), not by a separate,
# independently-registered commit-attribution hook. Install must therefore
# never stomp a neighbour: the operator's own hooks and the existing DES guard
# stay registered exactly as they were, and install registers no independent
# commit-attribution hook of its own. When the Claude config is absent or
# corrupt, install leaves it alone (untouched, or simply absent) rather than
# crashing.
#
# Driving port: the install plugin lifecycle over a sandboxed ~/.claude.

@driving_port @real-io @contract-shape:bounded-change
Feature: Installing nWave preserves neighbours and never registers an independent commit-attribution hook

  Scenario: Install with attribution enabled preserves neighbours and registers no independent hook
    Given a sandboxed nWave home where the commit guard is already registered
    And the operator has added their own Bash hook
    And the operator has chosen to enable attribution
    When nWave is installed
    Then the operator's own Bash hook is still registered
    And the existing commit guard is still registered
    And no commit-attribution hook is registered
    And the install still succeeds

  Scenario: Registration skips when the Claude config is absent
    Given a sandboxed nWave home with no Claude configuration
    And the operator has chosen to enable attribution
    When nWave is installed
    Then no commit-attribution hook is registered
    And the install still succeeds

  Scenario: Registration warns and skips when the settings file is unreadable
    Given a sandboxed nWave home whose settings are corrupt
    And the operator has chosen to enable attribution
    When nWave is installed
    Then the corrupt settings are left untouched
    And the install still succeeds
