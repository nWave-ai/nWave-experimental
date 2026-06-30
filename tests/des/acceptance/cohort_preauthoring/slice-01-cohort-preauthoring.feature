@feature-fix-cohort-gate-preauthoring
Feature: Cohort gate counts pre-authoring candidate ATs from the feature-delta Test Placement list

  Phase-0 cohort classification counts a fresh feature's acceptance tests. A fresh
  feature has no authored Gherkin yet; its candidate ATs live as a numbered prose
  list under the DISTILL Test Placement section of the feature-delta. The cohort
  gate must count that prose list pre-authoring, preserve the authored-scenario
  count once scenarios exist, and report the larger of the two so a fresh feature
  is classified by its real candidate-AT volume instead of zero.

  The observable in every scenario is the candidate-AT count the real
  cohort classifier reports for the crafted hermetic feature-delta. The count
  function is driven directly over feature-delta texts staged under a temporary
  directory; no developer home directory and no real repository deltas are read.

  @slice-01 @US-01 @driving_port @contract-shape:bounded-change
  Scenario: A fresh feature-delta with a Test Placement candidate list and no authored scenarios is counted by its candidate list
    Given a feature-delta listing 4 candidate acceptance tests in its Test Placement section
    And the feature-delta has no authored Gherkin scenarios
    When the cohort classifier counts the feature-delta candidate acceptance tests
    Then the reported candidate-AT count is 4

  @slice-01 @US-01 @driving_port @contract-shape:unbounded-preservation
  Scenario: A feature-delta with authored scenarios still counts those scenarios
    Given a feature-delta with 3 authored Gherkin scenarios
    And the feature-delta has no Test Placement candidate list
    When the cohort classifier counts the feature-delta candidate acceptance tests
    Then the reported candidate-AT count is 3

  @slice-01 @US-01 @driving_port @contract-shape:bounded-change
  Scenario: A feature-delta with both a candidate list and authored scenarios is counted by the larger of the two
    Given a feature-delta listing 4 candidate acceptance tests in its Test Placement section
    And the feature-delta also has 2 authored Gherkin scenarios
    When the cohort classifier counts the feature-delta candidate acceptance tests
    Then the reported candidate-AT count is 4

  @slice-01 @US-01 @driving_port @contract-shape:unbounded-preservation
  Scenario: A feature-delta with neither a candidate list nor authored scenarios counts nothing
    Given a feature-delta with no Test Placement candidate list
    And the feature-delta has no authored Gherkin scenarios
    When the cohort classifier counts the feature-delta candidate acceptance tests
    Then the reported candidate-AT count is 0
