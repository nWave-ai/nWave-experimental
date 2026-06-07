@feature-fix-crafter-slim-atd-expert @slice-01
Feature: The crafter agents and the nw-execute dispatch skill declare the SLIM-crafter contract at the prose layer
  As the agent-prose layer of the DELIVER wave
  I want the two crafter agents and the nw-execute classic-template dispatch
    skill to declare, by grep contract, the SLIM-crafter scope —
    no test authoring of any form, and an escalation route to
    nw-acceptance-designer when an AT cannot reach GREEN —
  So that the Q3 conditional-authoring loophole is closed at the dispatch
    surface and the agent surface in a single carpaccio slice, ahead of
    the DES hook layer (slice-03) and the cross-tree handoff (slice-04).

  # slice-01 of F-CRAFTER-SLIM-ATD-EXPERT (DDD-1 + DDD-7 walking-skeleton-
  # first). Driving port: filesystem read over three live repo assets.
  # Observable surface: contract-clause hit counts produced by grep against
  # the file content. Layer 3 (filesystem / project asset), example-only
  # per Mandate 9/11 — no PBT machinery.
  #
  # Contract pinned by these ATs:
  #   * R1 (AT-01a) — nw-software-crafter.md declares no test authoring AND
  #     declares the AT_INSUFFICIENT_FOR_GREEN escalation route. Loophole
  #     text absent.
  #   * R2 (AT-01b) — nw-functional-software-crafter.md REGRESSION GUARD:
  #     loophole text remains absent (the surface is already-clean per
  #     L42/L54/L182/L226 on master). PASS-on-master is intentional and
  #     documented in distill/red-classification.md.
  #   * R3 (AT-01c) — nw-execute SKILL.md classic template loophole removed;
  #     escalation contract present.

  @slice-01 @driving_port @walking_skeleton @contract-shape:unbounded-preservation
  Scenario: The OOP crafter agent declares no test authoring and the AT-insufficient escalation route
    Given the OOP crafter agent file
    When the SLIM-crafter contract audit runs against that surface
    Then no loophole phrase appears in the audited surface
    And the AT_INSUFFICIENT_FOR_GREEN escalation token appears in the audited surface
    And the nw-acceptance-designer route token appears in the audited surface

  @slice-01 @driving_port @regression_guard @contract-shape:unbounded-preservation
  Scenario: The FP crafter agent remains clean of test-authoring loophole text
    Given the FP crafter agent file
    When the SLIM-crafter contract audit runs against that surface
    Then no loophole phrase appears in the audited surface

  @slice-01 @driving_port @walking_skeleton @contract-shape:unbounded-preservation
  Scenario: The nw-execute classic template forbids conditional unit-test authoring and routes to escalation
    Given the nw-execute dispatch skill file
    When the SLIM-crafter contract audit runs against that surface
    Then no loophole phrase appears in the audited surface
    And the AT_INSUFFICIENT_FOR_GREEN escalation token appears in the audited surface
    And the nw-acceptance-designer route token appears in the audited surface
