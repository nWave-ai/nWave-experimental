@feature-oss-review-verdict-demotion @slice-05 @coupled:slice-05-keyless-installer
Feature: Installing nWave provisions no signing key and preserves the operator's own

  In the OSS threat model the reviewer signing key holder and the would-be
  forger are the same operator, so the signature buys no guarantee -- it only
  forces the operator to provision a key before a verdict can be recorded. This
  slice DEMOTES the install surface: the reviewer signing plugin is deleted, the
  production plugin registry honestly registers seven plugins, and a fresh
  install completes cleanly on a system with no key anywhere.

  One contract is sacred across the demotion: preserve-by-default. The
  operator's existing .nwave/secrets/reviewer-signing.key is a user file -- the
  demoted installer never reads it and never deletes it. It simply stops being
  consulted.

  The three scenarios below form one coupled AT group
  (@coupled:slice-05-keyless-installer): the preserve-by-default walking
  skeleton, the honest seven-plugin registry, and the keyless fresh install all
  assert one indivisible contract -- "the installer no longer touches signing".
  Dropping the plugin without honestly correcting the registry count ships a
  lying registry; honestly correcting the count while a fresh install still
  writes a key ships a half-demotion; and either without the preserve-by-default
  guarantee risks eating the operator's own file. coupling_justification
  recorded in the slice plan.

  # Driving ports (Mandate 13, Layer 3 composition root + subprocess):
  #   - NWaveInstaller._create_plugin_registry(...) -- the production
  #     composition root that wires the install plugins (registry surface).
  #   - scripts/install/install_nwave.py invoked as a real subprocess against a
  #     tmp_path target -- the full install pipeline (keyless install + key
  #     preservation).
  # Example-based walking skeleton (Mandate 11) -- Layer 3 FS/subprocess
  # acceptance; no PBT machinery.

  @slice-05 @walking_skeleton @driving_port @real-io @contract-shape:unbounded-preservation
  Scenario: Installing over an operator's existing signing key leaves it untouched and drops the signing plugin
    Given an install target that already carries the operator's own signing key
    And no signing key override is set in the operator environment
    When the operator runs the nWave install pipeline against the target
    Then the operator's signing key file is byte-identical to the one they had
    And the production install registry no longer registers the signing plugin

  @slice-05 @driving_port @real-io @contract-shape:bounded-change
  Scenario: The production install registry honestly registers seven plugins
    Given the production nWave installer for the default platform
    When the install plugins are wired into the registry
    Then the registry registers exactly seven plugins
    And none of the registered plugins is the reviewer signing plugin

  @slice-05 @driving_port @real-io @contract-shape:bounded-change
  Scenario: A fresh install on a system with no key anywhere completes and provisions none
    Given a fresh install target with no signing key anywhere
    And no signing key override is set in the operator environment
    When the operator runs the nWave install pipeline against the target
    Then the install completes cleanly
    And no signing key file is provisioned on the target
