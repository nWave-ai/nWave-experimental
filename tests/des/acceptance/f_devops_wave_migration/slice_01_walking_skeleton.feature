@feature-f-devops-wave-migration @slice-01 @walking_skeleton @real-io @driving_port
Feature: A maintainer running DEVOPS instruments outcome KPIs against telemetry signals
  # Slice-01 walking skeleton (feature-delta DESIGN Slice Plan FINAL: slice-01
  # carries AT-1..AT-3). The thinnest end-to-end vertical proving the JOB-026
  # "instrument-against-outcomes" job: the DEVOPS prose normatively declares that
  # the gate-IN consumes the DESIGN-OUT pass + DISCUSS Outcome KPIs (applicability
  # first), every outcome KPI maps to a concrete telemetry signal, and the 2nd-Way
  # observability is designed around those signals — instead of after-the-fact
  # monitoring untraced to the outcomes the feature was built to move.
  #
  # Driving surface (Mandate-13, Layer-3 subprocess): the real `des
  # skill-normative-gate` dispatcher reads the REAL shipped
  # nWave/agents/nw-platform-architect.md and
  # nWave/skills/nw-infrastructure-and-observability/SKILL.md and emits
  # PASS/FAIL/INDETERMINATE. The AT asserts the SHIPPED exit code — never a
  # fabricated oracle (protocol-driver contract: the oracle is the gate's real
  # exit code over the real file).
  #
  # Active-RED (atdd_pure / ADR-025, NOT @skip): each f-devops induction marker is
  # ABSENT from the shipped prose at HEAD → the real gate returns FAIL (exit 1) →
  # these scenarios expect PASS → AssertionError. DELIVER migrates the KPI→telemetry
  # + gate-IN-consume prose into the DEVOPS surfaces → the gate returns PASS → green.
  #
  # Mandate 9 v2: @real-io (real subprocess + real filesystem) → example-based;
  # no PBT machinery (Mandate 11).

  @contract-shape:unbounded-preservation @ac-1 @slice-01
  Scenario: The DEVOPS prose declares the gate-IN consumes the design pass and the outcome KPIs
    Given the real shipped DEVOPS agent that the gate-IN consume rule lives in exists
    And a clause asserting the gate-IN consumes the design pass and the outcome KPIs applicability-first
    When the maintainer runs the skill-normative gate through the des dispatcher
    Then the gate verdict is PASS with exit code 0
    And the verdict reports zero failing instrumentation clauses

  @contract-shape:unbounded-preservation @ac-2 @slice-01
  Scenario: The DEVOPS prose declares every outcome KPI maps to a concrete telemetry signal
    Given the real shipped DEVOPS agent that the KPI to telemetry map lives in exists
    And a clause asserting every outcome KPI maps to a concrete telemetry signal
    When the maintainer runs the skill-normative gate through the des dispatcher
    Then the gate verdict is PASS with exit code 0
    And the verdict reports zero failing instrumentation clauses

  @contract-shape:unbounded-preservation @ac-3 @slice-01
  Scenario: The observability prose declares second-way observability is designed around the KPI signals
    Given the real shipped observability skill that the second-way observability rule lives in exists
    And a clause asserting second-way observability is designed around the outcome-KPI signals not generic
    When the maintainer runs the skill-normative gate through the des dispatcher
    Then the gate verdict is PASS with exit code 0
    And the verdict reports zero failing instrumentation clauses
