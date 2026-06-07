@feature-fix-mandate-9-v2-rollout
Feature: Mandate 9 v2 rollout slice-03 — audit closure + gate promotion + project-local criticality

  As the Mandate 9 v2 rollout author
  I want the retro-audit artifact populated with verdict rows, the carpaccio
  gate's MandateNineTagMismatch detector promoted from non-blocking warning
  to a blocking gate (exit code 44 on mismatch), and the project-local
  Adapter Criticality table seeded with at least one classified
  (Port, Adapter) pair
  So that mislabeled `@real-io` scenarios across nwave-dev are catalogued
  with closure verdicts, future crafters writing mismatched ATs are stopped
  by the gate rather than warned, and the project policy carries the
  classification SSOT for project-local adapters
  (per spike v2 §7 slice-03 row — audit closure ships LAST after warning
  baseline gathered + audit catalog populated; big-bang re-tag forbidden
  per MIG-1; snapshot scope frozen at slice-01 commit SHA per MIG-3).

  Background:
    Given the mandate 9 v2 rollout slice-03 composition is available

  @walking_skeleton @driving_port @real-io @slice-03 @contract-shape:bounded-change
  Scenario: Retro-audit artifact carries at least one populated verdict row
    Given the retro-audit artifact at the architecture path is loaded for slice-03 closure
    When the audit body rows are counted by verdict
    Then the retro-audit carries at least one populated row
    And the populated row verdict is one of the closed vocabulary "CORRECT" "MISLABEL" "MIXED"
    And the retro-audit header still carries the column "verdict"
    And the retro-audit header still carries the column "re-tag action"

  @driving_port @real-io @slice-03 @contract-shape:bounded-change
  Scenario: MandateNineTagMismatch detector in blocking mode raises exit code 44 on mismatch
    Given a scenario tagged "@real-io" at "tests/example.feature" line 17 for blocking detector
    And the composition root constructs only "MockAdapter" and "StubAdapter" for blocking detector
    And the mandate 9 detector blocking mode is on
    When the carpaccio gate runs the mandate 9 tag-mismatch detector in blocking mode
    Then the detector raises the gate error with exit code 44
    And the detector gate error payload event is named "MandateNineTagMismatch"
    And the detector gate error payload severity is "BLOCKING"

  @driving_port @real-io @slice-03 @contract-shape:bounded-change
  Scenario: ATDD infrastructure policy carries Adapter Criticality table with at least one classified pair
    Given the atdd infrastructure policy document at the architecture path is loaded
    When the adapter criticality rows are counted
    Then the atdd infrastructure policy carries the section heading "Adapter Criticality"
    And the adapter criticality table carries the column "Port"
    And the adapter criticality table carries the column "Adapter"
    And the adapter criticality table carries the column "Criticality"
    And the adapter criticality table carries the column "Required slices"
    And the adapter criticality table carries at least one classified pair
    And one classified pair carries the criticality literal "CRITICAL"
