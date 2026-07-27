@feature-dor-items-ssot @dor-items-ssot @slice-02
Feature: The DoR-validation skill the reviewer loads presents the canonical nine
  As a reviewer who loads the Definition-of-Ready validation skill to check readiness
  I want the loaded skill to present the same complete canonical item-set the authoritative place carries
  So that the enforcement path I actually follow no longer silently drops the Outcome-KPIs hard gate

  Background:
    Given the Definition-of-Ready validation skill a reviewer loads

  @slice-02 @real-io @driving_port @contract-shape:unbounded-preservation
  Scenario: The loaded skill stops claiming eight and presents all nine readiness items
    When the reviewer reads the loaded Definition-of-Ready validation skill
    Then the loaded skill no longer claims eight readiness items
    And the loaded skill presents all nine canonical readiness items
    And the loaded skill is left unchanged after being read

  @slice-02 @real-io @driving_port @contract-shape:unbounded-preservation
  Scenario: The loaded skill presents the Outcome-KPIs item it drops today
    Given the reviewer has read the loaded Definition-of-Ready validation skill
    Then the loaded skill presents the readiness item "Outcome KPIs defined with measurable targets and a stated baseline (current-state value the target is measured against)"
    And the loaded skill points at the canonical authoritative place without naming a deprecated data location

  @slice-02 @real-io @driving_port @contract-shape:unbounded-preservation
  Scenario: The readiness items the loaded skill presents match the authoritative place
    Given the reviewer has read the loaded Definition-of-Ready validation skill
    When the reviewer reads the canonical readiness item-set from the authoritative place
    Then the readiness items the loaded skill presents match the authoritative item-set exactly
