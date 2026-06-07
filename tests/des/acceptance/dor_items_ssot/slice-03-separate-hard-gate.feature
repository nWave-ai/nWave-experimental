@feature-dor-items-ssot @dor-items-ssot @slice-03
Feature: The loaded DoR-validation skill tells the reviewer job-traceability is a separate hard gate
  As a reviewer who loads the Definition-of-Ready validation skill to enforce readiness
  I want the loaded skill to tell me, at the point of enforcement, that job-traceability is a separate hard gate above the readiness items
  So that the job-traceability check is never confused for an enumerated readiness item, nor silently skipped alongside one

  Background:
    Given the Definition-of-Ready validation skill a reviewer loads to enforce readiness

  @slice-03 @real-io @driving_port @contract-shape:unbounded-preservation
  Scenario: A reviewer is told job-traceability is a separate hard gate above the readiness items
    When the reviewer reads the loaded Definition-of-Ready validation skill at the point of enforcement
    Then the loaded skill tells the reviewer job-traceability is a separate hard gate above the readiness items

  @slice-03 @real-io @driving_port @contract-shape:unbounded-preservation
  Scenario: The loaded skill keeps job-traceability out of the nine enumerated readiness items
    Given the reviewer has read the loaded Definition-of-Ready validation skill at the point of enforcement
    Then the loaded skill does not count job-traceability among the nine readiness items

  @slice-03 @real-io @driving_port @contract-shape:unbounded-preservation
  Scenario: The separate hard gate the loaded skill presents matches the authoritative place
    Given the reviewer has read the loaded Definition-of-Ready validation skill at the point of enforcement
    When the reviewer reads the separate hard gates from the authoritative place
    Then the separate hard gate the loaded skill presents matches the separate hard gate the authoritative place carries
