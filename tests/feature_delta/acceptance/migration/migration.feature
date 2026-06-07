Feature: Lossless migration from legacy .feature files to embedded Gherkin
  As Ale, the nwave maintainer adopting the unified feature-delta format
  I want to convert existing .feature files into embedded Gherkin blocks
  So that legacy features migrate incrementally without rewriting and
  the round-trip back to .feature is provably byte-identical

  Background:
    Given a clean working directory with no prior nwave-ai state
    And the nwave-ai binary is on PATH

  # ------------------------------------------------------------------
  # Walking Skeleton — migration WS proves the round-trip invariant
  # ------------------------------------------------------------------

  @walking_skeleton @driving_adapter @real-io @adapter-integration @vendor_neutral @US-08 @AC-1
  Scenario: Maintainer migrates a legacy .feature with byte-identical round-trip
    Given a feature directory containing one ".feature" file with three scenarios
    When the maintainer runs "nwave-ai migrate-feature <feature_dir>" via subprocess
    Then the exit code is 0
    And the feature-delta in the directory contains a fenced gherkin block with the original content
    And the original ".feature" file is renamed to ".feature.pre-migration"
    And re-running the extractor produces output byte-identical to the original modulo one trailing newline

  # ------------------------------------------------------------------
  # Round-trip failure aborts cleanly (US-08)
  # ------------------------------------------------------------------

  @US-08 @AC-2 @error
  Scenario: Round-trip diff exceeding tolerance aborts migration
    Given a feature directory whose ".feature" content would lose more than one byte on round-trip
    When the maintainer runs the migration
    Then the exit code is 1
    And no file in the directory is modified
    And stderr contains the diff between original and round-tripped content

  # ------------------------------------------------------------------
  # Multi-file migration (US-08)
  # ------------------------------------------------------------------

  @US-08 @AC-3
  Scenario: Three .feature files migrate to three gherkin blocks preserving boundaries
    Given a feature directory containing three ".feature" files
    When the maintainer runs the migration
    Then the feature-delta contains three separate fenced gherkin blocks
    And each block contains the original file's content
    And round-trip extraction concatenates to content identical to the original concatenation

  # ------------------------------------------------------------------
  # Idempotency (DD-A7b)
  # ------------------------------------------------------------------

  @US-08 @AC-4
  Scenario: Re-running migration on already-migrated directory is a no-op
    Given a feature directory that was previously migrated and contains ".feature.pre-migration" backup
    When the maintainer runs the migration again
    Then the exit code is 0
    And stderr contains "already migrated"
    And no file in the directory is modified

  # ------------------------------------------------------------------
  # G4 zero-side-effects (DD-A4) — migration writes only inside <path>
  # ------------------------------------------------------------------

  @US-08 @AC-5 @US-10 @real-io @adapter-integration
  Scenario: Migration touches only files inside the target feature directory
    Given a sandbox with a feature directory and surrounding monitored files
    And the monitored files include ".git/", ".pre-commit-config.yaml", and shell rc files
    When the maintainer runs the migration on the feature directory
    Then no monitored file outside the feature directory is modified
    And the only modifications inside the feature directory are the feature-delta and the pre-migration backup
