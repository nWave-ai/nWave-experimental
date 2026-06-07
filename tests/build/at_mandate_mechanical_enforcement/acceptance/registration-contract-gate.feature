# slice-06 — the dispatcher registration-contract gate, a git-free in-process
# import-resolution arch-test (feature-delta slice-plan row 223, DDD-6).
#
# The gate reads a subcommand registry as data and checks each row against the
# dispatcher's wiring contract: every row must RESOLVE, IMPORT, and expose a
# CALLABLE entry. A dropped or half-wired row — its module unimportable, or its
# main missing/non-callable — is a registration breach the gate catches, so a
# dropped-registration regression cannot pass green. A fully-wired registry is
# cleared. The gate is count-agnostic by construction: it iterates whatever rows
# the registry exposes, so a newly-added valid subcommand is auto-covered with
# zero per-subcommand authoring — and the count-agnostic scenario proves this by
# clearing the LIVE des registry read at runtime.
#
# Honest tagging: an in-process importlib resolution — @component (auto-unit
# under tests/build/), NEVER @wiring_e2e/@subprocess. The gate practises the
# honesty the suite enforces. No spawn, no real I/O beyond importing the
# registered modules.

@feature-at-mandate-mechanical-enforcement @slice-06 @component
Feature: A dropped or half-wired subcommand registration is caught

  As the test author and the audit rotation
  I want every subcommand row of the dispatcher mechanically checked so a row
  whose module cannot be imported or whose entry is missing is caught, while a
  fully-wired registry is cleared and the check scales to the live registry
  with no per-subcommand authoring
  So that a dropped-registration regression cannot pass green, generically

  Background:
    Given the dispatcher registration-contract gate

  @slice-06 @driving_port @contract-shape:pure-function
  Scenario: The gate catches a registry with a dropped and a half-wired row
    When the gate checks a registry with a dropped module and a missing entry
    Then the registration-contract gate rules the registry non-conformant
    And the gate names the dropped-module row and the missing-entry row
    And the inspected registry is left untouched

  @slice-06 @contract-shape:pure-function
  Scenario: The gate clears a fully-wired registry
    When the gate checks a registry whose every row resolves and exposes its entry
    Then the registration-contract gate rules the registry conformant
    And the gate raises no objection to the fully-wired registry

  @slice-06 @contract-shape:pure-function
  Scenario: The gate clears the live registry and scales to its row count
    When the gate checks the live dispatcher registry read at runtime
    Then the registration-contract gate rules the registry conformant
    And the gate checked every row the live registry exposes
