@feature-fix-slice-id-regex-suffix-support
Feature: Slice-Id regex accepts canonical + phase-suffix + letter-suffix shapes

  As an nWave orchestrator authoring slice commits across atdd_pure carpaccio
  I want the Slice-Id/Step-Id trailer regex to accept three shapes:
    - canonical `slice-NN` (e.g. `slice-01`)
    - phase-suffix `slice-NN-PHASE` (e.g. `slice-02-A_GREEN_ATS`)
    - letter-suffix `slice-NNa` (e.g. `slice-03a`)
  So that backfill via verify_slice_commit_completeness CLI parses every
  shipped commit trailer (cascade-blocker friction #10 anchor 2026-05-26)
  And the carpaccio gate accepts architect's sibling-class decomposition tags
  And customer trailers carrying only canonical `slice-NN` continue parsing
  byte-identical (regression-pin)

  Background:
    Given the Slice-Id trailer regex is loaded from verify_slice_commit_completeness

  @walking_skeleton @driving_port @in-process @real-io @slice-01 @contract-shape:pure-function
  Scenario: Phase-suffix Slice-Id trailer parses to bare slice-NN
    Given the commit message body is exactly "Slice-Id: slice-02-A_GREEN_ATS"
    When the trailer regex extracts the slice-id
    Then the extracted slice-id is exactly "slice-02"

  @driving_port @in-process @real-io @slice-01 @contract-shape:pure-function
  Scenario: Letter-suffix Slice-Id trailer parses to slice-NN-letter
    Given the commit message body is exactly "Slice-Id: slice-03a"
    When the trailer regex extracts the slice-id
    Then the extracted slice-id is exactly "slice-03a"

  @driving_port @in-process @real-io @slice-01 @regression-pin @contract-shape:unbounded-preservation
  Scenario: Canonical Slice-Id trailer continues parsing byte-identical
    Given the commit message body is exactly "Slice-Id: slice-01"
    When the trailer regex extracts the slice-id
    Then the extracted slice-id is exactly "slice-01"
