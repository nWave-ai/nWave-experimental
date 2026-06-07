@feature-fix-mandate-9-v2-rollout
Feature: Mandate 9 v2 rollout slice-02 — behavior + reviewer + skill expansion

  As the Mandate 9 v2 rollout author
  I want the behavioural skill, reviewer agent, and TDD-methodology skill to
  carry the Adapter Integration Slice authoring contract (10-property matrix
  + EXERCISED/N/A/DEFERRED declaration), the Sentinel critique vectors (S3
  mock-tag consistency + adapter-criticality coverage check with 4-step
  mechanical reviewer checklist per spike v2 AUTH-2), and the RED-phase
  semantics distinguishing acceptance RED from adapter-integration RED
  So that DISTILL authors can produce adapter-integration slices against
  a documented contract, Sentinel can mechanically verify them, and crafters
  apply the correct RED-gate semantics during DELIVER
  (per spike v2 §6 surfaces 2, 4, 6, 10 + §7 slice-02 row — behavioral
  change ships against the slice-01 detector; slice-03 closes audit + gate
  promotion).

  Background:
    Given the mandate 9 v2 rollout composition is available

  @walking_skeleton @driving_port @real-io @slice-02 @contract-shape:bounded-change
  Scenario: Distill skill carries the Adapter Integration Slice Authoring section with 10-property matrix
    Given the nw-distill skill document is loaded
    Then the distill skill carries the section heading "Adapter Integration Slice Authoring"
    And the distill skill enumerates the property "Error class taxonomy"
    And the distill skill enumerates the property "Concurrency"
    And the distill skill enumerates the property "Atomicity"
    And the distill skill enumerates the property "Idempotency"
    And the distill skill enumerates the property "Recovery"
    And the distill skill enumerates the property "Edge cases"
    And the distill skill enumerates the property "Observability"
    And the distill skill enumerates the property "Fail-mode contract"
    And the distill skill enumerates the property "Resource-leak absence"
    And the distill skill enumerates the property "Driving-port purity"
    And the distill skill declares the per-property verdict vocabulary "EXERCISED"
    And the distill skill declares the per-property verdict vocabulary "N/A"
    And the distill skill declares the per-property verdict vocabulary "DEFERRED"

  @driving_port @real-io @slice-02 @contract-shape:bounded-change
  Scenario: Acceptance designer reviewer carries critique vector S3 mock-tag consistency and adapter-criticality coverage check
    Given the acceptance designer reviewer agent document is loaded
    Then the reviewer agent declares the critique vector "S3 mock-tag consistency"
    And the reviewer agent declares the critique vector "adapter-criticality coverage check"
    And the reviewer agent enumerates the mechanical checklist step "EXERCISED row cites an AT path"
    And the reviewer agent enumerates the mechanical checklist step "N/A row cites Port contract excerpt"
    And the reviewer agent enumerates the mechanical checklist step "DEFERRED row cites backlog friction ID"
    And the reviewer agent enumerates the mechanical checklist step "Driving-port purity grep"

  @driving_port @real-io @slice-02 @contract-shape:bounded-change
  Scenario: TDD methodology skill carries Adapter Integration Slice RED-Phase Semantics
    Given the nw-tdd-methodology skill document is loaded
    Then the tdd methodology skill carries the section heading "Adapter Integration Slice RED-Phase Semantics"
    And the tdd methodology skill mentions the red phase mode "acceptance RED"
    And the tdd methodology skill mentions the red phase mode "adapter-integration RED"
    And the tdd methodology skill distinguishes red phase semantics by mentioning "property-matrix row"
