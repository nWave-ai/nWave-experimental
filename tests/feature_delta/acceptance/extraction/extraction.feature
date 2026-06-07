Feature: Embedded Gherkin extraction for cucumber-family BDD runners
  As Ale, the nwave maintainer using pytest-bdd for acceptance tests
  I want to extract embedded Gherkin blocks from feature-delta.md
  So that any cucumber-family runner can consume the scenarios without
  the markdown narrative drifting from the executable specification

  Background:
    Given a clean working directory with no prior nwave-ai state
    And the nwave-ai binary is on PATH

  # ------------------------------------------------------------------
  # Walking Skeleton — extraction WS proves end-to-end driving adapter
  # ------------------------------------------------------------------

  @walking_skeleton @driving_adapter @real-io @adapter-integration @vendor_neutral @US-06 @AC-1
  Scenario: Maintainer extracts embedded Gherkin and runs scenarios via pytest-bdd
    Given a feature-delta with two fenced gherkin blocks under DISCUSS and DISTILL
    When the maintainer runs "nwave-ai extract-gherkin <path>" via subprocess
    Then the exit code is 0
    And stdout begins with "Feature: " followed by the feature identifier
    And stdout contains both gherkin block contents in document order
    And the produced output parses without errors via pytest-bdd

  # ------------------------------------------------------------------
  # Cross-framework compatibility (US-06)
  # ------------------------------------------------------------------

  @US-06 @AC-2
  Scenario: Extracted feature parses across cucumber-family runners
    Given a feature-delta with one fenced gherkin block
    When the maintainer extracts the gherkin and feeds it to multiple runners
    Then the output parses via pytest-bdd
    And the output parses via cucumber-jvm dry-run
    And the output parses via godog dry-run

  # ------------------------------------------------------------------
  # Empty-input error path (US-06)
  # ------------------------------------------------------------------

  @US-06 @AC-3 @error
  Scenario: Feature-delta with no gherkin blocks reports clear error
    Given a feature-delta containing no fenced gherkin blocks
    When the maintainer runs the extractor
    Then the exit code is 1
    And stderr names the file and "no gherkin blocks found"

  # ------------------------------------------------------------------
  # Multiple blocks preserved in document order (US-06)
  # ------------------------------------------------------------------

  @US-06 @AC-4
  Scenario: Three gherkin blocks across waves concatenated in document order
    Given a feature-delta with three fenced gherkin blocks across DISCUSS, DESIGN, and DISTILL
    When the maintainer extracts the gherkin
    Then stdout contains three scenario sections
    And the order of scenario sections matches the order of blocks in the source document

  # ------------------------------------------------------------------
  # i18n keyword recognition (US-13 R3 extractor side)
  # ------------------------------------------------------------------

  @US-13 @AC-5 @real-io @adapter-integration
  Scenario: Italian language directive preserved in extracted feature
    Given a feature-delta with a fenced gherkin block declaring "# language: it"
    And the block uses "Funzionalità:" as the feature keyword
    When the maintainer extracts the gherkin
    Then stdout preserves the "# language: it" directive
    And stdout preserves the "Funzionalità:" keyword

  # ------------------------------------------------------------------
  # Round-trip with migration (US-08 cross-cutting check)
  # ------------------------------------------------------------------

  @US-06 @AC-5 @US-08
  Scenario: Round-trip extraction matches original .feature within tolerance
    Given a feature-delta produced by migrating an original ".feature" file
    When the maintainer extracts the gherkin from the feature-delta
    Then the extracted output is byte-identical to the original modulo one trailing newline
