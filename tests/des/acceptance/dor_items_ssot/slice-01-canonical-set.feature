@feature-dor-items-ssot @dor-items-ssot @slice-01
Feature: A reviewer reads the canonical Definition-of-Ready set from one place
  As a reviewer validating whether a story is Ready
  I want to read the complete canonical Definition-of-Ready item-set from one authoritative place
  So that every readiness decision checks the same complete set and no hard-gate item is silently skipped

  Background:
    Given the canonical Definition-of-Ready item-set is published in one authoritative place

  @slice-01 @walking-skeleton @real-io @driving_port @contract-shape:unbounded-preservation
  Scenario: A reviewer sees all nine canonical readiness items from the one place
    When the reviewer reads the canonical readiness item-set
    Then the reviewer sees all nine canonical readiness items
    And the authoritative place is left unchanged after being read

  @slice-01 @real-io @driving_port @contract-shape:unbounded-preservation
  Scenario: The reviewer sees the Outcome-KPIs item among the readiness items
    Given the reviewer has read the canonical readiness item-set
    Then the reviewer sees the readiness item "Outcome KPIs defined with measurable targets"

  @slice-01 @real-io @driving_port @contract-shape:unbounded-preservation
  Scenario: The reviewer is shown job-traceability as a separate hard gate, not a readiness item
    Given the reviewer has read the canonical readiness item-set
    Then the reviewer sees job-traceability listed as a separate hard gate
    And the reviewer does not see job-traceability counted among the nine readiness items
