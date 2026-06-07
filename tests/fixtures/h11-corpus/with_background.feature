Feature: background round-trip

  Background:
    Given a common precondition

  Scenario: first
    Given first context
    When first runs
    Then first holds

  Scenario: second
    Given second context
    When second runs
    Then second holds
