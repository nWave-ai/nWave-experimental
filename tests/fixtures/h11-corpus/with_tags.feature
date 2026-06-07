Feature: tagged scenarios round-trip

  @smoke @happy-path
  Scenario: tagged happy path
    Given a tagged precondition
    When the tagged action runs
    Then the tagged outcome holds

  @error
  Scenario: tagged error case
    Given an error precondition
    When the error action runs
    Then the error outcome holds
