# Regression guard for fix-installer-never-ships-data-tree.
#
# THE DEFECT: `nWave/data/` was never installed by any plugin, yet eight
# runtime modules read it (log-persistence defaults, coverage-map digest
# fixtures, the flavor dispatcher's tables, `des doctor`, two adapters, and
# the orchestrator-affordance catalogue the standing-loop hook injects). On
# every operator machine those reads resolved against a directory that only
# exists in a development checkout, and the installer reported success
# regardless.
#
# THE FIX: `DESPlugin._install_des_data(context)` copies `nWave/data/` to
# `<claude_dir>/data/`, wired into `install()` immediately before the
# templates step. Fail-loud contract: an absent source is refused (never
# skipped) with a WHAT/WHY/HOW message naming the path tried; after the copy
# it verifies the STRUCTURED FACT (every declared entry present at the
# destination), never the weak signal "copytree did not raise".
#
# Driving port: DESPlugin._install_des_data(InstallContext) — the real
# plugin method, real filesystem under tmp_path. No mocking of the method
# itself (Pillar 3); the "dropped entry" scenario patches only the stdlib
# copy call to simulate an environmental partial-copy, not the method's own
# verification logic.

@feature-installer-never-ships-data-tree
Feature: DES installer plugin installs the framework data tree its runtime consumers read

  As a framework maintainer
  I need the installer to deploy nWave/data/ to the operator's <claude_dir>/data/
  So that log-persistence defaults, coverage-map fixtures, the flavor dispatcher tables,
    des doctor, and the orchestrator-affordance catalogue never resolve against a
    directory that only exists in a development checkout

  Background:
    Given an isolated installation target

  @slice-01 @walking_skeleton @driving_port @contract-shape:bounded-change
  Scenario: A valid data source tree is installed in full
    Given a framework source tree carrying the declared data entries
    When the DES plugin installs the framework data tree
    Then the plugin reports success
    And every declared data entry exists at the destination
    And the destination carries an "orchestrator-affordance" entry

  @slice-01 @driving_port @contract-shape:bounded-change
  Scenario: A missing data source tree is refused, never silently skipped
    Given no data directory exists anywhere in the framework source
    When the DES plugin installs the framework data tree
    Then the plugin does not report success
    And the failure names the source path it tried
    And the failure explains WHAT, WHY, and HOW

  @slice-01 @driving_port @contract-shape:bounded-change
  Scenario: An entry that fails to arrive at the destination is refused, not reported as success
    Given a framework source tree carrying the declared data entries
    And the copy step silently drops the "orchestrator-affordance" entry on its way to the destination
    When the DES plugin installs the framework data tree
    Then the plugin does not report success
    And the failure names "orchestrator-affordance" as missing
