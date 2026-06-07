@feature-fix-des-single-entry-point-consolidation @slice-01 @walking_skeleton
Feature: slice-01 — single des entry point walking skeleton

  As a developer or operator invoking nWave runtime utilities,
  I want one binary `des` in my PATH that exposes every subcommand,
  so that I see ONE consistent CLI surface instead of 6 console scripts plus 16 module-form invocations.

  Architecture invariant: one entry point, one CLI process per nWave runtime — `des <subcommand>`.
  Slice-01 ships the dispatcher plus ONE wired subcommand end-to-end (`health-check`).

  Background:
    Given the nwave runtime is installed

  @slice-01 @contract-shape:pure-function @driving_port @real-io @adapter-integration
  Scenario: Operator discovers every subcommand by asking des to list them
    When the operator asks des to list its subcommands
    Then the listing names every known subcommand
    And the listing exits successfully

  @slice-01 @contract-shape:bounded-change @driving_port @real-io @adapter-integration
  Scenario: Operator runs the health-check subcommand and gets the same verdict as today's standalone
    When the operator runs the health-check subcommand
    Then the health-check exits with the same verdict the standalone shim returns

  @slice-01 @contract-shape:pure-function @driving_port @real-io @adapter-integration
  Scenario: Operator asks for json output and gets the canonical health-check shape
    When the operator runs the health-check subcommand asking for json output
    Then the health-check emits the canonical json shape with seven named checks
